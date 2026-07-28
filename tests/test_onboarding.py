"""П.13: онбординг-цепочка на 3 дня (bot/scheduler.onboarding_chain)."""
from datetime import UTC, datetime, timedelta

from bot import config, db, keyboards, scheduler, texts
from tests.test_scheduler_queries import FakeBot


async def _set_created_days_ago(n: int) -> None:
    """Отодвинуть created_at охотника на n локальных суток назад.

    Вычитаем n дней у локального (config.TZ) времени, а не у UTC: так дата
    сдвигается ровно на n суток независимо от часа запуска теста, и результат
    записывается в БД тем же форматом, что и SQLite datetime('now') — наивная
    строка в UTC.
    """
    local = datetime.now(config.TZ) - timedelta(days=n)
    utc_str = local.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")
    await db.update_user(1, created_at=utc_str)


async def test_step1_silent_before_one_day(conn, user, monkeypatch):
    """Зарегистрированный только что охотник шаг 1 не получает."""
    monkeypatch.setattr(scheduler, "_SEND_INTERVAL", 0)
    bot = FakeBot()

    await scheduler.onboarding_chain(bot)

    assert bot.sent == []
    assert (await db.get_user(1))["onboarding_day"] == 0


async def test_step1_fires_after_one_day(conn, user, monkeypatch):
    await _set_created_days_ago(1)
    monkeypatch.setattr(scheduler, "_SEND_INTERVAL", 0)
    bot = FakeBot()

    await scheduler.onboarding_chain(bot)

    assert bot.sent == [(1, texts.ONBOARDING_DAY1_REPORT_HINT)]
    assert bot.markups == [keyboards.onboarding_stop()]
    assert (await db.get_user(1))["onboarding_day"] == 1


async def test_step_not_resent_on_second_run(conn, user, monkeypatch):
    """Повторный прогон в тот же день не дублирует уже отправленный шаг."""
    await _set_created_days_ago(1)
    monkeypatch.setattr(scheduler, "_SEND_INTERVAL", 0)
    bot = FakeBot()

    await scheduler.onboarding_chain(bot)
    await scheduler.onboarding_chain(bot)

    assert len(bot.sent) == 1


async def test_steps_do_not_batch_catch_up(conn, user, monkeypatch):
    """Охотник, пропавший на 3+ дня, получает шаги по одному за прогон, не все разом."""
    await _set_created_days_ago(5)
    monkeypatch.setattr(scheduler, "_SEND_INTERVAL", 0)
    bot = FakeBot()

    await scheduler.onboarding_chain(bot)
    assert len(bot.sent) == 1
    assert bot.sent[0][1] == texts.ONBOARDING_DAY1_REPORT_HINT
    assert (await db.get_user(1))["onboarding_day"] == 1

    await scheduler.onboarding_chain(bot)
    assert len(bot.sent) == 2
    assert bot.sent[1][1] == texts.ONBOARDING_DAY2_BOSS_RATING
    assert (await db.get_user(1))["onboarding_day"] == 2

    await scheduler.onboarding_chain(bot)
    assert len(bot.sent) == 3
    assert "https://t.me/" in bot.sent[2][1]
    assert (await db.get_user(1))["onboarding_day"] == 3

    # Цепочка исчерпана — дальнейшие прогоны молчат
    await scheduler.onboarding_chain(bot)
    assert len(bot.sent) == 3


async def test_opt_out_stops_all_future_steps(conn, user, monkeypatch):
    await _set_created_days_ago(5)
    await db.update_user(1, onboarding_day=config.ONBOARDING_STOP)
    monkeypatch.setattr(scheduler, "_SEND_INTERVAL", 0)
    bot = FakeBot()

    await scheduler.onboarding_chain(bot)

    assert bot.sent == []
    assert (await db.get_user(1))["onboarding_day"] == config.ONBOARDING_STOP


async def test_opt_out_callback_stops_chain(conn, user, monkeypatch):
    """Кнопка «Не напоминать» ставит сентинел и глушит все последующие шаги."""
    from bot.handlers.onboarding import cb_stop_onboarding

    class FakeMessage:
        async def edit_reply_markup(self, reply_markup=None):
            pass

    class FakeUser:
        id = 1

    class FakeCallback:
        data = "onb:stop"
        from_user = FakeUser()
        message = FakeMessage()

        async def answer(self, text=None, show_alert=False):
            self.answered_with = text

    callback = FakeCallback()
    await cb_stop_onboarding(callback)

    assert (await db.get_user(1))["onboarding_day"] == config.ONBOARDING_STOP

    await _set_created_days_ago(5)
    monkeypatch.setattr(scheduler, "_SEND_INTERVAL", 0)
    bot = FakeBot()
    await scheduler.onboarding_chain(bot)
    assert bot.sent == []
