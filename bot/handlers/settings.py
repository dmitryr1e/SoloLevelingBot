"""Хендлеры: /remind — время напоминания, /timezone — часовой пояс охотника."""
import re
from datetime import UTC, datetime, timedelta

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message

from bot import db, keyboards, texts, timeutil
from bot.handlers.helpers import load_user

router = Router()

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")

# Пояс можно менять не чаще раза в сутки. Смена вперёд немедленно открывает
# новый игровой день, поэтому без ограничения серию можно было бы накручивать,
# перепрыгивая по поясам. Остаточный риск (один «лишний» день при переезде)
# сознательно принят: он не отличим от честного перелёта.
TZ_CHANGE_COOLDOWN = timedelta(hours=24)

# Разрешённые значения приходят только из этого множества: callback_data
# подделывается элементарно, а произвольная строка ушла бы прямо в БД.
_ALLOWED = {tz for _, tz in timeutil.COMMON_ZONES}


@router.message(Command("remind"))
async def cmd_remind(message: Message, command: CommandObject) -> None:
    user = await load_user(message)
    if user is None:
        return
    arg = (command.args or "").strip()
    match = _TIME_RE.match(arg)
    if not match:
        await message.answer(texts.REMIND_USAGE)
        return
    hhmm = f"{int(match.group(1)):02d}:{match.group(2)}"
    await db.update_user(user["user_id"], reminder_time=hhmm)
    # Пояс показываем пользовательский: напоминание сработает по его часам.
    await message.answer(
        texts.REMIND_SET.format(time=hhmm, tz=timeutil.label_of(user))
    )


@router.message(Command("timezone"))
async def cmd_timezone(message: Message) -> None:
    user = await load_user(message)
    if user is None:
        return
    await message.answer(
        texts.TZ_PROMPT.format(
            current=timeutil.label_of(user),
            local=timeutil.now_for(user).strftime("%H:%M"),
        ),
        reply_markup=keyboards.timezone_menu(),
    )


@router.callback_query(F.data.startswith("tz:"))
async def cb_set_timezone(callback: CallbackQuery) -> None:
    tz_name = callback.data.split(":", 1)[1]
    if tz_name not in _ALLOWED:
        await callback.answer(texts.TZ_UNKNOWN, show_alert=True)
        return

    user = await db.get_user(callback.from_user.id)
    if user is None:
        await callback.answer(texts.TZ_NO_PROFILE, show_alert=True)
        return

    if timeutil.raw_tz(user) == tz_name:
        await callback.answer(texts.TZ_ALREADY)
        return

    # Кулдаун проверяется до записи. Пустое/битое значение трактуем как
    # «никогда не менял»: у охотников, заведённых до этой функции, поля нет.
    last_raw = ""
    try:
        last_raw = user["tz_changed_at"] or ""
    except (IndexError, KeyError, TypeError):
        last_raw = ""
    now = datetime.now(UTC)
    if last_raw:
        try:
            last = datetime.fromisoformat(last_raw)
            if last.tzinfo is None:
                last = last.replace(tzinfo=UTC)
            left = TZ_CHANGE_COOLDOWN - (now - last)
            if left > timedelta(0):
                hours = max(1, int(left.total_seconds() // 3600))
                await callback.answer(texts.TZ_COOLDOWN.format(hours=hours), show_alert=True)
                return
        except ValueError:
            pass  # битая метка — считаем, что смены не было

    if not await db.set_timezone(callback.from_user.id, tz_name, now.isoformat()):
        # Между чтением и записью пояс уже поменяли (двойное нажатие)
        await callback.answer(texts.TZ_ALREADY)
        return

    fresh = await db.get_user(callback.from_user.id)
    text = texts.TZ_SET.format(
        tz=timeutil.label_of(fresh),
        local=timeutil.now_for(fresh).strftime("%H:%M"),
    )
    try:
        await callback.message.edit_text(text, reply_markup=None)
    except Exception:
        await callback.message.answer(text)
    await callback.answer()
