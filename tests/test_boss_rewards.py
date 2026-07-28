"""Б.10: награды за босса выдаются сразу после добивания, ровно один раз.

Главное, что проверяется: XP не начисляется дважды (мгновенная выдача против
воскресного джоба и против второго параллельного таска) и о падении босса
узнают все участники рейда, а не только нанёсший последний удар.
"""
import asyncio

import pytest

from bot import boss as boss_mod
from bot import config, db, game, scheduler, texts
from bot.handlers import helpers


class FakeBot:
    """Заглушка бота: собирает отправленные сообщения вместо походов в Telegram."""

    def __init__(self):
        self.sent: list[tuple[int, str]] = []
        self.markups: list[object] = []

    async def send_message(self, user_id: int, text: str, reply_markup=None) -> None:
        self.sent.append((user_id, text))
        self.markups.append(reply_markup)


class FakeUser:
    def __init__(self, user_id: int):
        self.id = user_id


class FakeMessage:
    """Минимальный Message для хендлерных хелперов: answer + bot + from_user."""

    def __init__(self, user_id: int, bot: FakeBot):
        self.bot = bot
        self.from_user = FakeUser(user_id)
        self.answers: list[str] = []

    async def answer(self, text: str, **kwargs) -> None:
        self.answers.append(text)


async def _make_raid(*damages: int):
    """Создать босса и участников с заданным уроном; вернуть строку босса.

    Урон пишется напрямую через db.damage_boss, поэтому HP босса падает до нуля
    и он помечается defeated — ровно так же, как при добивании через grant_xp.
    """
    boss = await db.create_boss(boss_mod.week_key(), "Тестовый Босс", sum(damages))
    for i, damage in enumerate(damages, start=1):
        if i != 1:
            await db.create_user(i, f"hunter{i}", f"Охотник {i}")
        await db.damage_boss(boss["id"], i, damage)
    return await db.get_boss(boss_mod.week_key())


async def _weekly_xp(user_id: int) -> int:
    user = await db.get_user(user_id)
    return user["weekly_xp"]


@pytest.fixture
def no_throttle(monkeypatch):
    monkeypatch.setattr(scheduler, "_SEND_INTERVAL", 0)


# ---------- сама выдача ----------

async def test_rewards_granted_once_and_flag_set(conn, user, no_throttle):
    boss = await _make_raid(100, 50)
    bot = FakeBot()

    await scheduler.distribute_boss_rewards(bot)

    assert (await db.get_boss(boss_mod.week_key()))["rewarded"] == 1
    # Оба участника в топ-3 (их всего двое) → база + бонус
    expected = config.BOSS_REWARD_XP + config.BOSS_TOP_REWARD_XP
    assert await _weekly_xp(1) == expected
    assert await _weekly_xp(2) == expected
    assert len(bot.sent) == 2
    assert boss["name"] in bot.sent[0][1]


async def test_second_call_is_noop(conn, user, no_throttle):
    await _make_raid(100, 50)
    bot = FakeBot()

    await scheduler.distribute_boss_rewards(bot)
    first = await _weekly_xp(1)
    bot.sent.clear()
    await scheduler.distribute_boss_rewards(bot)

    assert await _weekly_xp(1) == first
    assert bot.sent == []


async def test_weekly_report_after_instant_payout_does_not_double(conn, user, no_throttle):
    """Воскресный джоб — только страховка: после мгновенной выдачи он молчит."""
    await _make_raid(100, 50)
    bot = FakeBot()

    await scheduler.distribute_boss_rewards(bot)
    paid = await _weekly_xp(1)
    reward_messages = len(bot.sent)

    await scheduler.weekly_report(bot)

    # weekly_report обнуляет недельные счётчики, поэтому сверяем сам факт
    # повторной выдачи: сообщение о награде должно быть ровно одно на участника.
    assert sum(1 for _, text in bot.sent if "НАГРАДА РЕЙДА" in text) == reward_messages
    assert paid == config.BOSS_REWARD_XP + config.BOSS_TOP_REWARD_XP


async def test_parallel_tasks_pay_once(conn, user, no_throttle):
    """Два таска на одного босса: право на выдачу занимает только один."""
    await _make_raid(100, 50)
    bot = FakeBot()

    await asyncio.gather(
        scheduler.distribute_boss_rewards(bot),
        scheduler.distribute_boss_rewards(bot),
    )

    assert await _weekly_xp(1) == config.BOSS_REWARD_XP + config.BOSS_TOP_REWARD_XP
    assert len(bot.sent) == 2  # по одному сообщению на участника, не по два


async def test_top3_get_bonus_others_base(conn, user, no_throttle):
    await _make_raid(500, 400, 300, 200, 100)
    bot = FakeBot()

    await scheduler.distribute_boss_rewards(bot)

    top_reward = config.BOSS_REWARD_XP + config.BOSS_TOP_REWARD_XP
    for uid in (1, 2, 3):
        assert await _weekly_xp(uid) == top_reward
    for uid in (4, 5):
        assert await _weekly_xp(uid) == config.BOSS_REWARD_XP
    bonus_messages = [text for _, text in bot.sent if texts.BOSS_REWARD_TOP_BONUS in text]
    assert len(bonus_messages) == 3


async def test_all_participants_notified(conn, user, no_throttle):
    """Регресс AUDIT 1.6: о падении босса узнаёт весь рейд, а не только добивший."""
    await _make_raid(300, 200, 100)
    bot = FakeBot()

    await scheduler.distribute_boss_rewards(bot)

    assert {uid for uid, _ in bot.sent} == {1, 2, 3}


async def test_deleted_participant_skipped(conn, user, no_throttle):
    """Удалённый охотник не ломает выдачу остальным."""
    await _make_raid(300, 200)
    await db.delete_user_data(2)
    bot = FakeBot()

    await scheduler.distribute_boss_rewards(bot)

    assert [uid for uid, _ in bot.sent] == [1]
    assert await _weekly_xp(1) == config.BOSS_REWARD_XP + config.BOSS_TOP_REWARD_XP


async def test_alive_boss_not_rewarded(conn, user, no_throttle):
    boss = await db.create_boss(boss_mod.week_key(), "Живой Босс", 1000)
    await db.damage_boss(boss["id"], 1, 10)
    bot = FakeBot()

    await scheduler.distribute_boss_rewards(bot)

    assert (await db.get_boss(boss_mod.week_key()))["rewarded"] == 0
    assert await _weekly_xp(1) == 0
    assert bot.sent == []


# ---------- запуск из хендлера ----------

async def test_spawn_reuses_running_task(conn, user, no_throttle):
    await _make_raid(100, 50)
    bot = FakeBot()

    first = scheduler.spawn_boss_rewards(bot)
    second = scheduler.spawn_boss_rewards(bot)
    assert first is second

    await first
    assert len(bot.sent) == 2
    # Завершившийся таск убран из словаря — следующая неделя стартует чисто
    assert scheduler._reward_tasks == {}


async def test_notify_side_effects_pays_immediately(conn, user, no_throttle):
    """Добивший получает свой текст сразу, награды уходят фоновым таском."""
    await _make_raid(100, 50)
    bot = FakeBot()
    message = FakeMessage(1, bot)
    result = game.XpResult(boss_killed=True)

    await helpers.notify_side_effects(message, result, user_id=1)
    await asyncio.gather(*scheduler._reward_tasks.values())

    assert any("Последний удар" in text for text in message.answers)
    assert not any("НАГРАДА РЕЙДА" in text for text in message.answers)
    assert {uid for uid, _ in bot.sent} == {1, 2}
    assert (await db.get_boss(boss_mod.week_key()))["rewarded"] == 1


async def test_notify_side_effects_without_kill_does_not_spawn(conn, user, no_throttle):
    await _make_raid(100, 50)
    bot = FakeBot()
    message = FakeMessage(1, bot)

    await helpers.notify_side_effects(message, game.XpResult(), user_id=1)

    assert scheduler._reward_tasks == {}
    assert bot.sent == []
    assert await _weekly_xp(1) == 0
