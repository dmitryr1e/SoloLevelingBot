"""Апселл: клавиатуры-офферы и ключи, которые отдаёт рендер смены дня.

Проверяем не «красиво ли», а две вещи, которые ломаются молча:
1) callback_data кнопок совпадает с payload'ами товаров в handlers/premium —
   иначе кнопка есть, а инвойс не открывается;
2) оффер приходит именно в момент боли и не приходит тому, кому не нужен.
"""
from bot import config, game, keyboards, render
from bot.handlers import premium

# ---------- клавиатуры ----------

def test_upsell_without_keys_returns_none():
    """None вместо пустой клавиатуры: вызывающий код передаёт результат как есть."""
    assert keyboards.upsell() is None
    assert keyboards.upsell(None) is None


def test_upsell_builds_row_per_offer_with_price():
    kb = keyboards.upsell(config.UPSELL_REVIVE, config.UPSELL_FREEZE)

    assert kb is not None
    assert len(kb.inline_keyboard) == 2
    labels = [row[0].text for row in kb.inline_keyboard]
    assert f"{config.REVIVE_PRICE_STARS} ⭐" in labels[0]
    assert f"{config.FREEZE_PRICE_STARS} ⭐" in labels[1]


def test_upsell_ignores_unknown_keys():
    """Опечатка в ключе не должна ронять отправку сообщения."""
    assert keyboards.upsell("no-such-offer") is None
    kb = keyboards.upsell("no-such-offer", config.UPSELL_PREMIUM)
    assert kb is not None and len(kb.inline_keyboard) == 1


def test_every_upsell_callback_matches_a_real_product():
    """Главный регресс: кнопка без товара = «ничего не происходит» у охотника."""
    for key in (config.UPSELL_PREMIUM, config.UPSELL_REVIVE, config.UPSELL_FREEZE):
        kb = keyboards.upsell(key)
        payload = kb.inline_keyboard[0][0].callback_data.removeprefix("buy:")
        assert payload in premium._PRODUCTS, f"нет товара для оффера {key}"


# ---------- ключи офферов из рендера ----------

def test_dying_message_offers_revive():
    """«При смерти» — единственное окно, где воскрешение реально спасает уровень."""
    events = game.DayEvents(
        new_day=True, quests_issued=4, dying=True, level=7, hp=0, max_hp=100
    )

    offers = {m.upsell for m in render.render_day_messages(events)}

    assert config.UPSELL_REVIVE in offers


def test_lost_streak_offers_freeze_only_without_charges():
    def events(freezes: int) -> game.DayEvents:
        return game.DayEvents(
            new_day=True,
            quests_issued=4,
            skipped_days=2,
            streak_reset=True,
            damage=config.SKIPPED_DAY_DAMAGE * 2,
            freezes=freezes,
            hp=80,
            max_hp=100,
        )

    without = {m.upsell for m in render.render_day_messages(events(0))}
    assert config.UPSELL_FREEZE in without

    # С зарядом на руках предлагать покупку заморозки — издевательство
    with_charge = {m.upsell for m in render.render_day_messages(events(2))}
    assert config.UPSELL_FREEZE not in with_charge


def test_neutral_messages_carry_no_offer():
    """Успешный день не должен превращаться в рекламный блок."""
    events = game.DayEvents(new_day=True, quests_issued=4, hp=100, max_hp=100)

    assert [m.upsell for m in render.render_day_messages(events)] == [None]


def test_render_day_events_still_returns_plain_texts():
    """Старый API остался строковым — на него опирается существующий код."""
    events = game.DayEvents(
        new_day=True, quests_issued=4, dying=True, level=3, hp=0, max_hp=100
    )

    texts_only = render.render_day_events(events)

    assert all(isinstance(m, str) for m in texts_only)
    assert texts_only == [m.text for m in render.render_day_messages(events)]
