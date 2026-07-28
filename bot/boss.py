"""Босс недели: общий рейд-босс, урон которому наносится полученным XP."""
from datetime import datetime

from bot import config, db

BOSS_NAMES = [
    "Игрис, Рыцарь Крови",
    "Барука, Король Ледяных Клыков",
    "Каргалган, Вождь Гоблинов",
    "Метус, Страж Врат",
    "Танатос, Пожиратель Теней",
    "Вулкан, Демон Пламени",
    "Керберос, Хранитель Бездны",
    "Архилич Некрон",
]


def week_key(dt: datetime | None = None) -> str:
    dt = dt or datetime.now(config.TZ)
    iso = dt.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


async def get_or_create_boss():
    """Босс текущей недели; HP масштабируется от числа охотников."""
    key = week_key()
    boss = await db.get_boss(key)
    if boss is not None:
        return boss
    hunters = len(await db.all_users())
    max_hp = config.BOSS_BASE_HP + hunters * config.BOSS_HP_PER_HUNTER
    # Имя детерминировано от недели, чтобы не зависеть от гонок INSERT OR IGNORE
    name = BOSS_NAMES[sum(map(ord, key)) % len(BOSS_NAMES)]
    return await db.create_boss(key, name, max_hp)


async def deal_damage(user_id: int, xp_amount: int) -> tuple[int, bool]:
    """Урон боссу = полученный XP. Возвращает (остаток HP, добит ли этим ударом)."""
    boss = await get_or_create_boss()
    if boss["defeated"]:
        return 0, False
    hp_left = await db.damage_boss(boss["id"], user_id, xp_amount)
    return hp_left, hp_left <= 0


def bar(hp: int, max_hp: int, width: int = 14) -> str:
    filled = max(0, round(width * hp / max_hp))
    return "█" * filled + "░" * (width - filled)
