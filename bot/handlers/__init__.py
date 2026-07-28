from aiogram import Router

from bot.handlers import (
    admin,
    boss,
    card,
    common,
    custom,
    menu,
    onboarding,
    premium,
    privacy,
    quests,
    report,
    settings,
    social,
)


def setup_routers() -> Router:
    root = Router()
    root.include_router(admin.router)
    root.include_router(menu.router)  # кнопки меню: раньше FSM-хендлеров
    root.include_router(common.router)
    root.include_router(quests.router)
    root.include_router(report.router)
    root.include_router(boss.router)
    root.include_router(social.router)
    root.include_router(custom.router)
    root.include_router(card.router)
    root.include_router(premium.router)
    root.include_router(privacy.router)
    root.include_router(settings.router)
    root.include_router(onboarding.router)
    return root
