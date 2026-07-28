"""Хендлер: отписка от онбординг-цепочки (bot/scheduler.onboarding_chain)."""
from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot import config, db, texts

router = Router()


@router.callback_query(F.data == "onb:stop")
async def cb_stop_onboarding(callback: CallbackQuery) -> None:
    # Без проверки user is None: отписаться может и охотник, чья запись
    # успела исчезнуть (/delete_me между отправкой шага и нажатием кнопки).
    # update_user на несуществующий user_id — no-op, а не ошибка.
    await db.update_user(callback.from_user.id, onboarding_day=config.ONBOARDING_STOP)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:  # noqa: BLE001
        pass
    # show_alert=True рендерится Telegram как обычный текст без HTML —
    # ONBOARDING_STOPPED поэтому специально без тегов.
    await callback.answer(texts.ONBOARDING_STOPPED, show_alert=True)
