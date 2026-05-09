"""
Обробник нагадувань.
Реалізує ФВ 5.2.1.
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from src.database.connection import db_manager
from src.services.goals_service import ReminderService
from src.utils.keyboards import confirm_keyboard, main_menu_keyboard

logger = logging.getLogger(__name__)
router = Router()

DAYS_UA = {
    "Пн": 1, "Вт": 2, "Ср": 3, "Чт": 4, "Пт": 5, "Сб": 6, "Нд": 7
}
REMINDER_TYPES = {
    "🏋️ Тренування": "workout",
    "🥗 Харчування": "nutrition",
    "🔔 Всі": "all",
}


class ReminderStates(StatesGroup):
    waiting_type = State()
    waiting_days = State()
    waiting_time = State()
    confirming = State()


def reminder_type_keyboard():
    builder = ReplyKeyboardBuilder()
    for label in REMINDER_TYPES:
        builder.button(text=label)
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def days_keyboard():
    builder = ReplyKeyboardBuilder()
    for day in DAYS_UA:
        builder.button(text=day)
    builder.button(text="✅ Готово")
    builder.adjust(4)
    return builder.as_markup(resize_keyboard=True)


@router.callback_query(F.data == "profile:reminders")
async def show_reminders_menu(callback: CallbackQuery) -> None:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Нове нагадування", callback_data="reminder:new")
    builder.button(text="📋 Мої нагадування", callback_data="reminder:list")
    builder.button(text="🚫 Вимкнути тренування", callback_data="reminder:off:workout")
    builder.button(text="🚫 Вимкнути харчування", callback_data="reminder:off:nutrition")
    builder.button(text="🚫 Вимкнути всі", callback_data="reminder:off:all")
    builder.adjust(1)
    await callback.message.answer("🔔 Управління нагадуваннями:", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "reminder:new")
async def start_new_reminder(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.answer(
        "Оберіть тип нагадування:",
        reply_markup=reminder_type_keyboard(),
    )
    await state.set_state(ReminderStates.waiting_type)
    await callback.answer()


@router.message(ReminderStates.waiting_type)
async def handle_reminder_type(message: Message, state: FSMContext) -> None:
    rtype = REMINDER_TYPES.get(message.text)
    if not rtype:
        await message.answer("❌ Оберіть тип з кнопок:", reply_markup=reminder_type_keyboard())
        return
    await state.update_data(reminder_type=rtype, selected_days=[])
    await message.answer(
        "Оберіть дні тижня для нагадування.\n"
        "Натискайте кнопки днів, потім <b>✅ Готово</b>:",
        parse_mode="HTML",
        reply_markup=days_keyboard(),
    )
    await state.set_state(ReminderStates.waiting_days)


@router.message(ReminderStates.waiting_days)
async def handle_days_selection(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    selected = data.get("selected_days", [])

    if message.text == "✅ Готово":
        if not selected:
            await message.answer("❌ Оберіть хоча б один день тижня!")
            return
        await message.answer(
            "⏰ Введіть час нагадування у форматі ГГ:ХХ\n<i>Наприклад: 17:00</i>",
            parse_mode="HTML",
        )
        await state.set_state(ReminderStates.waiting_time)
        return

    day_num = DAYS_UA.get(message.text)
    if day_num is None:
        await message.answer("❌ Натисніть кнопку дня або «✅ Готово».")
        return

    if day_num in selected:
        selected.remove(day_num)
        await message.answer(f"❌ {message.text} прибрано.")
    else:
        selected.append(day_num)
        await message.answer(f"✅ {message.text} додано.")
    await state.update_data(selected_days=selected)


@router.message(ReminderStates.waiting_time)
async def handle_reminder_time(message: Message, state: FSMContext) -> None:
    time_str = message.text.strip()
    # Валідація формату ГГ:ХХ
    parts = time_str.split(":")
    if len(parts) != 2:
        await message.answer(
            "❌ Невірний формат. Введіть час у форматі ГГ:ХХ\n<i>Приклад: 17:00</i>",
            parse_mode="HTML",
        )
        return
    try:
        h, m = int(parts[0]), int(parts[1])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError
    except ValueError:
        await message.answer(
            "❌ Некоректний час. Години: 0–23, хвилини: 0–59.\n<i>Приклад: 17:00</i>",
            parse_mode="HTML",
        )
        return

    await state.update_data(remind_time=f"{h:02d}:{m:02d}")
    data = await state.get_data()
    days_names = [k for k, v in DAYS_UA.items() if v in data["selected_days"]]
    type_name = {v: k for k, v in REMINDER_TYPES.items()}.get(data["reminder_type"], "")
    await message.answer(
        f"Зберегти нагадування?\n\n"
        f"Тип: <b>{type_name}</b>\n"
        f"Дні: <b>{', '.join(days_names)}</b>\n"
        f"Час: <b>{data['remind_time']}</b>",
        parse_mode="HTML",
        reply_markup=confirm_keyboard(),
    )
    await state.set_state(ReminderStates.confirming)


@router.message(ReminderStates.confirming, F.text == "✅ Так")
async def confirm_reminder(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    async with db_manager.session_factory() as session:
        service = ReminderService(session)
        reminder, error = await service.set_reminder(
            user_id=message.from_user.id,
            reminder_type=data["reminder_type"],
            days_of_week=data["selected_days"],
            remind_time=data["remind_time"],
        )
    if error:
        await message.answer(f"❌ {error}", reply_markup=main_menu_keyboard())
    else:
        await message.answer(
            f"✅ Нагадування встановлено о <b>{data['remind_time']}</b>!",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(),
        )
    await state.clear()


@router.message(ReminderStates.confirming, F.text == "❌ Ні")
async def cancel_reminder(message: Message, state: FSMContext) -> None:
    await message.answer("Скасовано.", reply_markup=main_menu_keyboard())
    await state.clear()


@router.callback_query(F.data.startswith("reminder:off:"))
async def disable_reminder(callback: CallbackQuery) -> None:
    rtype = callback.data.split(":")[2]
    async with db_manager.session_factory() as session:
        service = ReminderService(session)
        if rtype == "all":
            await service.disable_all(callback.from_user.id)
            await callback.message.answer("✅ Всі нагадування вимкнено.")
        else:
            await service.disable_by_type(callback.from_user.id, rtype)
            type_name = {v: k for k, v in REMINDER_TYPES.items()}.get(rtype, rtype)
            await callback.message.answer(f"✅ Нагадування «{type_name}» вимкнено.")
    await callback.answer()


@router.callback_query(F.data == "reminder:list")
async def list_reminders(callback: CallbackQuery) -> None:
    async with db_manager.session_factory() as session:
        service = ReminderService(session)
        reminders = await service.get_reminders(callback.from_user.id)
    if not reminders:
        await callback.message.answer("У вас немає активних нагадувань.")
        await callback.answer()
        return
    lines = ["🔔 <b>Ваші нагадування:</b>\n"]
    day_names = {v: k for k, v in DAYS_UA.items()}
    for r in reminders:
        days = ", ".join(
            day_names.get(int(d), d) for d in r.days_of_week.split(",")
        )
        type_name = {v: k for k, v in REMINDER_TYPES.items()}.get(r.reminder_type, r.reminder_type)
        lines.append(f"• {type_name} — {days} о {r.remind_time}")
    await callback.message.answer("\n".join(lines), parse_mode="HTML")
    await callback.answer()
