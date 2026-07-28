"""Достижения: коды, условия, проверка после событий."""
from collections.abc import Callable
from dataclasses import dataclass

from bot import db


@dataclass(frozen=True)
class Achievement:
    code: str
    title: str
    desc: str
    check: Callable  # (user) -> bool, по свежей строке users


ACHIEVEMENTS: list[Achievement] = [
    Achievement("first_blood", "Первая кровь", "Выполнить первый квест",
                lambda u: u["total_done"] >= 1),
    Achievement("quests_50", "Ветеран подземелий", "Выполнить 50 квестов",
                lambda u: u["total_done"] >= 50),
    Achievement("quests_200", "Машина Системы", "Выполнить 200 квестов",
                lambda u: u["total_done"] >= 200),
    Achievement("streak_3", "Разогрев", "Серия 3 дня",
                lambda u: u["best_streak"] >= 3),
    Achievement("streak_7", "Неделя без слабости", "Серия 7 дней",
                lambda u: u["best_streak"] >= 7),
    Achievement("streak_30", "Одержимый", "Серия 30 дней",
                lambda u: u["best_streak"] >= 30),
    Achievement("level_10", "Ранг D", "Достигнуть 10 уровня",
                lambda u: u["level"] >= 10),
    Achievement("level_20", "Ранг C", "Достигнуть 20 уровня",
                lambda u: u["level"] >= 20),
    Achievement("level_30", "Ранг B", "Достигнуть 30 уровня",
                lambda u: u["level"] >= 30),
    Achievement("level_45", "Ранг A", "Достигнуть 45 уровня",
                lambda u: u["level"] >= 45),
    Achievement("level_60", "Ранг S", "Достигнуть 60 уровня",
                lambda u: u["level"] >= 60),
    Achievement("first_report", "Голос охотника", "Отправить первый ИИ-отчёт",
                lambda u: u["total_reports"] >= 1),
    Achievement("reports_30", "Летописец", "Отправить 30 ИИ-отчётов",
                lambda u: u["total_reports"] >= 30),
    Achievement("first_ref", "Вербовщик", "Пригласить первого охотника",
                lambda u: u["ref_count"] >= 1),
    Achievement("refs_10", "Мастер Гильдии", "Пригласить 10 охотников",
                lambda u: u["ref_count"] >= 10),
    Achievement("death_1", "Воскресший", "Умереть и вернуться",
                lambda u: u["deaths"] >= 1),
]

BY_CODE = {a.code: a for a in ACHIEVEMENTS}


async def check_new(user) -> list[Achievement]:
    """Вернуть только что разблокированные ачивки для пользователя."""
    unlocked = await db.user_achievements(user["user_id"])
    fresh: list[Achievement] = []
    for ach in ACHIEVEMENTS:
        if ach.code in unlocked:
            continue
        try:
            if ach.check(user):
                if await db.unlock_achievement(user["user_id"], ach.code):
                    fresh.append(ach)
        except (KeyError, IndexError):
            continue
    return fresh
