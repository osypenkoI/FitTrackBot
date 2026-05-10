"""
Обробник профілю та авторизації.
Реалізує ФВ 1.1.1–1.1.4, ФВ 1.2.1–1.2.2.
Всі поля введення валідуються з зрозумілими повідомленнями.
"""

import logging
from aiogram import Router, F
from aiogram.types import (
    Message, Contact, CallbackQuery,
    ReplyKeyboardMarkup, KeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from src.database.connection import db_manager
from src.services.profile_service import ProfileService
from src.utils.keyboards import (
    share_phone_keyboard, main_menu_keyboard,
    confirm_keyboard, menu_button,
    registration_confirm_keyboard,
)
from src.utils.formatters import format_profile

logger = logging.getLogger(__name__)
router = Router()


class RegistrationStates(StatesGroup):
    waiting_phone = State()
    waiting_name = State()
    waiting_age = State()
    waiting_weight = State()
    waiting_height = State()
    waiting_gender = State()
    waiting_activity = State()
    waiting_goal = State()
    confirming = State()


class EditProfileStates(StatesGroup):
    waiting_field = State()
    waiting_value = State()
    confirming = State()


def gender_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text="👨 Чоловіча")
    builder.button(text="👩 Жіноча")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def activity_level_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text="🐢 Низький")
    builder.button(text="🚶 Середній")
    builder.button(text="🏃 Високий")
    builder.button(text="⚡ Дуже високий")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def goal_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text="⬇️ Схуднення")
    builder.button(text="💪 Набір маси")
    builder.button(text="⚖️ Підтримка форми")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


GENDER_MAP = {"👨 Чоловіча": "male", "👩 Жіноча": "female"}
ACTIVITY_MAP = {
    "🐢 Низький": "low",
    "🚶 Середній": "medium",
    "🏃 Високий": "high",
    "⚡ Дуже високий": "very_high",
}
GOAL_MAP = {
    "⬇️ Схуднення": "weight_loss",
    "💪 Набір маси": "muscle_gain",
    "⚖️ Підтримка форми": "maintain",
}


@router.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    async with db_manager.session_factory() as session:
        service = ProfileService(session)
        user = await service.get_user_by_telegram_id(message.from_user.id)
    if user:
        await message.answer(
            "З поверненням! Поділіться номером для авторизації.",
            reply_markup=share_phone_keyboard(),
        )
    else:
        await message.answer(
            "👋 Вітаю! Я <b>FitTrackBot</b>.\n\n"
            "Поділіться номером телефону для початку реєстрації.",
            reply_markup=share_phone_keyboard(),
            parse_mode="HTML",
        )
        await state.set_state(RegistrationStates.waiting_phone)


@router.message(F.contact)
async def handle_contact(message: Message, state: FSMContext) -> None:
    contact: Contact = message.contact
    current_state = await state.get_state()
    async with db_manager.session_factory() as session:
        service = ProfileService(session)
        if current_state == RegistrationStates.waiting_phone:
            await state.update_data(
                phone_number=contact.phone_number,
                telegram_id=message.from_user.id,
                username=message.from_user.first_name or message.from_user.username,
            )
            await message.answer(
                "📝 Введіть ваше ім'я (2–50 символів):",
                reply_markup=menu_button(),
            )
            await state.set_state(RegistrationStates.waiting_name)
        else:
            user = await service.authorize_user(contact.phone_number)
            if user:
                await message.answer(
                    f"✅ <b>Вітаємо, {user.username or 'друже'}! З поверненням!</b>",
                    parse_mode="HTML",
                    reply_markup=main_menu_keyboard(),
                )
            else:
                await message.answer(
                    "❌ Вас не знайдено. Введіть /start для реєстрації."
                )


@router.message(RegistrationStates.waiting_name)
async def handle_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("❌ Ім'я занадто коротке (мінімум 2 символи). Спробуйте ще раз:")
        return
    if len(name) > 50:
        await message.answer("❌ Ім'я занадто довге (максимум 50 символів). Спробуйте ще раз:")
        return
    if any(ch.isdigit() for ch in name):
        await message.answer("❌ Ім'я не може містити цифри. Введіть ваше ім'я:")
        return
    await state.update_data(username=name)
    await message.answer(
        "🎂 Введіть ваш вік (від 5 до 120 років):\n<i>Приклад: 22</i>",
        parse_mode="HTML",
    )
    await state.set_state(RegistrationStates.waiting_age)


@router.message(RegistrationStates.waiting_age)
async def handle_age(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if not text.isdigit():
        await message.answer(
            "❌ Вік має бути цілим числом без букв та знаків.\n"
            "<i>Приклад: 22</i>\nСпробуйте ще раз:",
            parse_mode="HTML",
        )
        return
    age = int(text)
    if age < 5:
        await message.answer("❌ Вік не може бути меншим за 5 років. Введіть коректний вік:")
        return
    if age > 120:
        await message.answer("❌ Вік не може перевищувати 120 років. Введіть коректний вік:")
        return
    await state.update_data(age=age)
    await message.answer(
        "⚖️ Введіть вашу вагу в кілограмах (від 20 до 500):\n<i>Приклад: 65.5</i>",
        parse_mode="HTML",
    )
    await state.set_state(RegistrationStates.waiting_weight)


@router.message(RegistrationStates.waiting_weight)
async def handle_weight(message: Message, state: FSMContext) -> None:
    text = message.text.strip().replace(",", ".")
    try:
        weight = float(text)
    except ValueError:
        await message.answer(
            "❌ Вага має бути числом.\n<i>Приклад: 65.5</i>\nСпробуйте ще раз:",
            parse_mode="HTML",
        )
        return
    if weight < 10:
        await message.answer("❌ Вага не може бути меншою за 10 кг:")
        return
    if weight > 500:
        await message.answer("❌ Вага не може перевищувати 500 кг:")
        return
    await state.update_data(weight=round(weight, 1))
    await message.answer(
        "📏 Введіть ваш зріст у сантиметрах (від 50 до 300):\n<i>Приклад: 165</i>",
        parse_mode="HTML",
    )
    await state.set_state(RegistrationStates.waiting_height)


@router.message(RegistrationStates.waiting_height)
async def handle_height(message: Message, state: FSMContext) -> None:
    text = message.text.strip().replace(",", ".")
    try:
        height = float(text)
    except ValueError:
        await message.answer(
            "❌ Зріст має бути числом.\n<i>Приклад: 165</i>\nСпробуйте ще раз:",
            parse_mode="HTML",
        )
        return
    if height < 50:
        await message.answer("❌ Зріст не може бути меншим за 50 см:")
        return
    if height > 300:
        await message.answer("❌ Зріст не може перевищувати 300 см:")
        return
    await state.update_data(height=round(height, 1))
    await message.answer("🚻 Оберіть вашу стать:", reply_markup=gender_keyboard())
    await state.set_state(RegistrationStates.waiting_gender)


@router.message(RegistrationStates.waiting_gender)
async def handle_gender(message: Message, state: FSMContext) -> None:
    gender = GENDER_MAP.get(message.text)
    if not gender:
        await message.answer("❌ Натисніть одну з кнопок нижче:", reply_markup=gender_keyboard())
        return
    await state.update_data(gender=gender)
    await message.answer("🏋️ Оберіть рівень фізичної активності:", reply_markup=activity_level_keyboard())
    await state.set_state(RegistrationStates.waiting_activity)


@router.message(RegistrationStates.waiting_activity)
async def handle_activity(message: Message, state: FSMContext) -> None:
    level = ACTIVITY_MAP.get(message.text)
    if not level:
        await message.answer("❌ Оберіть рівень з кнопок:", reply_markup=activity_level_keyboard())
        return
    await state.update_data(activity_level=level)
    await message.answer("🎯 Оберіть ціль тренувань:", reply_markup=goal_keyboard())
    await state.set_state(RegistrationStates.waiting_goal)


@router.message(RegistrationStates.waiting_goal)
async def handle_goal(message: Message, state: FSMContext) -> None:
    goal = GOAL_MAP.get(message.text)
    if not goal:
        await message.answer("❌ Оберіть ціль з кнопок:", reply_markup=goal_keyboard())
        return
    await state.update_data(target_goal=goal)
    data = await state.get_data()
    activity_label = {v: k for k, v in ACTIVITY_MAP.items()}.get(data["activity_level"], "")
    goal_label = {v: k for k, v in GOAL_MAP.items()}.get(data["target_goal"], "")
    summary = (
        f"📋 <b>Перевірте ваші дані:</b>\n\n"
        f"Ім'я: {data.get('username')}\n"
        f"Вік: {data.get('age')} р.\n"
        f"Вага: {data.get('weight')} кг\n"
        f"Зріст: {data.get('height')} см\n"
        f"Стать: {'Чоловіча' if data.get('gender') == 'male' else 'Жіноча'}\n"
        f"Рівень активності: {activity_label}\n"
        f"Ціль: {goal_label}\n\n"
        f"Зберегти профіль?"
    )
    await message.answer(
        summary,
        parse_mode="HTML",
        reply_markup=registration_confirm_keyboard(),
    )
    await state.set_state(RegistrationStates.confirming)


@router.message(RegistrationStates.confirming, F.text == "✅ Зберегти")
async def confirm_registration(message: Message, state: FSMContext) -> None:
    """Зберігає профіль після підтвердження."""
    data = await state.get_data()
    async with db_manager.session_factory() as session:
        service = ProfileService(session)
        user, error = await service.register_user(data)
    if error:
        await message.answer(f"❌ Помилка: {error}", reply_markup=main_menu_keyboard())
    else:
        await message.answer(
            f"✅ <b>Реєстрацію завершено!</b> Вітаємо, {data.get('username')}! 🎉",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(),
        )
    await state.clear()


@router.message(RegistrationStates.confirming, F.text == "🔄 Змінити")
async def restart_registration(message: Message, state: FSMContext) -> None:
    """
    Очищає поля введення та перезапускає форму з імені (рис. 2.9, кнопка «Змінити»).
    Зберігає лише телефон та telegram_id — їх вводити повторно не потрібно.
    """
    data = await state.get_data()
    phone_number = data.get("phone_number")
    telegram_id = data.get("telegram_id")

    await state.clear()
    await state.update_data(
        phone_number=phone_number,
        telegram_id=telegram_id,
    )

    await message.answer(
        "🔄 <b>Дані скинуто.</b> Заповніть форму знову.\n\n"
        "📝 Введіть ваше ім'я (2–50 символів):",
        parse_mode="HTML",
        reply_markup=menu_button(),
    )
    await state.set_state(RegistrationStates.waiting_name)


@router.message(RegistrationStates.confirming, F.text == "❌ Скасувати")
async def cancel_registration(message: Message, state: FSMContext) -> None:
    """Повністю скасовує реєстрацію."""
    await message.answer("Реєстрацію скасовано. Введіть /start щоб спробувати знову.")
    await state.clear()


@router.message(F.text == "👤 Профіль")
async def show_profile(message: Message) -> None:
    async with db_manager.session_factory() as session:
        service = ProfileService(session)
        profile = await service.get_profile(message.from_user.id)
    if not profile:
        await message.answer("❌ Профіль не знайдено. Введіть /start.", reply_markup=main_menu_keyboard())
        return
    text = format_profile(profile["user"], profile["metrics"])
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Редагувати профіль", callback_data="profile:edit")
    builder.button(text="🔔 Нагадування", callback_data="profile:reminders")
    builder.button(text="🚪 Вийти", callback_data="profile:logout")
    builder.adjust(1)
    await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())


@router.callback_query(F.data == "profile:logout")
async def handle_logout(callback: CallbackQuery) -> None:
    await callback.message.answer(
        "👋 До побачення! Для повторного входу введіть /start.",
        reply_markup=share_phone_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "profile:edit")
async def handle_edit_start(callback: CallbackQuery, state: FSMContext) -> None:
    builder = ReplyKeyboardBuilder()
    for f in ["Ім'я", "Вік", "Вага", "Зріст", "Рівень активності"]:
        builder.button(text=f)
    builder.adjust(2)
    await callback.message.answer(
        "Оберіть параметр для зміни:",
        reply_markup=builder.as_markup(resize_keyboard=True, one_time_keyboard=True),
    )
    await state.set_state(EditProfileStates.waiting_field)
    await callback.answer()


EDIT_FIELDS = {
    "Ім'я": "username",
    "Вік": "age",
    "Вага": "weight",
    "Зріст": "height",
    "Рівень активності": "activity_level",
}


@router.message(EditProfileStates.waiting_field)
async def handle_edit_field(message: Message, state: FSMContext) -> None:
    field = EDIT_FIELDS.get(message.text)
    if not field:
        await message.answer("❌ Оберіть параметр зі списку.")
        return
    await state.update_data(edit_field=field)
    prompts = {
        "username": "Введіть нове ім'я (2–50 символів):",
        "age": "Введіть новий вік (5–120):",
        "weight": "Введіть нову вагу в кг (10–500):",
        "height": "Введіть новий зріст в см (50–300):",
        "activity_level": None,
    }
    if field == "activity_level":
        await message.answer("Оберіть новий рівень активності:", reply_markup=activity_level_keyboard())
    else:
        await message.answer(prompts[field])
    await state.set_state(EditProfileStates.waiting_value)


@router.message(EditProfileStates.waiting_value)
async def handle_edit_value(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    field = data.get("edit_field")
    text = message.text.strip()
    value = None
    if field == "username":
        if not (2 <= len(text) <= 50) or any(c.isdigit() for c in text):
            await message.answer("❌ Ім'я: 2–50 символів, без цифр:")
            return
        value = text
    elif field == "age":
        if not text.isdigit() or not (5 <= int(text) <= 120):
            await message.answer("❌ Введіть ціле число від 5 до 120:")
            return
        value = int(text)
    elif field == "weight":
        try:
            w = float(text.replace(",", "."))
            if not (10 <= w <= 500):
                raise ValueError
            value = round(w, 1)
        except ValueError:
            await message.answer("❌ Введіть число від 20 до 500:")
            return
    elif field == "height":
        try:
            h = float(text.replace(",", "."))
            if not (50 <= h <= 300):
                raise ValueError
            value = round(h, 1)
        except ValueError:
            await message.answer("❌ Введіть число від 50 до 300:")
            return
    elif field == "activity_level":
        value = ACTIVITY_MAP.get(text)
        if not value:
            await message.answer("❌ Оберіть з кнопок:", reply_markup=activity_level_keyboard())
            return
    await state.update_data(edit_value=value)
    await message.answer("Зберегти зміни?", reply_markup=confirm_keyboard())
    await state.set_state(EditProfileStates.confirming)


@router.message(EditProfileStates.confirming, F.text == "✅ Так")
async def confirm_edit(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    async with db_manager.session_factory() as session:
        service = ProfileService(session)
        ok = await service.update_profile(
            message.from_user.id, {data["edit_field"]: data["edit_value"]}
        )
    await message.answer(
        "✅ Зміни збережено!" if ok else "❌ Не вдалося оновити.",
        reply_markup=main_menu_keyboard(),
    )
    await state.clear()


@router.message(EditProfileStates.confirming, F.text == "❌ Ні")
async def cancel_edit(message: Message, state: FSMContext) -> None:
    await message.answer("Скасовано.", reply_markup=main_menu_keyboard())
    await state.clear()


@router.message(F.text == "🏠 Menu")
async def go_to_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Головне меню:", reply_markup=main_menu_keyboard())
