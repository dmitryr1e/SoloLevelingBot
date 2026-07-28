"""Тесты /addquest: FSM вместо модульного словаря (спринт А, п. 6).

Хендлеры вызываются напрямую с поддельными Message/CallbackQuery и настоящим
FSMContext на MemoryStorage — Telegram для этого не нужен.
"""
from datetime import timedelta

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from bot import config, db, game, texts
from bot.handlers import custom
from bot.handlers.custom import AddQuestFlow, cb_pick_stat, cb_pick_stat_stale, cmd_addquest


class FakeMessage:
    """Message с минимумом, который нужен хендлеру: from_user.id и answer()."""

    def __init__(self, user_id: int = 1):
        self.from_user = type("U", (), {"id": user_id})()
        self.answers: list[str] = []
        self.edits: list[str] = []

    async def answer(self, text: str, **kwargs) -> None:
        self.answers.append(text)

    async def edit_text(self, text: str, **kwargs) -> None:
        self.edits.append(text)


class FakeCallback:
    def __init__(self, data: str, user_id: int = 1):
        self.data = data
        self.from_user = type("U", (), {"id": user_id})()
        self.message = FakeMessage(user_id)
        self.alerts: list[str] = []

    async def answer(self, text: str | None = None, **kwargs) -> None:
        if text is not None:
            self.alerts.append(text)


class FakeCommand:
    def __init__(self, args: str | None):
        self.args = args


@pytest.fixture
def fsm():
    """Настоящий FSMContext на MemoryStorage — как в боте по умолчанию."""
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=1, user_id=1)
    return FSMContext(storage=storage, key=key)


async def test_addquest_sets_state_and_title(user, fsm):
    message = FakeMessage()
    await cmd_addquest(message, FakeCommand("50 отжиманий"), fsm)

    assert await fsm.get_state() == AddQuestFlow.waiting_stat
    assert (await fsm.get_data())["title"] == "50 отжиманий"
    assert "50 отжиманий" in message.answers[0]


async def test_pending_titles_dict_is_gone():
    """Модульный словарь состояния удалён — состояние живёт только в FSM."""
    assert not hasattr(custom, "_pending_titles")


@pytest.mark.parametrize("args", [None, "", "   ", "x" * 81])
async def test_addquest_rejects_bad_title(user, fsm, args):
    message = FakeMessage()
    await cmd_addquest(message, FakeCommand(args), fsm)

    assert message.answers == [texts.ADDQUEST_USAGE]
    assert await fsm.get_state() is None  # протокол не начат


async def test_addquest_refuses_over_limit(user, fsm):
    for i in range(config.FREE_CUSTOM_QUESTS):
        await db.add_custom_quest(1, f"квест {i}", "strength")

    message = FakeMessage()
    await cmd_addquest(message, FakeCommand("ещё один"), fsm)

    assert texts.ADDQUEST_LIMIT.format(limit=config.FREE_CUSTOM_QUESTS) in message.answers[0]
    assert await fsm.get_state() is None


async def test_full_flow_saves_quest_and_clears_state(user, fsm):
    await cmd_addquest(FakeMessage(), FakeCommand("медитация"), fsm)

    callback = FakeCallback("cqstat:intelligence")
    await cb_pick_stat(callback, fsm)

    saved = await db.custom_quests(1)
    assert [(q["title"], q["stat"]) for q in saved] == [("медитация", "intelligence")]
    assert await fsm.get_state() is None  # состояние очищено
    assert await fsm.get_data() == {}
    assert "медитация" in callback.message.edits[0]


async def test_flow_adds_quest_to_today_if_day_issued(user, fsm):
    """Если день уже выдан, квест появляется в сегодняшнем списке сразу."""
    await game.ensure_today(user)
    before = len(await db.quests_for_date(1, game.today_str()))

    await cmd_addquest(FakeMessage(), FakeCommand("турник"), fsm)
    await cb_pick_stat(FakeCallback("cqstat:strength"), fsm)

    today = await db.quests_for_date(1, game.today_str())
    assert len(today) == before + 1
    added = [q for q in today if q["title"] == "турник"]
    assert len(added) == 1
    assert added[0]["is_custom"] == 1


async def test_flow_skips_today_if_day_not_issued(user, fsm):
    """Без выданного дня квест только в реестре, в quests его нет."""
    await cmd_addquest(FakeMessage(), FakeCommand("турник"), fsm)
    await cb_pick_stat(FakeCallback("cqstat:strength"), fsm)

    assert len(await db.custom_quests(1)) == 1
    assert await db.quests_for_date(1, game.today_str()) == []


async def test_unknown_stat_rejected(user, fsm):
    await cmd_addquest(FakeMessage(), FakeCommand("медитация"), fsm)

    callback = FakeCallback("cqstat:wisdom")  # такого стата нет
    await cb_pick_stat(callback, fsm)

    assert await db.custom_quests(1) == []
    assert callback.alerts == [texts.ADDQUEST_EXPIRED]
    assert await fsm.get_state() is None


async def test_limit_rechecked_at_confirmation(user, fsm):
    """TOCTOU: лимит выбран, пока пользователь думал над статом."""
    await cmd_addquest(FakeMessage(), FakeCommand("ещё один"), fsm)
    for i in range(config.FREE_CUSTOM_QUESTS):
        await db.add_custom_quest(1, f"квест {i}", "strength")

    callback = FakeCallback("cqstat:strength")
    await cb_pick_stat(callback, fsm)

    assert len(await db.custom_quests(1)) == config.FREE_CUSTOM_QUESTS  # новый не добавлен
    assert callback.alerts == [
        texts.ADDQUEST_LIMIT_SHORT.format(limit=config.FREE_CUSTOM_QUESTS)
    ]
    assert await fsm.get_state() is None


async def test_premium_limit_is_higher(user, fsm):
    future = (game.datetime.now(config.TZ).date() + timedelta(days=30)).strftime("%Y-%m-%d")
    await db.update_user(1, premium_until=future)
    for i in range(config.FREE_CUSTOM_QUESTS):
        await db.add_custom_quest(1, f"квест {i}", "strength")

    message = FakeMessage()
    await cmd_addquest(message, FakeCommand("премиум-квест"), fsm)

    assert await fsm.get_state() == AddQuestFlow.waiting_stat
    await cb_pick_stat(FakeCallback("cqstat:agility"), fsm)
    assert len(await db.custom_quests(1)) == config.FREE_CUSTOM_QUESTS + 1


async def test_deleted_user_gets_alert(user, fsm):
    await cmd_addquest(FakeMessage(), FakeCommand("медитация"), fsm)
    await db.delete_user_data(1)

    callback = FakeCallback("cqstat:strength")
    await cb_pick_stat(callback, fsm)

    assert callback.alerts == [texts.ADDQUEST_EXPIRED]
    assert await fsm.get_state() is None


async def test_stale_callback_answers_instead_of_hanging(user):
    """Кнопка нажата после рестарта: пользователь получает алерт, не вечный спиннер."""
    callback = FakeCallback("cqstat:strength")
    await cb_pick_stat_stale(callback)

    assert callback.alerts == [texts.ADDQUEST_EXPIRED]
    assert await db.custom_quests(1) == []
