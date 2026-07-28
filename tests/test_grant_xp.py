"""Атомарность начисления опыта (спринт А, п. 2-3).

Проверяем, что параллельные начисления не теряются: счётчики идут инкрементами,
а уровень и остаток XP пишутся через compare-and-set с повтором попытки.
"""
import asyncio

from bot import config, db, game

# ---------- инкрементальные счётчики ----------

async def test_increment_user_accumulates(user):
    await db.increment_user(1, weekly_xp=10, total_done=1)
    await db.increment_user(1, weekly_xp=5, total_done=1)

    row = await db.get_user(1)
    assert row["weekly_xp"] == 15
    assert row["total_done"] == 2


async def test_increment_user_ignores_zero_and_empty(user):
    before = await db.get_user(1)
    await db.increment_user(1)
    await db.increment_user(1, weekly_xp=0)

    after = await db.get_user(1)
    assert after["weekly_xp"] == before["weekly_xp"]


# ---------- compare-and-set ----------

async def test_cas_rejects_stale_expectation(user):
    stale = await db.get_user(1)
    await db.update_user(1, xp=999)

    applied = await db.compare_and_set_user(
        1,
        expect={"level": stale["level"], "xp": stale["xp"]},
        absolute={"xp": 42},
    )

    assert applied is False
    assert (await db.get_user(1))["xp"] == 999


async def test_cas_applies_on_fresh_expectation(user):
    fresh = await db.get_user(1)

    applied = await db.compare_and_set_user(
        1,
        expect={"level": fresh["level"], "xp": fresh["xp"]},
        absolute={"xp": 42},
        increments={"weekly_xp": 7},
    )

    assert applied is True
    row = await db.get_user(1)
    assert row["xp"] == 42
    assert row["weekly_xp"] == fresh["weekly_xp"] + 7


# ---------- grant_xp ----------

async def test_grant_xp_adds_to_counters(user):
    result = await game.grant_xp(user, 10)

    row = await db.get_user(1)
    assert result.amount == 10
    assert row["weekly_xp"] == 10
    assert row["weekly_done"] == 1
    assert row["total_done"] == 1


async def test_grant_xp_without_quest_does_not_bump_done(user):
    await game.grant_xp(user, 10, count_quest=False)

    row = await db.get_user(1)
    assert row["weekly_xp"] == 10
    assert row["weekly_done"] == 0
    assert row["total_done"] == 0


async def test_concurrent_grants_do_not_lose_xp(user):
    """Ключевой регресс: 10 параллельных начислений по 5 XP = ровно 50 XP.

    До фикса каждое начисление читало строку и писало абсолютное значение
    weekly_xp, поэтому большая часть начислений затиралась.
    """
    stale = await db.get_user(1)
    grants = 10
    amount = 5

    await asyncio.gather(*[game.grant_xp(stale, amount) for _ in range(grants)])

    row = await db.get_user(1)
    assert row["weekly_xp"] == grants * amount
    assert row["weekly_done"] == grants
    assert row["total_done"] == grants


async def test_concurrent_grants_keep_total_progress(user):
    """Суммарный прогресс (уровни + остаток XP) равен сумме начислений."""
    stale = await db.get_user(1)
    grants, amount = 8, 30

    await asyncio.gather(*[game.grant_xp(stale, amount) for _ in range(grants)])

    row = await db.get_user(1)
    spent = sum(config.xp_to_next(lvl) for lvl in range(1, row["level"]))
    assert spent + row["xp"] == grants * amount


async def test_grant_xp_uses_fresh_row_not_stale_argument(user):
    """Начисление опирается на актуальную строку, даже если передали устаревшую."""
    stale = await db.get_user(1)
    await db.update_user(1, xp=7)

    await game.grant_xp(stale, 10, count_quest=False)

    assert (await db.get_user(1))["xp"] == 17


async def test_level_up_restores_hp_and_grants_stat(user):
    await db.update_user(1, hp=20)
    stale = await db.get_user(1)
    total_stats_before = sum(stale[s] for s in config.STATS)

    result = await game.grant_xp(stale, config.xp_to_next(1), count_quest=False)

    row = await db.get_user(1)
    assert result.levels_gained
    assert row["level"] == 2
    assert row["hp"] == row["max_hp"]
    assert sum(row[s] for s in config.STATS) > total_stats_before


async def test_grant_xp_without_level_up_keeps_hp(user):
    await db.update_user(1, hp=20)
    stale = await db.get_user(1)

    result = await game.grant_xp(stale, 1, count_quest=False)

    assert not result.levels_gained
    assert (await db.get_user(1))["hp"] == 20


async def test_grant_xp_on_deleted_user_is_noop(user):
    stale = await db.get_user(1)
    await db.delete_user_data(1)

    result = await game.grant_xp(stale, 10)

    assert result.amount == 0
    assert await db.get_user(1) is None
