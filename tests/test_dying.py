"""Состояние «при смерти»: HP на нуле не убивает сразу.

Смысл механики: при HP <= 0 охотник получает окно до конца дня, внутри
которого уровень ещё можно спасти — воскрешением за звёзды или левелапом.
Смерть наступает на СЛЕДУЮЩЕМ rollover, если HP так и осталось нулевым.

Все даты — ОТНОСИТЕЛЬНЫЕ (фикстуры `days_ago` / `set_prev_day` из conftest).
"""
from bot import config, db, game, render, texts

# ---------- вход в окно ----------

async def test_zero_hp_does_not_kill_immediately(user, set_prev_day):
    await game.ensure_today(user)
    await set_prev_day(1, done=False, hp=5, level=5, xp=30)

    events = await game.ensure_today(await db.get_user(1))

    assert events.dying, "охотник должен уйти «при смерти»"
    assert events.died is False, "смерть не должна наступать в тот же день"
    fresh = await db.get_user(1)
    assert fresh["hp"] == 0, "HP фиксируется на нуле, а не уходит в минус"
    assert fresh["level"] == 5, "уровень обязан сохраниться"
    assert fresh["xp"] == 30, "опыт текущего уровня обязан сохраниться"
    assert fresh["deaths"] == 0, "смерть ещё не засчитана"
    assert fresh["dying_until"] == game.today_str(), "окно действует до конца дня"


async def test_dying_renders_offer_not_death(user, set_prev_day):
    await game.ensure_today(user)
    await set_prev_day(1, done=False, hp=5, level=5)

    events = await game.ensure_today(await db.get_user(1))
    messages = render.render_day_events(events)

    offers = [m for m in messages if "КРИТИЧЕСКОЕ СОСТОЯНИЕ" in m]
    assert len(offers) == 1, "оффер воскрешения показывается ровно один раз"
    assert str(config.REVIVE_PRICE_STARS) in offers[0], "в оффере должна быть цена"
    assert not any("ФАТАЛЬНЫЙ ИСХОД" in m for m in messages), "смерти ещё не было"


async def test_is_dying_flag(user, set_prev_day):
    await game.ensure_today(user)
    assert game.is_dying(await db.get_user(1)) is False

    await set_prev_day(1, done=False, hp=5)
    await game.ensure_today(await db.get_user(1))
    assert game.is_dying(await db.get_user(1)) is True


async def test_is_dying_false_after_hp_restored(user, set_prev_day):
    """Окно ещё не закрылось, но HP уже поднято — охотник не «при смерти»."""
    await game.ensure_today(user)
    await set_prev_day(1, done=False, hp=5)
    await game.ensure_today(await db.get_user(1))

    await db.update_user(1, hp=100)

    assert game.is_dying(await db.get_user(1)) is False


async def test_repeated_call_same_day_keeps_window(user, set_prev_day):
    await game.ensure_today(user)
    await set_prev_day(1, done=False, hp=5, level=5)
    await game.ensure_today(await db.get_user(1))
    before = await db.get_user(1)

    again = await game.ensure_today(await db.get_user(1))

    assert again.new_day is False
    assert again.dying is False, "повторный вызов не должен дублировать оффер"
    after = await db.get_user(1)
    assert after["dying_until"] == before["dying_until"]
    assert after["level"] == 5
    assert after["deaths"] == 0


# ---------- закрытие окна ----------

async def test_window_expired_with_zero_hp_kills(user, set_prev_day):
    await game.ensure_today(user)
    await set_prev_day(1, done=False, hp=0, level=5, xp=30, dying_until="")
    # Окно было открыто вчера и к сегодняшнему дню истекло
    await db.update_user(1, dying_until=(await db.get_user(1))["last_daily_date"])

    events = await game.ensure_today(await db.get_user(1))

    assert events.died, "просроченное окно обязано привести к смерти"
    assert events.death_level == 4
    fresh = await db.get_user(1)
    assert fresh["level"] == 4, "уровень понижен ровно на один"
    assert fresh["xp"] == 0
    assert fresh["hp"] == int(fresh["max_hp"] * config.DEATH_HP_RESTORE_RATIO)
    assert fresh["deaths"] == 1, "ровно одна смерть, не больше"
    assert fresh["dying_until"] == "", "окно должно быть снято"


async def test_window_expired_with_hp_survives(user, set_prev_day, days_ago):
    """Воскрешение внутри окна сохраняет уровень."""
    await game.ensure_today(user)
    # streak=0: серия 3 дня дала бы бонус вехи и сбила проверку опыта
    await set_prev_day(1, done=True, hp=100, level=5, xp=30, streak=0)
    await db.update_user(1, dying_until=days_ago(1))

    events = await game.ensure_today(await db.get_user(1))

    assert events.dying_survived, "окно закрылось без смерти"
    assert events.died is False
    fresh = await db.get_user(1)
    assert fresh["level"] == 5, "уровень сохранён"
    assert fresh["xp"] == 30, "опыт сохранён"
    assert fresh["deaths"] == 0
    assert fresh["dying_until"] == ""
    messages = render.render_day_events(events)
    assert any(texts.DYING_SURVIVED.split("\n")[0] in m for m in messages)


async def test_levelup_inside_window_saves_level(user, set_prev_day, days_ago):
    """Левелап восстанавливает HP, поэтому охотник выкарабкивается сам."""
    await game.ensure_today(user)
    await set_prev_day(1, done=False, hp=5, level=5)
    await game.ensure_today(await db.get_user(1))
    assert (await db.get_user(1))["hp"] == 0

    await game.grant_xp(await db.get_user(1), 10_000, count_quest=False)
    assert (await db.get_user(1))["hp"] > 0, "левелап восстанавливает HP"

    # Следующий день: окно истекло, но HP уже не нулевое. Дату окна тоже
    # отматываем назад — в тесте день «сдвигается» вручную.
    level_before = (await db.get_user(1))["level"]
    await set_prev_day(1, done=True, dying_until=days_ago(1))
    events = await game.ensure_today(await db.get_user(1))

    assert events.died is False
    assert events.dying_survived
    fresh = await db.get_user(1)
    assert fresh["level"] == level_before, "уровень не потерян"
    assert fresh["deaths"] == 0


async def test_long_absence_counts_single_death(user, set_prev_day, days_ago):
    """Возврат через несколько дней даёт ровно одну смерть, не по одной за день."""
    await game.ensure_today(user)
    await set_prev_day(5, done=False, hp=0, level=5)
    await db.update_user(1, dying_until=days_ago(5))

    events = await game.ensure_today(await db.get_user(1))

    assert events.died
    fresh = await db.get_user(1)
    assert fresh["deaths"] == 1
    assert fresh["level"] == 4
    assert fresh["dying_until"] == ""


async def test_death_after_window_reopens_on_new_zero_hp(user, set_prev_day, days_ago):
    """После смерти HP восстановлено — новое окно не открывается сразу же."""
    await game.ensure_today(user)
    await set_prev_day(1, done=False, hp=0, level=5)
    await db.update_user(1, dying_until=days_ago(1))

    events = await game.ensure_today(await db.get_user(1))

    assert events.died
    assert events.dying is False, "воскресший после смерти не «при смерти»"
    assert (await db.get_user(1))["dying_until"] == ""
