"""Хендлеры прав на данные: /delete_me (право на забвение) и /privacy."""
import logging
import time

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot import config, db, texts
from bot.handlers.helpers import load_user

router = Router()
log = logging.getLogger(__name__)

# user_id -> момент запроса удаления. Подтверждение живёт CONFIRM_TTL секунд.
_pending_deletes: dict[int, float] = {}
CONFIRM_TTL = 300  # 5 минут


def _prune_pending(now: float) -> None:
    """Убрать просроченные запросы, чтобы словарь не рос бесконечно."""
    for uid in [u for u, ts in _pending_deletes.items() if now - ts > CONFIRM_TTL]:
        _pending_deletes.pop(uid, None)


def _confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Отмена — я остаюсь", callback_data="del:no")],
            [InlineKeyboardButton(text="Стереть меня навсегда", callback_data="del:yes")],
        ]
    )


@router.message(Command("privacy"))
async def cmd_privacy(message: Message) -> None:
    """Короткая справка о данных со ссылками на полные документы."""
    await message.answer(
        f"<b>{texts.SYS} // ДАННЫЕ ОХОТНИКА</b>\n\n"
        "Система хранит: Telegram ID, имя, username, игровой прогресс, "
        "тексты твоих отчётов и историю покупок в Stars.\n"
        "Тексты отчётов оценивает внешний модуль Google Gemini API.\n\n"
        "Удалить всё: /delete_me\n"
        "Скрыться из рейтинга: /hideme\n\n"
        f'<a href="{config.PRIVACY_URL}">Политика конфиденциальности</a> · '
        f'<a href="{config.TERMS_URL}">Условия использования</a>',
        disable_web_page_preview=True,
    )


@router.message(Command("delete_me"))
async def cmd_delete_me(message: Message) -> None:
    user = await load_user(message)
    if user is None:
        return
    now = time.monotonic()
    _prune_pending(now)
    _pending_deletes[message.from_user.id] = now
    await message.answer(
        texts.DELETE_ME_CONFIRM.format(
            level=user["level"],
            rank=config.rank_for_level(user["level"]),
            streak=user["streak"],
        ),
        reply_markup=_confirm_kb(),
    )


@router.callback_query(F.data == "del:no")
async def cb_delete_cancel(callback: CallbackQuery) -> None:
    _pending_deletes.pop(callback.from_user.id, None)
    await callback.message.edit_text(texts.DELETE_ME_CANCELLED)
    await callback.answer()


@router.callback_query(F.data == "del:yes")
async def cb_delete_confirm(callback: CallbackQuery) -> None:
    requested_at = _pending_deletes.pop(callback.from_user.id, None)
    if requested_at is None or time.monotonic() - requested_at > CONFIRM_TTL:
        await callback.message.edit_text(texts.DELETE_ME_EXPIRED)
        await callback.answer()
        return

    await db.delete_user_data(callback.from_user.id)
    log.info("Данные пользователя %s удалены по запросу", callback.from_user.id)
    await callback.message.edit_text(texts.DELETE_ME_DONE)
    await callback.answer("Стёрто.")
