"""А.7: агрегатные выборки для фоновых джобов (индексы + отсутствие N+1).

Ключевая проверка — новые запросы дают ровно те же «сделано/всего», что и
старый путь через db.quests_for_date в цикле, включая пользователя без квестов.
"""
from datetime import datetime

from bot import config, db, game, keyboards, scheduler, texts, timeutil


async def _legacy_progress(user_id: int, date: str) -> tuple[int, int]:
    """Старый путь: строки квестов за дату и подсчёт в Python."""
    quests = await db.quests_for_date(user_id, date)
    return len(quests), sum(1 for q in quests if q["done"])


async def _add_quests(user_id: int, date: str, total: int, done: int) -> None:
    rows = [
        (user_id, f"Квест {i}", "strength", 10, date, 0)
        for i in range(total)
    ]
    await db.insert_quests(rows)
    if done:
        ids = [q["id"] for q in await db.quests_for_date(user_id, date)][:done]
        for quest_id in ids:
            await db.mark_quest_done(quest_id)


# ---------- индексы ----------

async def test_new_indexes_created(conn):
    cur = await conn.execute("SELECT name FROM sqlite_master WHERE type = 'index'")
    names = {row["name"] for row in await cur.fetchall()}
    assert "idx_users_reminder" in names
    assert "idx_quests_date" in names
    assert "idx_boss_damage_user" in names


async def test_reminder_query_uses_index(conn):
    cur = await conn.execute(
        "EXPLAIN QUERY PLAN SELECT * FROM users WHERE reminder_time = ?", ("20:00",)
    )
    plan = " ".join(row["detail"] for row in await cur.fetchall())
    assert "idx_users_reminder" in plan


# ---------- quests_progress_for_date ----------

async def test_progress_matches_legacy_path(conn, user):
    today = game.today_str()
    await db.create_user(2, "two", "Второй")
    await db.create_user(3, "three", "Третий")
    await _add_quests(1, today, total=3, done=2)
    await _add_quests(2, today, total=2, done=0)
    # user_id=3 — без квестов: строки в агрегате быть не должно

    progress = await db.quests_progress_for_date(today)

    assert progress[1] == await _legacy_progress(1, today)
    assert progress[2] == await _legacy_progress(2, today)
    assert 3 not in progress
    assert await _legacy_progress(3, today) == (0, 0)


async def test_progress_ignores_other_dates(conn, user, days_ago):
    today, yesterday = game.today_str(), days_ago(1)
    await _add_quests(1, yesterday, total=4, done=4)
    await _add_quests(1, today, total=2, done=1)

    assert (await db.quests_progress_for_date(today))[1] == (2, 1)
    assert (await db.quests_progress_for_date(yesterday))[1] == (4, 4)


async def test_progress_empty_day(conn, user):
    assert await db.quests_progress_for_date(game.today_str()) == {}


# ---------- users_with_reminder_progress ----------

async def test_reminder_progress_has_zeroes_without_quests(conn, user):
    rows = await db.users_with_reminder_progress(
        config.DEFAULT_REMINDER, game.today_str(), ""
    )
    assert [r["user_id"] for r in rows] == [1]
    # Пользователь без квестов приходит с нулями, а не с NULL
    assert (rows[0]["quests_total"], rows[0]["quests_done"]) == (0, 0)


async def test_reminder_progress_matches_legacy(conn, user):
    today = game.today_str()
    await db.create_user(2, "two", "Второй")
    await db.update_user(2, reminder_time="07:30")
    await _add_quests(1, today, total=3, done=1)
    await _add_quests(2, today, total=1, done=1)

    rows = await db.users_with_reminder_progress(config.DEFAULT_REMINDER, today, "")
    assert [r["user_id"] for r in rows] == [1]
    assert (rows[0]["quests_total"], rows[0]["quests_done"]) == await _legacy_progress(
        1, today
    )
    # Совпадает и набор колонок users — джоб читает streak из той же строки
    assert rows[0]["streak"] == 0

    other = await db.users_with_reminder_progress("07:30", today, "")
    assert [r["user_id"] for r in other] == [2]
    assert (other[0]["quests_total"], other[0]["quests_done"]) == (1, 1)

    # Пояс — часть фильтра: тот же охотник в выборке другого пояса не появится
    await db.set_timezone(1, "Asia/Vladivostok", "2026-01-01T00:00:00+00:00")
    assert await db.users_with_reminder_progress(config.DEFAULT_REMINDER, today, "") == []
    moved = await db.users_with_reminder_progress(
        config.DEFAULT_REMINDER, today, "Asia/Vladivostok"
    )
    assert [r["user_id"] for r in moved] == [1]


# ---------- users_in_streak_danger ----------

async def test_streak_danger_selects_only_pending_and_long_streak(conn, user):
    today = game.today_str()
    min_streak = config.DEADLINE_MIN_STREAK
    # 1 — серия достаточная, есть незакрытые квесты → попадает
    await db.update_user(1, streak=min_streak)
    await _add_quests(1, today, total=3, done=1)
    # 2 — серия короткая → отсекается в SQL
    await db.create_user(2, "two", "Второй")
    await db.update_user(2, streak=min_streak - 1)
    await _add_quests(2, today, total=2, done=0)
    # 3 — всё выполнено → отсекается
    await db.create_user(3, "three", "Третий")
    await db.update_user(3, streak=min_streak + 5)
    await _add_quests(3, today, total=2, done=2)
    # 4 — квестов нет вовсе → отсекается
    await db.create_user(4, "four", "Четвёртый")
    await db.update_user(4, streak=min_streak + 1)

    rows = await db.users_in_streak_danger(today, min_streak, "")

    assert [r["user_id"] for r in rows] == [1]
    total, done = rows[0]["quests_total"], rows[0]["quests_done"]
    assert (total, done) == await _legacy_progress(1, today)
    assert total - done == 2
    assert rows[0]["streak"] == min_streak


async def test_streak_danger_ignores_yesterday_quests(conn, user, days_ago):
    await db.update_user(1, streak=config.DEADLINE_MIN_STREAK)
    await _add_quests(1, days_ago(1), total=2, done=0)

    rows = await db.users_in_streak_danger(
        game.today_str(), config.DEADLINE_MIN_STREAK, ""
    )
    assert rows == []


# ---------- сами джобы (используют новые колонки строк) ----------

class FakeBot:
    """Заглушка бота: собирает отправленные сообщения вместо походов в Telegram."""

    def __init__(self):
        self.sent: list[tuple[int, str]] = []
        self.markups: list[object] = []

    async def send_message(self, user_id: int, text: str, reply_markup=None) -> None:
        self.sent.append((user_id, text))
        self.markups.append(reply_markup)


async def _reminder_now() -> str:
    """Выставить охотнику время напоминания «прямо сейчас» (без жёстких дат)."""
    hhmm = datetime.now(config.TZ).strftime("%H:%M")
    await db.update_user(1, reminder_time=hhmm)
    return hhmm


async def test_send_reminders_counts_pending(conn, user, monkeypatch):
    await _add_quests(1, game.today_str(), total=3, done=1)
    await _reminder_now()
    monkeypatch.setattr(scheduler, "_SEND_INTERVAL", 0)
    bot = FakeBot()

    await scheduler.send_reminders(bot)

    assert len(bot.sent) == 1
    assert "2" in bot.sent[0][1]  # осталось 2 квеста


async def test_send_reminders_all_done_variant(conn, user, monkeypatch):
    await _add_quests(1, game.today_str(), total=2, done=2)
    await _reminder_now()
    monkeypatch.setattr(scheduler, "_SEND_INTERVAL", 0)
    bot = FakeBot()

    await scheduler.send_reminders(bot)

    assert len(bot.sent) == 1
    assert bot.sent[0][1] == texts.REMINDER_ALL_DONE.format(streak=0)


def _freeze_deadline(monkeypatch, hour: int | None = None, minute: int = 5) -> None:
    """Подменить локальное время пояса на «час дедлайна».

    Джоб streak_danger тикает каждые 15 минут и рассылает только тем поясам,
    где сейчас начался DEADLINE_HOUR, — без подмены времени тест был бы
    зелёным лишь один час в сутки.
    """
    hour = config.DEADLINE_HOUR if hour is None else hour
    today = datetime.now(config.TZ)

    def fake_now_in(tz_name):
        return today.replace(hour=hour, minute=minute, second=0, microsecond=0)

    monkeypatch.setattr(timeutil, "now_in", fake_now_in)


async def test_streak_danger_job_sends_once(conn, user, monkeypatch):
    await db.update_user(1, streak=config.DEADLINE_MIN_STREAK)
    await _add_quests(1, game.today_str(), total=4, done=1)
    monkeypatch.setattr(scheduler, "_SEND_INTERVAL", 0)
    _freeze_deadline(monkeypatch)
    bot = FakeBot()

    await scheduler.streak_danger(bot)

    assert bot.sent == [
        (
            1,
            texts.STREAK_DANGER.format(
                pending=3, streak=config.DEADLINE_MIN_STREAK
            ),
        )
    ]
    # Апселл заморозки — в момент реальной угрозы серии
    assert bot.markups == [keyboards.upsell(config.UPSELL_FREEZE)]


async def test_streak_danger_job_hides_freeze_upsell_if_charged(
    conn, user, monkeypatch
):
    """У кого есть заряд заморозки — того не просят её купить."""
    await db.update_user(1, streak=config.DEADLINE_MIN_STREAK, streak_freezes=1)
    await _add_quests(1, game.today_str(), total=4, done=1)
    monkeypatch.setattr(scheduler, "_SEND_INTERVAL", 0)
    _freeze_deadline(monkeypatch)
    bot = FakeBot()

    await scheduler.streak_danger(bot)

    assert len(bot.sent) == 1
    assert bot.markups == [None]


async def test_streak_danger_job_silent_outside_window(conn, user, monkeypatch):
    """Вне часа дедлайна и во второй половине часа джоб молчит.

    Второй случай — защита от дублей: джоб тикает 4 раза в час, попадание
    должно быть ровно одно (окно minute < 15).
    """
    await db.update_user(1, streak=config.DEADLINE_MIN_STREAK)
    await _add_quests(1, game.today_str(), total=4, done=1)
    monkeypatch.setattr(scheduler, "_SEND_INTERVAL", 0)

    _freeze_deadline(monkeypatch, hour=(config.DEADLINE_HOUR + 3) % 24)
    bot = FakeBot()
    await scheduler.streak_danger(bot)
    assert bot.sent == []

    _freeze_deadline(monkeypatch, minute=30)
    bot = FakeBot()
    await scheduler.streak_danger(bot)
    assert bot.sent == []
