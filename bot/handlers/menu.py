"""Хендлер кнопок постоянного меню: переадресация на командные хендлеры.

Роутер регистрируется ПЕРВЫМ, чтобы кнопки меню работали даже внутри
FSM-состояний (например, прерывали протокол отчёта).
"""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot import keyboards
from bot.handlers import boss as boss_h
from bot.handlers import common as common_h
from bot.handlers import quests as quests_h
from bot.handlers import report as report_h
from bot.handlers import social as social_h

router = Router()


@router.message(F.text == keyboards.BTN_QUESTS)
async def btn_quests(message: Message, state: FSMContext) -> None:
    await state.clear()
    await quests_h.cmd_quests(message)


@router.message(F.text == keyboards.BTN_REPORT)
async def btn_report(message: Message, state: FSMContext) -> None:
    await state.clear()
    await report_h.cmd_report(message, state)


@router.message(F.text == keyboards.BTN_PROFILE)
async def btn_profile(message: Message, state: FSMContext) -> None:
    await state.clear()
    await common_h.cmd_profile(message)


@router.message(F.text == keyboards.BTN_BOSS)
async def btn_boss(message: Message, state: FSMContext) -> None:
    await state.clear()
    await boss_h.cmd_boss(message)


@router.message(F.text == keyboards.BTN_RATING)
async def btn_rating(message: Message, state: FSMContext) -> None:
    await state.clear()
    await social_h.cmd_rating(message)


@router.message(F.text == keyboards.BTN_MORE)
async def btn_more(message: Message, state: FSMContext) -> None:
    await state.clear()
    await common_h.cmd_help(message)
