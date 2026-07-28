"""Хендлер: /card — генерация карточки охотника."""
import asyncio

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, Message

from bot import config, db, game, keyboards, share, texts
from bot.card import render_card
from bot.handlers.helpers import load_user, process_day_events

router = Router()


@router.message(Command("card"))
async def cmd_card(message: Message) -> None:
    user = await load_user(message)
    if user is None:
        return
    if await process_day_events(message, user):
        user = await db.get_user(message.from_user.id)

    await message.answer(texts.CARD_GENERATING)
    premium = game.is_premium(user)
    png = await asyncio.to_thread(render_card, user, premium, premium)
    # Реф-ссылка идёт текстом в подписи, а не только QR-кодом: пересланную
    # карточку читают с телефона, и сканировать QR с того же экрана нечем.
    caption = "<b>{sys}</b>\n\n{body}".format(
        sys=texts.SYS,
        body=texts.SHARE_CAPTION.format(
            bonus=config.REF_BONUS_XP, link=share.ref_link(user["user_id"])
        ),
    )
    await message.answer_photo(
        BufferedInputFile(png, filename="hunter_card.png"),
        caption=caption,
        reply_markup=keyboards.share_kb(user["user_id"], share.card_text(user)),
    )
