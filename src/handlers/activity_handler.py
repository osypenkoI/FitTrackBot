"""
Обробник активності та харчування.
Реалізує ФВ 2.1.1–2.1.3, ФВ 2.2.1–2.2.2, ФВ 2.3.1.
Валідація всіх полів введення з зрозумілими повідомленнями.
"""

from email import message
import logging
from datetime import date
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from src.database.connection import db_manager
from src.services.activity_service import ActivityService
from src.services.profile_service import ProfileService
from src.utils.keyboards import (
    activity_type_keyboard, confirm_keyboard, main_menu_keyboard,
)
from src.utils.formatters import format_activity_log, format_nutrition_log

logger = logging.getLogger(__name__)
router = Router()


class ActivityStates(StatesGroup):
    waiting_type = State()
    waiting_duration = State()
    confirming = State()


class NutritionStates(StatesGroup):
    waiting_meal_type = State()
    waiting_food = State()
    waiting_grams = State()
    waiting_calories = State()
    waiting_bjv = State()
    confirming = State()


class EditRecordStates(StatesGroup):
    waiting_record_type = State()
    waiting_record_id = State()
    waiting_field = State()
    waiting_value = State()
    confirming = State()


MEAL_MAP = {
    "🌅 Сніданок": "breakfast",
    "☀️ Обід": "lunch",
    "🌙 Вечеря": "dinner",
    "🍎 Перекус": "snack",
}

ACTIVITY_TYPES = {
    "🏃 Кардіо": "cardio",
    "💪 Силові": "strength",
    "🧘 Йога": "yoga",
    "🚴 Велосипед": "cycling",
    "🏊 Плавання": "swimming",
    "🚶 Ходьба": "walking",
}


# ── Додати активність ────────────────────────────────────────────────────────

@router.message(F.text == "🏃 Додати активність")
async def start_activity(message: Message, state: FSMContext) -> None:
    await message.answer(
        "Оберіть тип активності:", reply_markup=activity_type_keyboard()
    )
    await state.set_state(ActivityStates.waiting_type)


@router.callback_query(F.data.startswith("activity:"))
async def handle_activity_type(callback: CallbackQuery, state: FSMContext) -> None:
    activity_type = callback.data.split(":")[1]
    await state.update_data(activity_type=activity_type, user_id=callback.from_user.id)
    await callback.message.answer(
        "⏱ Введіть тривалість тренування в хвилинах (від 1 до 480):\n"
        "<i>Приклад: 45</i>",
        parse_mode="HTML",
    )
    await state.set_state(ActivityStates.waiting_duration)
    await callback.answer()


@router.message(ActivityStates.waiting_duration)
async def handle_duration(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if not text.isdigit():
        await message.answer(
            "❌ Тривалість має бути цілим числом.\n<i>Приклад: 45</i>\nСпробуйте ще раз:",
            parse_mode="HTML",
        )
        return
    duration = int(text)
    if duration < 1:
        await message.answer("❌ Тривалість не може бути меншою за 1 хвилину:")
        return
    if duration > 480:
        await message.answer("❌ Тривалість не може перевищувати 480 хвилин (8 год):")
        return

    await state.update_data(duration_minutes=duration)
    data = await state.get_data()
    type_label = {v: k for k, v in ACTIVITY_TYPES.items()}.get(
        data["activity_type"], data["activity_type"]
    )
    await message.answer(
        f"Зберегти тренування?\n\n"
        f"Тип: <b>{type_label}</b>\n"
        f"Тривалість: <b>{duration} хв</b>",
        parse_mode="HTML",
        reply_markup=confirm_keyboard(),
    )
    await state.set_state(ActivityStates.confirming)


@router.message(ActivityStates.confirming, F.text == "✅ Так")
async def confirm_activity(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    async with db_manager.session_factory() as session:
        profile_svc = ProfileService(session)
        profile = await profile_svc.get_profile(message.from_user.id)
        weight = profile["metrics"].weight if profile and profile.get("metrics") else 70.0
        activity_svc = ActivityService(session)
        log, error = await activity_svc.log_activity(data, user_weight=weight)

        # Оновлюємо прогрес цілей після збереження активності (ФВ 6.1.2)
        if not error:
            from src.services.goals_service import GoalsService
            goals_svc = GoalsService(session)
            notifications = await goals_svc.check_goal_notifications(message.from_user.id)
            for notif in notifications:
                await message.answer(notif)

    if error:
        await message.answer(f"❌ {error}", reply_markup=main_menu_keyboard())
    else:
        await message.answer(
            format_activity_log(log),
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(),
        )
    await state.clear()


@router.message(ActivityStates.confirming, F.text == "❌ Ні")
async def cancel_activity(message: Message, state: FSMContext) -> None:
    await message.answer("Скасовано.", reply_markup=main_menu_keyboard())
    await state.clear()


# ── Додати харчування ────────────────────────────────────────────────────────

@router.message(F.text == "🥗 Додати харчування")
async def start_nutrition(message: Message, state: FSMContext) -> None:
    builder = ReplyKeyboardBuilder()
    for label in MEAL_MAP:
        builder.button(text=label)
    builder.adjust(2)
    await message.answer(
        "Оберіть тип прийому їжі:",
        reply_markup=builder.as_markup(resize_keyboard=True, one_time_keyboard=True),
    )
    await state.set_state(NutritionStates.waiting_meal_type)


@router.message(NutritionStates.waiting_meal_type)
async def handle_meal_type(message: Message, state: FSMContext) -> None:
    meal = MEAL_MAP.get(message.text)
    if not meal:
        await message.answer("❌ Оберіть тип прийому з кнопок нижче.")
        return
    await state.update_data(meal_type=meal, user_id=message.from_user.id)
    await message.answer(
        "🍽 Введіть назву страви (наприклад: Вівсянка):"
    )
    await state.set_state(NutritionStates.waiting_food)


@router.message(NutritionStates.waiting_food)
async def handle_food_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if len(name) < 1:
        await message.answer("❌ Назва страви не може бути порожньою:")
        return
    if len(name) > 128:
        await message.answer("❌ Назва занадто довга (максимум 128 символів):")
        return
    await state.update_data(food_name=name)
    await message.answer(
        "⚖️ Введіть кількість у грамах (від 1 до 5000):\n<i>Приклад: 150</i>",
        parse_mode="HTML",
    )
    await state.set_state(NutritionStates.waiting_grams)


@router.message(NutritionStates.waiting_grams)
async def handle_grams(message: Message, state: FSMContext) -> None:
    text = message.text.strip().replace(",", ".")
    try:
        grams = float(text)
    except ValueError:
        await message.answer(
            "❌ Кількість має бути числом.\n<i>Приклад: 150</i>\nСпробуйте ще раз:",
            parse_mode="HTML",
        )
        return
    if grams < 1:
        await message.answer("❌ Кількість не може бути меншою за 1 г:")
        return
    if grams > 5000:
        await message.answer("❌ Кількість не може перевищувати 5000 г:")
        return
    await state.update_data(amount_grams=round(grams, 1))
    await message.answer(
        "🔥 Введіть кількість калорій (від 1 до 10000 ккал):\n<i>Приклад: 350</i>",
        parse_mode="HTML",
    )
    await state.set_state(NutritionStates.waiting_calories)


@router.message(NutritionStates.waiting_calories)
async def handle_nutrition_calories(message: Message, state: FSMContext) -> None:
    text = message.text.strip().replace(",", ".")
    try:
        calories = float(text)
    except ValueError:
        await message.answer(
            "❌ Калорії мають бути числом.\n<i>Приклад: 350</i>\nСпробуйте ще раз:",
            parse_mode="HTML",
        )
        return
    if calories < 1:
        await message.answer("❌ Калорії не можуть бути меншими за 1 ккал:")
        return
    if calories > 10000:
        await message.answer("❌ Значення не може перевищувати 10000 ккал:")
        return

    await state.update_data(calories_intake=round(calories, 1))
    # Питаємо БЖВ (ФВ 2.2.1)
    builder = ReplyKeyboardBuilder()
    builder.button(text="⏩ Пропустити")
    builder.adjust(1)
    await message.answer(
        "Введіть БЖВ у форматі <b>Білки Жири Вуглеводи</b> (г):\n"
        "<i>Приклад: 12.5 5.0 45.0</i>\n\n"
        "Або натисніть «Пропустити».",
        parse_mode="HTML",
        reply_markup=builder.as_markup(resize_keyboard=True, one_time_keyboard=True),
    )
    await state.set_state(NutritionStates.waiting_bjv)


@router.message(NutritionStates.waiting_bjv)
async def handle_bjv(message: Message, state: FSMContext) -> None:
    """Обробляє введення БЖВ або пропуск (ФВ 2.2.1)."""
    data = await state.get_data()
    proteins = fats = carbs = None

    if message.text.strip() != "⏩ Пропустити":
        parts = message.text.strip().replace(",", ".").split()
        if len(parts) != 3:
            await message.answer(
                "❌ Введіть три числа через пробіл.\n<i>Приклад: 12.5 5.0 45.0</i>",
                parse_mode="HTML",
            )
            return
        try:
            proteins, fats, carbs = [float(p) for p in parts]
            if any(v < 0 or v > 1000 for v in (proteins, fats, carbs)):
                await message.answer("❌ Значення мають бути від 0 до 1000 г:")
                return
        except ValueError:
            await message.answer(
                "❌ Усі значення мають бути числами.\n<i>Приклад: 12.5 5.0 45.0</i>",
                parse_mode="HTML",
            )
            return

    await state.update_data(proteins=proteins, fats=fats, carbohydrates=carbs)

    # Енергетичний баланс (ФВ 2.2.2)
    calories = data["calories_intake"]

    async with db_manager.session_factory() as session:
        service = ActivityService(session)
        balance, tdee = await service.get_energy_balance(
            message.from_user.id,
            calories,
        )
    balance_text = f"+{balance}" if balance >= 0 else str(balance)
    balance_emoji = "📈" if balance >= 0 else "📉"

    bjv_text = ""
    if proteins is not None:
        bjv_text = f"\nБ: {proteins}г | Ж: {fats}г | В: {carbs}г"

    await message.answer(
        f"Зберегти запис?\n\n"
        f"Страва: <b>{data['food_name']}</b> — {data['amount_grams']} г\n"
        f"Калорій: <b>{calories:.0f} ккал</b>{bjv_text}\n\n"
        f"{balance_emoji} Баланс: <b>{balance_text} ккал</b>",
        parse_mode="HTML",
        reply_markup=confirm_keyboard(),
    )
    await state.set_state(NutritionStates.confirming)


@router.message(NutritionStates.confirming, F.text == "✅ Так")
async def confirm_nutrition(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    async with db_manager.session_factory() as session:
        service = ActivityService(session)
        log, error = await service.log_nutrition(data)
    if error:
        await message.answer(f"❌ {error}", reply_markup=main_menu_keyboard())
    else:
        await message.answer(
            format_nutrition_log(log), parse_mode="HTML", reply_markup=main_menu_keyboard()
        )
    await state.clear()


@router.message(NutritionStates.confirming, F.text == "❌ Ні")
async def cancel_nutrition(message: Message, state: FSMContext) -> None:
    await message.answer("Скасовано.", reply_markup=main_menu_keyboard())
    await state.clear()


# ── Перегляд та редагування історії (ФВ 2.3.1) ──────────────────────────────

@router.message(F.text == "📋 Історія")
async def show_history_menu(message: Message) -> None:
    builder = ReplyKeyboardBuilder()
    builder.button(text="🏃 Активність")
    builder.button(text="🥗 Харчування")
    builder.button(text="🏠 Menu")
    builder.adjust(2)
    await message.answer(
        "Оберіть тип історії:",
        reply_markup=builder.as_markup(resize_keyboard=True),
    )


@router.message(F.text.in_({"🏃 Активність", "🥗 Харчування"}))
async def show_history(message: Message) -> None:
    history_type = "activity" if message.text == "🏃 Активність" else "nutrition"
    async with db_manager.session_factory() as session:
        service = ActivityService(session)
        records = await service.get_history(message.from_user.id, history_type)

    if not records:
        await message.answer("Записів не знайдено.", reply_markup=main_menu_keyboard())
        return

    builder = InlineKeyboardBuilder()
    lines = []
    for rec in records[:10]:
        if history_type == "activity":
            label = f"{rec.activity_type} — {rec.duration_minutes}хв — {rec.calories_burned:.0f}ккал"
            short = f"{rec.created_at.strftime('%d.%m')} {rec.activity_type[:8]}"
        else:
            label = f"{rec.food_name} {rec.amount_grams:.0f}г — {rec.calories_intake:.0f}ккал"
            short = f"{rec.date} {rec.food_name[:8]}"
        lines.append(label)
        builder.button(text=f"✏️ {short}", callback_data=f"edit:{history_type}:{rec.id}")
        builder.button(text=f"🗑 {short}", callback_data=f"del:{history_type}:{rec.id}")

    builder.adjust(2)
    text = f"📋 <b>Остання 10 записів ({message.text}):</b>\n\n" + "\n".join(
        f"{i+1}. {l}" for i, l in enumerate(lines)
    )
    await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("del:"))
async def delete_record(callback: CallbackQuery) -> None:
    _, rec_type, rec_id = callback.data.split(":")
    async with db_manager.session_factory() as session:
        service = ActivityService(session)
        ok = await service.delete_record(int(rec_id), rec_type)
    await callback.message.answer(
        "✅ Запис видалено." if ok else "❌ Не вдалося видалити.",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("edit:"))
async def start_edit_record(callback: CallbackQuery, state: FSMContext) -> None:
    _, rec_type, rec_id = callback.data.split(":")
    await state.update_data(
        edit_rec_type=rec_type, edit_rec_id=int(rec_id), user_id=callback.from_user.id
    )
    if rec_type == "activity":
        builder = ReplyKeyboardBuilder()
        for f in ["Тип активності", "Тривалість"]:
            builder.button(text=f)
        builder.adjust(2)
    else:
        builder = ReplyKeyboardBuilder()
        for f in ["Назва страви", "Кількість грамів", "Калорії"]:
            builder.button(text=f)
        builder.adjust(2)

    await callback.message.answer(
        "Що бажаєте змінити?",
        reply_markup=builder.as_markup(resize_keyboard=True, one_time_keyboard=True),
    )
    await state.set_state(EditRecordStates.waiting_field)
    await callback.answer()


@router.message(EditRecordStates.waiting_field)
async def handle_record_edit_field(message: Message, state: FSMContext) -> None:
    field_map = {
        "Тип активності": "activity_type",
        "Тривалість": "duration_minutes",
        "Назва страви": "food_name",
        "Кількість грамів": "amount_grams",
        "Калорії": "calories_intake",
    }
    field = field_map.get(message.text)
    if not field:
        await message.answer("❌ Оберіть параметр зі списку.")
        return
    await state.update_data(edit_field=field)

    prompts = {
        "activity_type": "Введіть новий тип (cardio/strength/yoga/cycling/swimming/running/walking):",
        "duration_minutes": "Введіть нову тривалість в хвилинах (1–480):",
        "food_name": "Введіть нову назву страви:",
        "amount_grams": "Введіть нову кількість у грамах (1–5000):",
        "calories_intake": "Введіть нову кількість калорій (1–10000):",
    }
    await message.answer(prompts[field])
    await state.set_state(EditRecordStates.waiting_value)


@router.message(EditRecordStates.waiting_value)
async def handle_record_edit_value(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    field = data["edit_field"]
    text = message.text.strip()
    value = None

    if field == "activity_type":
        allowed = {"cardio", "strength", "yoga", "cycling", "swimming", "running", "walking"}
        if text.lower() not in allowed:
            await message.answer(f"❌ Допустимі типи: {', '.join(allowed)}")
            return
        value = text.lower()

    elif field == "duration_minutes":
        if not text.isdigit() or not (1 <= int(text) <= 480):
            await message.answer("❌ Введіть ціле число від 1 до 480:")
            return
        value = int(text)

    elif field == "food_name":
        if not (1 <= len(text) <= 128):
            await message.answer("❌ Назва: 1–128 символів:")
            return
        value = text

    elif field in ("amount_grams", "calories_intake"):
        limits = {"amount_grams": (1, 5000), "calories_intake": (1, 10000)}
        lo, hi = limits[field]
        try:
            v = float(text.replace(",", "."))
            if not (lo <= v <= hi):
                raise ValueError
            value = round(v, 1)
        except ValueError:
            await message.answer(f"❌ Введіть число від {lo} до {hi}:")
            return

    await state.update_data(edit_value=value)
    await message.answer(f"Зберегти зміни ({field} = {value})?", reply_markup=confirm_keyboard())
    await state.set_state(EditRecordStates.confirming)


@router.message(EditRecordStates.confirming, F.text == "✅ Так")
async def confirm_record_edit(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    async with db_manager.session_factory() as session:
        service = ActivityService(session)
        ok = await service.update_record(
            user_id=message.from_user.id,
            record_id=data["edit_rec_id"],
            record_type=data["edit_rec_type"],
            field=data["edit_field"],
            value=data["edit_value"],
        )

    if ok:
        await message.answer("✅ Запис оновлено!", reply_markup=main_menu_keyboard())
    else:
        await message.answer("❌ Запис не знайдено.", reply_markup=main_menu_keyboard())
    await state.clear()


@router.message(EditRecordStates.confirming, F.text == "❌ Ні")
async def cancel_record_edit(message: Message, state: FSMContext) -> None:
    await message.answer("Скасовано.", reply_markup=main_menu_keyboard())
    await state.clear()
