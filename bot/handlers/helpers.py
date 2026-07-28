"""Общие помощники для хендлеров."""
from aiogram.types import Message

from bot import achievements, db, game, keyboards, render, texts


def markup_for(msg: render.Msg, user_id: int):
    """Разметка под сообщение рендера: апселл-оффер и/или кнопка «Поделиться».

    user_id обязателен: share-ссылка персональная (реф-параметр), и без него
    охотник поделился бы чужой вербовкой.
    """
    return keyboards.message_markup(
        upsell_key=msg.upsell,
        share_for=(user_id, msg.share) if msg.share else None,
    )


async def load_user(message: Message):
    """Вернуть пользователя или отправить приглашение к /start."""
    user = await db.get_user(message.from_user.id)
    if user is None:
        await message.answer(texts.NO_CHARACTER)
        return None
    return user


async def process_day_events(message: Message, user) -> bool:
    """Обработать смену дня и отправить системные сообщения.

    Возвращает True, если наступил новый день (данные пользователя устарели).
    """
    events = await game.ensure_today(user)
    if not events.new_day:
        return False

    # Единый рендер (bot/render.py) — тот же, что использует планировщик.
    # К части сообщений (сгоревшая серия, смерть, «при смерти») рендер отдаёт
    # ключ апселла — кнопка покупки приходит прямо в момент боли; к вехе серии
    # и ранг-апу — share-текст.
    for msg in render.render_day_messages(events):
        await message.answer(msg.text, reply_markup=markup_for(msg, user["user_id"]))

    # Побочные эффекты бонуса вехи (босс, достижения) — уже после текстов
    if events.milestone_result is not None:
        await notify_side_effects(message, events.milestone_result, user["user_id"])
    return True


async def notify_xp_events(message: Message, result: game.XpResult, user_id: int | None = None) -> None:
    """Сообщения о левелапах, рангах, убийстве босса и новых достижениях.

    user_id указывать явно, если message пришёл из callback (там from_user — бот).
    """
    uid = user_id if user_id is not None else message.from_user.id
    for msg in render.render_xp_messages(result):
        await message.answer(msg.text, reply_markup=markup_for(msg, uid))
    await notify_side_effects(message, result, user_id)


async def notify_side_effects(
    message: Message, result: game.XpResult, user_id: int | None = None
) -> None:
    """Убийство босса и новые достижения — требуют запросов в БД."""
    uid = user_id if user_id is not None else message.from_user.id
    if result.boss_killed:
        from bot import boss as boss_mod
        from bot import scheduler
        b = await boss_mod.get_or_create_boss()
        await message.answer(texts.BOSS_FINAL_BLOW.format(name=b["name"]))
        # Награды раздаём сразу, но в фоне: рассылка по всем участникам рейда
        # идёт с троттлингом (~20 msg/sec) и добивший ждал бы её в диалоге.
        # Воскресный distribute_boss_rewards остаётся страховкой и выйдет
        # молча — право на выдачу занимается атомарно в БД.
        if message.bot is not None:
            scheduler.spawn_boss_rewards(message.bot)
    await notify_achievements(message, uid)


async def notify_achievements(message: Message, user_id: int) -> None:
    """Проверить и объявить новые достижения."""
    user = await db.get_user(user_id)
    if user is None:
        return
    for ach in await achievements.check_new(user):
        await message.answer(
            texts.ACHIEVEMENT_UNLOCKED.format(title=ach.title, desc=ach.desc)
        )
