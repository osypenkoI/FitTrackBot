"""
Обробник персональних цілей.
Реалізує ФВ 6.1.1 – 6.1.4.
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from src.database.connection import db_manager
from src.services.goals_service import GoalsService, GOAL_TYPES, PERIOD_MAP
from src.utils.keyboards import confirm_keyboard, main_menu_keyboard

logger = logging.getLogger(__name__)
router = Router()


class GoalStates(StatesGroup):
    waiting_type = State()
    waiting_value = State()
    waiting_period = State()
    confirming = State()


class EditGoalStates(StatesGroup):
    waiting_field = State()
    waiting_value = State()
    confirming = State()


def goal_type_keyboard():
    builder = ReplyKeyboardBuilder()
    for label in GOAL_TYPES.values():
        builder.button(text=label)
    builder.button(text="🏠 Menu")
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def period_keyboard():
    builder = ReplyKeyboardBuilder()
    for label in PERIOD_MAP:
        builder.button(text=label)
    builder.adjust(3)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


GOAL_LABEL_TO_KEY = {v: k for k, v in GOAL_TYPES.items()}


@router.message(F.text == "🎯 Мої цілі")
async def show_goals_menu(message: Message) -> None:
    builder = ReplyKeyboardBuilder()
    builder.button(text="➕ Встановити ціль")
    builder.button(text="📊 Мої цілі")
    builder.button(text="🏠 Menu")
    builder.adjust(2)
    await message.answer(
        "🎯 <b>Управління цілями</b>",
        parse_mode="HTML",
        reply_markup=builder.as_markup(resize_keyboard=True),
    )


@router.message(F.text == "➕ Встановити ціль")
async def start_create_goal(message: Message, state: FSMContext) -> None:
    await message.answer(
        "Оберіть тип цілі:",
        reply_markup=goal_type_keyboard(),
    )
    await state.set_state(GoalStates.waiting_type)


@router.message(GoalStates.waiting_type)
async def handle_goal_type(message: Message, state: FSMContext) -> None:
    goal_key = GOAL_LABEL_TO_KEY.get(message.text)
    if not goal_key:
        await message.answer("❌ Оберіть тип цілі з кнопок:", reply_markup=goal_type_keyboard())
        return
    await state.update_data(goal_type=goal_key, goal_label=message.text)
    examples = {
        "workouts_per_week": "Приклад: 3 (тренувань на тиждень)",
        "calories_per_day": "Приклад: 2000 (ккал на день)",
        "calories_burned_total": "Приклад: 5000 (ккал за період)",
        "duration_minutes_total": "Приклад: 600 (хвилин за період)",
    }
    await message.answer(
        f"Введіть значення цілі (число більше 0):\n"
        f"<i>{examples.get(goal_key, '')}</i>",
        parse_mode="HTML",
    )
    await state.set_state(GoalStates.waiting_value)


@router.message(GoalStates.waiting_value)
async def handle_goal_value(message: Message, state: FSMContext) -> None:
    text = message.text.strip().replace(",", ".")
    try:
        value = float(text)
    except ValueError:
        await message.answer("❌ Значення має бути числом. Наприклад: 3")
        return
    if value <= 0:
        await message.answer("❌ Значення має бути більше нуля:")
        return
    if value > 1_000_000:
        await message.answer("❌ Значення занадто велике:")
        return
    await state.update_data(target_value=value)
    await message.answer(
        "Оберіть термін виконання цілі:",
        reply_markup=period_keyboard(),
    )
    await state.set_state(GoalStates.waiting_period)


@router.message(GoalStates.waiting_period)
async def handle_goal_period(message: Message, state: FSMContext) -> None:
    period_days = PERIOD_MAP.get(message.text)
    if not period_days:
        await message.answer("❌ Оберіть термін з кнопок:", reply_markup=period_keyboard())
        return
    await state.update_data(period_days=period_days)
    data = await state.get_data()
    await message.answer(
        f"Зберегти ціль?\n\n"
        f"Тип: <b>{data['goal_label']}</b>\n"
        f"Значення: <b>{data['target_value']}</b>\n"
        f"Термін: <b>{message.text}</b>",
        parse_mode="HTML",
        reply_markup=confirm_keyboard(),
    )
    await state.set_state(GoalStates.confirming)


@router.message(GoalStates.confirming, F.text == "✅ Так")
async def confirm_goal(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    async with db_manager.session_factory() as session:
        service = GoalsService(session)
        goal, error = await service.create_goal(
            user_id=message.from_user.id,
            goal_type=data["goal_type"],
            target_value=data["target_value"],
            period_days=data["period_days"],
        )
    if error:
        await message.answer(f"❌ {error}", reply_markup=main_menu_keyboard())
    else:
        await message.answer(
            f"✅ Ціль <b>{data['goal_label']}</b> встановлено!",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(),
        )
    await state.clear()


@router.message(GoalStates.confirming, F.text == "❌ Ні")
async def cancel_goal(message: Message, state: FSMContext) -> None:
    await message.answer("Скасовано.", reply_markup=main_menu_keyboard())
    await state.clear()


@router.message(F.text == "📊 Мої цілі")
async def show_my_goals(message: Message) -> None:
    async with db_manager.session_factory() as session:
        service = GoalsService(session)
        goals_data = await service.get_goals_with_progress(message.from_user.id)

    if not goals_data:
        await message.answer(
            "У вас ще немає активних цілей.\nНатисніть «➕ Встановити ціль».",
            reply_markup=main_menu_keyboard(),
        )
        return

    builder = InlineKeyboardBuilder()
    lines = ["🎯 <b>Ваші активні цілі:</b>\n"]
    for item in goals_data:
        goal = item["goal"]
        name = GOAL_TYPES.get(goal.goal_type, goal.goal_type)
        pct = item["progress_pct"]
        bar = "█" * int(pct // 10) + "░" * (10 - int(pct // 10))
        status = "✅" if item["is_done"] else ("⚠️" if item["at_risk"] else "🔄")
        lines.append(
            f"{status} <b>{name}</b>\n"
            f"{bar} {pct}%\n"
            f"{item['current']} / {goal.target_value}  "
            f"(залишилось {item['days_left']} дн.)\n"
        )
        builder.button(
            text=f"✏️ Редагувати: {name[:15]}", callback_data=f"goal:edit:{goal.id}"
        )
        builder.button(
            text=f"🗑 Видалити: {name[:15]}", callback_data=f"goal:del:{goal.id}"
        )

    builder.adjust(1)
    await message.answer(
        "\n".join(lines), parse_mode="HTML", reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("goal:del:"))
async def delete_goal(callback: CallbackQuery) -> None:
    goal_id = int(callback.data.split(":")[2])
    async with db_manager.session_factory() as session:
        service = GoalsService(session)
        ok = await service.delete_goal(goal_id, callback.from_user.id)
    await callback.message.answer(
        "✅ Ціль видалено." if ok else "❌ Не вдалося видалити.",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


# ── Редагування цілі (ФВ 6.1.4) ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("goal:edit:"))
async def start_edit_goal(callback: CallbackQuery, state: FSMContext) -> None:
    goal_id = int(callback.data.split(":")[2])
    await state.update_data(edit_goal_id=goal_id)
    builder = ReplyKeyboardBuilder()
    builder.button(text="🎯 Тип цілі")
    builder.button(text="🔢 Значення")
    builder.button(text="📅 Термін")
    builder.adjust(2)
    await callback.message.answer(
        "Що бажаєте змінити в цілі?",
        reply_markup=builder.as_markup(resize_keyboard=True, one_time_keyboard=True),
    )
    await state.set_state(EditGoalStates.waiting_field)
    await callback.answer()


@router.message(EditGoalStates.waiting_field)
async def handle_edit_goal_field(message: Message, state: FSMContext) -> None:
    field_map = {
        "🎯 Тип цілі": "goal_type",
        "🔢 Значення": "target_value",
        "📅 Термін": "period_days",
    }
    field = field_map.get(message.text)
    if not field:
        await message.answer("❌ Оберіть параметр зі списку.")
        return
    await state.update_data(edit_goal_field=field)
    if field == "goal_type":
        await message.answer("Оберіть новий тип цілі:", reply_markup=goal_type_keyboard())
    elif field == "target_value":
        await message.answer(
            "Введіть нове значення цілі (число більше 0):\n<i>Приклад: 5</i>",
            parse_mode="HTML",
        )
    else:
        await message.answer("Оберіть новий термін:", reply_markup=period_keyboard())
    await state.set_state(EditGoalStates.waiting_value)


@router.message(EditGoalStates.waiting_value)
async def handle_edit_goal_value(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    field = data["edit_goal_field"]
    text = message.text.strip()
    value = None

    if field == "goal_type":
        key = GOAL_LABEL_TO_KEY.get(text)
        if not key:
            await message.answer("❌ Оберіть тип з кнопок:", reply_markup=goal_type_keyboard())
            return
        value = key

    elif field == "target_value":
        try:
            value = float(text.replace(",", "."))
            if value <= 0 or value > 1_000_000:
                raise ValueError
        except ValueError:
            await message.answer("❌ Введіть число більше 0:")
            return

    elif field == "period_days":
        value = PERIOD_MAP.get(text)
        if not value:
            await message.answer("❌ Оберіть термін з кнопок:", reply_markup=period_keyboard())
            return

    await state.update_data(edit_goal_value=value)
    await message.answer(
        f"Зберегти зміну ({field} → {value})?",
        reply_markup=confirm_keyboard(),
    )
    await state.set_state(EditGoalStates.confirming)


@router.message(EditGoalStates.confirming, F.text == "✅ Так")
async def confirm_goal_edit(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    async with db_manager.session_factory() as session:
        service = GoalsService(session)
        ok = await service.update_goal(
            user_id=message.from_user.id,
            goal_id=data["edit_goal_id"],
            field=data["edit_goal_field"],
            value=data["edit_goal_value"],
        )

    if ok:
        await message.answer("✅ Ціль оновлено!", reply_markup=main_menu_keyboard())
    else:
        await message.answer("❌ Ціль не знайдено.", reply_markup=main_menu_keyboard())
    await state.clear()


@router.message(EditGoalStates.confirming, F.text == "❌ Ні")
async def cancel_goal_edit(message: Message, state: FSMContext) -> None:
    await message.answer("Скасовано.", reply_markup=main_menu_keyboard())
    await state.clear()
