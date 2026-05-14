"""Глобальна навігація FitTrackBot."""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.utils.keyboards import main_menu_keyboard

router = Router()


@router.message(Command("menu"))
async def show_main_menu_command(message: Message, state: FSMContext) -> None:
    """Повертає користувача до головного меню з будь-якого FSM-стану."""
    await state.clear()
    await message.answer(
        "🏠 Головне меню:",
        reply_markup=main_menu_keyboard(),
    )


@router.message(F.text.in_({"🏠 Menu", "Menu", "🏠 Меню", "Меню"}))
async def show_main_menu_button(message: Message, state: FSMContext) -> None:
    """Повертає користувача до головного меню через текстову кнопку меню."""
    await state.clear()
    await message.answer(
        "🏠 Головне меню:",
        reply_markup=main_menu_keyboard(),
    )