"""Общая настройка тестов: изолированная БД на каждый тест."""
import asyncio
import os
import sys
from datetime import timedelta

import pytest
import pytest_asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test:token")
os.environ.setdefault("GEMINI_API_KEY", "")

from bot import config, db, game, scheduler  # noqa: E402


@pytest_asyncio.fixture
async def conn(tmp_path, monkeypatch):
    """Свежая БД в tmp_path на каждый тест."""
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "test.db"))
    # Замки — модульные global-словари. asyncio.Lock привязывается к тому
    # event loop, где его впервые взяли, поэтому между тестами (у каждого свой
    # loop) их обязательно надо чистить, иначе «bound to a different event loop».
    game._day_locks.clear()
    game._xp_locks.clear()
    # Троттлер отправки — тоже модульный замок. Он привязывается к loop только
    # при реальной конкуренции (два таска рассылки), поэтому раньше не мешал,
    # но фоновая выдача наград такую конкуренцию создаёт.
    monkeypatch.setattr(scheduler, "_send_lock", asyncio.Lock())
    monkeypatch.setattr(scheduler, "_reward_tasks", {})
    connection = await db.init_db()
    yield connection
    await db.close_db()


@pytest_asyncio.fixture
async def user(conn):
    """Зарегистрированный охотник (user_id=1)."""
    await db.create_user(1, "tester", "Тестер")
    return await db.get_user(1)


@pytest.fixture
def days_ago():
    """Дата N дней назад в формате YYYY-MM-DD (относительно «сегодня» бота)."""
    def _days_ago(n: int) -> str:
        today = game.datetime.now(config.TZ).date()
        return (today - timedelta(days=n)).strftime("%Y-%m-%d")
    return _days_ago


@pytest.fixture
def set_prev_day(conn, days_ago):
    """Перевести охотника в состояние «прошлый день закрыт N дней назад».

    Переносит все его квесты на ту дату и выставляет last_daily_date.
    `done` управляет тем, были ли квесты выполнены.
    """
    async def _set(n: int, *, done: bool, **fields):
        date = days_ago(n)
        await db.update_user(1, last_daily_date=date, **fields)
        await conn.execute(
            "UPDATE quests SET quest_date = ?, done = ? WHERE user_id = 1",
            (date, 1 if done else 0),
        )
        await conn.commit()
        return date
    return _set
