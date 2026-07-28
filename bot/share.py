"""Вирусный контур: реф-ссылка и готовые share-тексты.

Модуль намеренно чистый — только `config`/`texts`, без aiogram. Причина та же,
что у `bot/render.py`: ссылки и тексты должны проверяться тестами без бота, а
клавиатуру по ним собирает `bot/keyboards.py`.

Ссылка вербовки раньше собиралась строкой в четырёх местах (`handlers/social`,
`card`, `scheduler`, теперь ещё и подпись карточки). Любая правка формата
deep-link (`?start=ref<id>`) требовала синхронной правки всех копий, а
`handlers/common._parse_ref` разбирает именно этот префикс — рассинхрон дал бы
ссылки, по которым вербовка молча не засчитывается. Теперь формат живёт здесь.
"""
from urllib.parse import quote

from bot import config, texts

# Штатный шеринг Telegram: открывает выбор чата и вставляет текст + ссылку.
# Выбран вместо switch_inline_query, потому что не требует включённого
# inline-режима у бота и работает из любого чата, включая канал.
_TG_SHARE = "https://t.me/share/url"


def ref_link(user_id: int) -> str:
    """Личная ссылка вербовки. Формат разбирается в `handlers/common._parse_ref`."""
    return f"https://t.me/{config.BOT_USERNAME}?start=ref{user_id}"


def share_url(user_id: int, text: str) -> str:
    """URL для кнопки «Поделиться»: текст + личная реф-ссылка охотника.

    `quote` с пустым `safe` обязателен: в share-текстах есть `&`, `#` и
    переводы строк, а незакодированный `&` обрезал бы текст на первом же
    символе — Telegram принял бы остаток за свой параметр.
    """
    return (
        f"{_TG_SHARE}?url={quote(ref_link(user_id), safe='')}"
        f"&text={quote(text, safe='')}"
    )


def card_text(user) -> str:
    """Share-текст к карточке охотника."""
    return texts.SHARE_CARD.format(
        rank=config.rank_for_level(user["level"]),
        level=user["level"],
        streak=user["streak"],
    )


def milestone_text(streak: int) -> str:
    return texts.SHARE_MILESTONE.format(streak=streak)


def rank_text(rank: str) -> str:
    return texts.SHARE_RANK.format(rank=rank)
