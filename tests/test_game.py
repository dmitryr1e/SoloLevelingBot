"""Игровая логика: смена дня, серия, заморозки, пропуски, смерть, врата.

Все даты — ОТНОСИТЕЛЬНЫЕ (фикстуры `days_ago` / `set_prev_day` из conftest).
Жёстко заданные даты запрещены: логика честного стрика считает разрыв
до сегодняшнего дня, и «2020-01-01 как вчера» превращается в ~2000 пропусков.
"""
import asyncio

from bot import config, db, game

# ---------- выдача квестов и идемпотентность дня ----------

async def test_first_day_issues_quests(user):
    events = await game.ensure_today(user)

    assert events.new_day
    assert events.quests_issued >= config.DAILY_QUEST_COUNT
    quests = await db.quests_for_date(1, game.today_str())
    assert len(quests) == events.quests_issued


async def test_second_call_same_day_is_noop(user):
    first = await game.ensure_today(user)
    before = await db.quests_for_date(1, game.today_str())

    second = await game.ensure_today(await db.get_user(1))

    assert not second.new_day
    assert second.quests_issued == 0
    after = await db.quests_for_date(1, game.today_str())
    assert len(after) == len(before) == first.quests_issued


async def test_concurrent_calls_open_day_once(user, set_prev_day):
    await game.ensure_today(user)
    await set_prev_day(1, done=True)

    fresh = await db.get_user(1)
    results = await asyncio.gather(*[game.ensure_today(fresh) for _ in range(5)])

    assert sum(1 for r in results if r.new_day) == 1


async def test_quest_cannot_be_completed_twice(user):
    await game.ensure_today(user)
    quest = (await db.quests_for_date(1, game.today_str()))[0]

    assert await db.mark_quest_done(quest["id"]) is True
    assert await db.mark_quest_done(quest["id"]) is False


# ---------- серия ----------

async def test_streak_grows_when_yesterday_completed(user, set_prev_day):
    await game.ensure_today(user)
    await set_prev_day(1, done=True, streak=1, hp=100)

    events = await game.ensure_today(await db.get_user(1))

    assert events.streak_up
    assert events.streak_reset is False
    assert (await db.get_user(1))["streak"] == 2


async def test_streak_milestone_grants_bonus(user, set_prev_day):
    await game.ensure_today(user)
    milestone_day = min(config.STREAK_MILESTONES)
    await set_prev_day(1, done=True, streak=milestone_day - 1, hp=100)

    events = await game.ensure_today(await db.get_user(1))

    assert events.milestone is not None
    day, bonus_xp, bonus_freezes = events.milestone
    assert day == milestone_day
    assert bonus_xp == config.STREAK_MILESTONES[milestone_day][0]
    assert events.milestone_result is not None  # XP реально начислен
    assert (await db.get_user(1))["streak_freezes"] >= bonus_freezes


async def test_missed_quests_reset_streak_and_damage_hp(user, set_prev_day):
    await game.ensure_today(user)
    await set_prev_day(1, done=False, streak=4, hp=100, streak_freezes=0)

    events = await game.ensure_today(await db.get_user(1))

    assert events.missed > 0
    assert events.damage == events.missed * config.HP_PENALTY_PER_MISS
    assert events.streak_reset
    fresh = await db.get_user(1)
    assert fresh["streak"] == 0
    assert fresh["hp"] == 100 - events.damage


async def test_freeze_protects_streak_and_hp(user, set_prev_day):
    await game.ensure_today(user)
    await set_prev_day(1, done=False, streak=3, hp=100, streak_freezes=1)

    events = await game.ensure_today(await db.get_user(1))

    assert events.streak_frozen
    assert events.damage == 0
    fresh = await db.get_user(1)
    assert fresh["streak"] == 3, "серия должна сохраниться"
    assert fresh["streak_freezes"] == 0, "заряд должен потратиться"
    assert fresh["hp"] == 100, "HP не должен пострадать"


# ---------- честный учёт отсутствия (регресс на «стрик через даунтайм») ----------

async def test_absence_resets_streak(user, set_prev_day):
    await game.ensure_today(user)
    await set_prev_day(4, done=True, streak=5, hp=100, streak_freezes=0)

    events = await game.ensure_today(await db.get_user(1))

    assert events.skipped_days == 3, "между last и сегодня 3 дня отсутствия"
    assert events.streak_reset
    assert (await db.get_user(1))["streak"] == 0


async def test_absence_covered_by_freezes(user, set_prev_day):
    await game.ensure_today(user)
    await set_prev_day(3, done=True, streak=5, hp=100, streak_freezes=5)

    events = await game.ensure_today(await db.get_user(1))

    assert events.skipped_days == 2
    assert events.streak_frozen
    assert events.streak_reset is False
    fresh = await db.get_user(1)
    assert fresh["streak"] == 6, "серия выросла за закрытый день и уцелела"
    assert fresh["streak_freezes"] == 3, "потрачено 2 заряда на 2 пропуска"
    assert fresh["hp"] == 100


async def test_absence_damage_is_capped(user, set_prev_day):
    """Длительный даунтайм бота не должен убивать всю базу."""
    await game.ensure_today(user)
    await set_prev_day(100, done=True, streak=5, hp=100, streak_freezes=0)

    events = await game.ensure_today(await db.get_user(1))

    assert events.skipped_days == 99
    cap = config.SKIPPED_DAMAGE_MAX_DAYS * config.SKIPPED_DAY_DAMAGE
    assert events.damage == cap, "урон ограничен SKIPPED_DAMAGE_MAX_DAYS"
    assert events.died is False


# ---------- премиум ----------

async def test_premium_expires_by_date(user):
    await db.update_user(1, is_premium=1, premium_until="2020-01-01 00:00:00")
    assert game.is_premium(await db.get_user(1)) is False

    await db.update_user(1, premium_until="2099-01-01 00:00:00")
    assert game.is_premium(await db.get_user(1)) is True
