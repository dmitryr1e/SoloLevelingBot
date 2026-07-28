"""Часовой пояс охотника: локальный «день», локальное время, валидация.

Единая точка правды о том, какой сейчас день у конкретного пользователя.
До появления этого модуля весь бот жил в одном поясе (`config.TZ`), из-за чего
у охотника во Владивостоке день закрывался в 19:00 по местному времени, а
напоминание на 20:00 приходило ночью (AUDIT 7.1).

Ключевое соглашение: пустая строка в `users.tz` = «пояс не выбран» и означает
`config.TZ`. Так мягкая миграция старых строк не требует бэкфилла, а поведение
для уже существующих охотников не меняется.
"""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from bot import config

log = logging.getLogger(__name__)

# Кэш разобранных поясов. ZoneInfo кэширует сам, но здесь кэшируются ещё и
# отказы: битое значение в БД не должно каждый раз бить по файлам tzdata.
_ZONE_CACHE: dict[str, ZoneInfo] = {}

# Пояса для клавиатуры выбора: подпись (со смещением от Москвы для наглядности)
# и имя зоны IANA. Покрывают Россию и основные страны СНГ — реальную аудиторию.
COMMON_ZONES: list[tuple[str, str]] = [
    ("Лондон (МСК−3)", "Europe/London"),
    ("Берлин / Варшава (МСК−2)", "Europe/Berlin"),
    ("Киев (МСК−1)", "Europe/Kyiv"),
    ("Калининград (МСК−1)", "Europe/Kaliningrad"),
    ("Москва / Минск (МСК)", "Europe/Moscow"),
    ("Самара / Тбилиси (МСК+1)", "Europe/Samara"),
    ("Дубай (МСК+1)", "Asia/Dubai"),
    ("Екатеринбург (МСК+2)", "Asia/Yekaterinburg"),
    ("Алматы / Ташкент (МСК+2)", "Asia/Almaty"),
    ("Омск (МСК+3)", "Asia/Omsk"),
    ("Красноярск (МСК+4)", "Asia/Krasnoyarsk"),
    ("Иркутск (МСК+5)", "Asia/Irkutsk"),
    ("Якутск (МСК+6)", "Asia/Yakutsk"),
    ("Владивосток (МСК+7)", "Asia/Vladivostok"),
    ("Магадан (МСК+8)", "Asia/Magadan"),
    ("Камчатка (МСК+9)", "Asia/Kamchatka"),
]

# Имя пояса -> подпись, для ответов пользователю
_LABELS = {tz: label for label, tz in COMMON_ZONES}


def zone(tz_name: str | None) -> ZoneInfo:
    """Разобрать имя пояса. Неизвестное/пустое значение -> пояс по умолчанию.

    Никогда не бросает: пояс мог быть удалён из tzdata при обновлении системы
    (например, переименование `Europe/Kiev` -> `Europe/Kyiv`), и падать из-за
    этого в расчёте дня — значит уронить всю игровую логику пользователя.
    """
    if not tz_name:
        return config.TZ
    cached = _ZONE_CACHE.get(tz_name)
    if cached is not None:
        return cached
    try:
        resolved = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        log.warning("Неизвестный часовой пояс %r, используем %s", tz_name, config.TZ_NAME)
        resolved = config.TZ
    _ZONE_CACHE[tz_name] = resolved
    return resolved


def is_valid(tz_name: str) -> bool:
    """Существует ли такой пояс в tzdata (для проверки пользовательского ввода)."""
    if not tz_name:
        return False
    try:
        ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return False
    return True


def raw_tz(user) -> str:
    """Значение `users.tz` из строки БД. Пустая строка, если пояс не выбран.

    Колонка добавляется мягкой миграцией, а в тестах и в старых кэшированных
    строках её может не быть вовсе — поэтому доступ защищён.
    """
    if user is None:
        return ""
    try:
        return user["tz"] or ""
    except (IndexError, KeyError, TypeError):
        return ""


def tz_name_of(user) -> str:
    """Имя пояса охотника — уже с подстановкой значения по умолчанию."""
    raw = raw_tz(user)
    return raw if raw and is_valid(raw) else config.TZ_NAME


def label_of(user) -> str:
    """Человеческая подпись пояса для сообщений."""
    name = tz_name_of(user)
    return _LABELS.get(name, name)


def now_for(user) -> datetime:
    """Текущее локальное время охотника."""
    return datetime.now(zone(raw_tz(user)))


def today_for(user) -> str:
    """Локальная дата охотника (YYYY-MM-DD) — граница игрового дня."""
    return now_for(user).strftime("%Y-%m-%d")


def now_in(tz_name: str | None) -> datetime:
    """Текущее время в конкретном поясе (для группировки в фоновых задачах)."""
    return datetime.now(zone(tz_name))


def today_in(tz_name: str | None) -> str:
    """Локальная дата в конкретном поясе."""
    return now_in(tz_name).strftime("%Y-%m-%d")


def local_date_of(utc_str: str, tz_name: str | None) -> str:
    """Локальная дата (YYYY-MM-DD) момента, хранящегося в БД как UTC-строка.

    `users.created_at` пишется SQLite-функцией `datetime('now')` — наивная
    строка в UTC. Нужна, чтобы посчитать «день N с регистрации» в поясе
    охотника, а не в UTC: иначе граница онбординг-шага разошлась бы с
    границей игрового дня (см. today_for/today_in), как раньше было с
    дедлайном серии (AUDIT 7.1).

    Пустая строка на пустом/битом значении — вызывающий обязан пропустить
    такую строку, а не трактовать её как «сегодня».
    """
    if not utc_str:
        return ""
    try:
        dt = datetime.strptime(utc_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo("UTC"))
    except ValueError:
        return ""
    return dt.astimezone(zone(tz_name)).strftime("%Y-%m-%d")
