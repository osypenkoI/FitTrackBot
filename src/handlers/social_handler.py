"""
Обробник соціальних функцій.
Реалізує ФВ 5.1.1 – 5.1.4: лідерборд, челенджі, запрошення друзів, прогрес учасників.
"""

import logging
from datetime import date, timedelta

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

from src.database.connection import db_manager
from src.services.social_service import SocialService
from src.utils.keyboards import main_menu_keyboard, confirm_keyboard

logger = logging.getLogger(__name__)
router = Router()


class ChallengeStates(StatesGroup):
    waiting_title = State()
    waiting_goal_value = State()
    waiting_metric = State()
    confirming = State()


class InviteStates(StatesGroup):
    waiting_challenge_id = State()
    waiting_phone = State()
    confirming = State()


METRIC_MAP = {
    "🔥 Калорії спалено": "calories_burned",
    "⏱ Хвилин тренувань": "duration_minutes",
    "🏋️ Кількість тренувань": "workouts_count",
}


def challenges_menu_keyboard():
    """Клавіатура меню соціальних функцій."""
    builder = ReplyKeyboardBuilder()
    builder.button(text="➕ Створити челендж")
    builder.button(text="📋 Мої челенджі")
    builder.button(text="🏆 Рейтинги")
    builder.button(text="👥 Запросити друга")
    builder.button(text="🏠 Menu")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


def metric_keyboard():
    """Клавіатура вибору метрики для челенджу."""
    builder = ReplyKeyboardBuilder()
    for label in METRIC_MAP:
        builder.button(text=label)
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def format_board(entries: list[dict], metric: str) -> str:
    """Форматує лідерборд залежно від обраної метрики."""
    if metric == "duration_minutes":
        title = "⏱ <b>Топ користувачів за тривалістю тренувань</b>"
        unit = "хв"
    elif metric == "workouts_count":
        title = "🏋️ <b>Топ користувачів за кількістю тренувань</b>"
        unit = "трен."
    else:
        title = "🔥 <b>Топ користувачів за спаленими калоріями</b>"
        unit = "ккал"

    if not entries:
        return f"{title}\n\nℹ️ Даних для формування рейтингу поки немає."

    medals = ["🥇", "🥈", "🥉"]
    lines = [title, ""]

    for index, item in enumerate(entries, start=1):
        prefix = medals[index - 1] if index <= 3 else f"{index}."
        username = item.get("username") or f"user_{item.get('user_id')}"
        value = float(item.get("value") or 0)

        if metric == "workouts_count":
            value_text = f"{int(value)} {unit}"
        else:
            value_text = f"{value:.0f} {unit}"

        lines.append(f"{prefix} {username} — {value_text}")

    return "\n".join(lines)


# ── Головне меню ────────────────────────────────────────────────────────────

@router.message(F.text == "🏆 Челенджі")
async def show_challenges_menu(message: Message) -> None:
    """Показує меню соціальної взаємодії."""
    await message.answer(
        "🏆 <b>Соціальна взаємодія</b>\nОберіть дію:",
        parse_mode="HTML",
        reply_markup=challenges_menu_keyboard(),
    )


# ── Лідерборд (ФВ 5.1.1) ────────────────────────────────────────────────────

@router.message(F.text == "🏆 Рейтинги")
async def show_leaderboard(message: Message) -> None:
    """Показує вибір метрики для рейтингу."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔥 За калоріями", callback_data="board:calories_burned")
    builder.button(text="⏱ За тривалістю", callback_data="board:duration_minutes")
    builder.adjust(2)

    await message.answer(
        "Оберіть метрику для рейтингу:",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data.startswith("board:"))
async def show_board_by_metric(callback: CallbackQuery) -> None:
    """Показує рейтинг користувачів за вибраною метрикою."""
    metric = callback.data.split(":", 1)[1]

    async with db_manager.session_factory() as session:
        service = SocialService(session)
        entries = await service.get_leaderboard(metric)

    text = format_board(entries, metric)

    await callback.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


# ── Створення челенджу (ФВ 5.1.2) ───────────────────────────────────────────

@router.message(F.text == "➕ Створити челендж")
async def start_create_challenge(message: Message, state: FSMContext) -> None:
    """Починає сценарій створення челенджу."""
    await message.answer(
        "Введіть назву челенджу (3–128 символів):\n"
        "<i>Приклад: 30 тренувань за місяць</i>",
        parse_mode="HTML",
    )
    await state.set_state(ChallengeStates.waiting_title)


@router.message(ChallengeStates.waiting_title)
async def handle_challenge_title(message: Message, state: FSMContext) -> None:
    """Обробляє назву челенджу."""
    title = message.text.strip()

    if len(title) < 3:
        await message.answer("❌ Назва занадто коротка (мінімум 3 символи):")
        return

    if len(title) > 128:
        await message.answer("❌ Назва занадто довга (максимум 128 символів):")
        return

    await state.update_data(title=title, creator_id=message.from_user.id)
    await message.answer(
        "Оберіть метрику челенджу:",
        reply_markup=metric_keyboard(),
    )
    await state.set_state(ChallengeStates.waiting_metric)


@router.message(ChallengeStates.waiting_metric)
async def handle_challenge_metric(message: Message, state: FSMContext) -> None:
    """Обробляє вибір метрики челенджу."""
    metric = METRIC_MAP.get(message.text)

    if not metric:
        await message.answer(
            "❌ Оберіть метрику з кнопок:",
            reply_markup=metric_keyboard(),
        )
        return

    await state.update_data(metric=metric, metric_label=message.text)
    await message.answer(
        "Введіть цільове значення (число більше 0):\n"
        "<i>Наприклад, для 30 тренувань введіть: 30</i>",
        parse_mode="HTML",
    )
    await state.set_state(ChallengeStates.waiting_goal_value)


@router.message(ChallengeStates.waiting_goal_value)
async def handle_challenge_goal(message: Message, state: FSMContext) -> None:
    """Обробляє цільове значення челенджу."""
    text = message.text.strip().replace(",", ".")

    try:
        goal = float(text)
    except ValueError:
        await message.answer("❌ Введіть число, наприклад: 30")
        return

    if goal <= 0:
        await message.answer("❌ Ціль має бути більше нуля:")
        return

    if goal > 1_000_000:
        await message.answer("❌ Занадто велике значення:")
        return

    await state.update_data(
        goal_value=goal,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=30),
    )

    data = await state.get_data()

    await message.answer(
        f"Створити челендж?\n\n"
        f"Назва: <b>{data['title']}</b>\n"
        f"Метрика: <b>{data['metric_label']}</b>\n"
        f"Ціль: <b>{goal}</b>\n"
        f"Термін: 30 днів",
        parse_mode="HTML",
        reply_markup=confirm_keyboard(),
    )
    await state.set_state(ChallengeStates.confirming)


@router.message(ChallengeStates.confirming, F.text == "✅ Так")
async def confirm_challenge(message: Message, state: FSMContext) -> None:
    """Підтверджує створення челенджу."""
    data = await state.get_data()

    async with db_manager.session_factory() as session:
        service = SocialService(session)
        challenge, error = await service.create_challenge(data)

    if error:
        await message.answer(f"❌ {error}", reply_markup=main_menu_keyboard())
    else:
        await message.answer(
            f"✅ Челендж <b>«{challenge.title}»</b> створено!\n"
            f"ID челенджу: <code>{challenge.id}</code>\n\n"
            f"Поділіться ID з друзями щоб вони приєднались.",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(),
        )

    await state.clear()


@router.message(ChallengeStates.confirming, F.text == "❌ Ні")
async def cancel_challenge(message: Message, state: FSMContext) -> None:
    """Скасовує створення челенджу."""
    await message.answer("Скасовано.", reply_markup=main_menu_keyboard())
    await state.clear()


# ── Мої челенджі (ФВ 5.1.4) ─────────────────────────────────────────────────

@router.message(F.text == "📋 Мої челенджі")
async def show_my_challenges(message: Message) -> None:
    """Показує челенджі користувача."""
    async with db_manager.session_factory() as session:
        service = SocialService(session)
        challenges = await service.get_user_challenges(message.from_user.id)

    if not challenges:
        await message.answer(
            "У вас поки немає челенджів.\n"
            "Натисніть «➕ Створити челендж».",
            reply_markup=main_menu_keyboard(),
        )
        return

    builder = InlineKeyboardBuilder()
    lines = ["📋 <b>Ваші челенджі:</b>\n"]

    for challenge in challenges:
        days_left = (challenge.end_date - date.today()).days
        status = "🟢" if days_left > 0 else "🔴"

        lines.append(
            f"{status} <b>{challenge.title}</b>\n"
            f"Ціль: {challenge.goal_value} ({challenge.metric})\n"
            f"До: {challenge.end_date} ({max(0, days_left)} дн.)"
        )

        builder.button(
            text=f"👥 Учасники: {challenge.title[:20]}",
            callback_data=f"ch:members:{challenge.id}",
        )
        builder.button(
            text=f"📨 Запросити у: {challenge.title[:15]}",
            callback_data=f"ch:invite:{challenge.id}",
        )

    builder.adjust(2)

    await message.answer(
        "\n\n".join(lines),
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )


# ── Прогрес учасників (ФВ 5.1.4) ────────────────────────────────────────────

@router.callback_query(F.data.startswith("ch:members:"))
async def show_challenge_members(callback: CallbackQuery) -> None:
    """Показує прогрес учасників челенджу."""
    challenge_id = int(callback.data.split(":")[2])

    async with db_manager.session_factory() as session:
        service = SocialService(session)
        members_data = await service.get_challenge_progress(challenge_id)

    if not members_data:
        await callback.message.answer(
            "Учасників ще немає.",
            reply_markup=main_menu_keyboard(),
        )
        await callback.answer()
        return

    lines = ["👥 <b>Прогрес учасників:</b>\n"]

    for index, entry in enumerate(members_data, start=1):
        name = entry.get("username") or f"User {entry.get('user_id')}"
        progress = float(entry.get("progress") or 0)
        target = float(entry.get("target") or 1)
        pct = min(100.0, round(progress / target * 100, 1)) if target else 0
        bar = "█" * int(pct // 10) + "░" * (10 - int(pct // 10))
        done = "✅" if pct >= 100 else "🔄"

        lines.append(
            f"{index}. {done} <b>{name}</b>\n"
            f"   {bar} {pct}%  ({progress} / {target})"
        )

    await callback.message.answer("\n".join(lines), parse_mode="HTML")
    await callback.answer()


# ── Запрошення друга (ФВ 5.1.3) ─────────────────────────────────────────────

@router.message(F.text == "👥 Запросити друга")
async def start_invite_friend(message: Message, state: FSMContext) -> None:
    """Починає сценарій запрошення друга."""
    async with db_manager.session_factory() as session:
        service = SocialService(session)
        challenges = await service.get_user_challenges(message.from_user.id)

    if not challenges:
        await message.answer(
            "❌ Спочатку створіть челендж.",
            reply_markup=main_menu_keyboard(),
        )
        return

    builder = InlineKeyboardBuilder()

    for challenge in challenges:
        builder.button(
            text=challenge.title[:30],
            callback_data=f"ch:invite:{challenge.id}",
        )

    builder.adjust(1)

    await message.answer(
        "Оберіть челендж для запрошення:",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data.startswith("ch:invite:"))
async def handle_invite_challenge_select(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Обробляє вибір челенджу для запрошення."""
    challenge_id = int(callback.data.split(":")[2])

    await state.update_data(
        invite_challenge_id=challenge_id,
        inviter_id=callback.from_user.id,
    )

    await callback.message.answer(
        "📱 Введіть номер телефону друга для запрошення:\n"
        "<i>Приклад: +380991234567</i>",
        parse_mode="HTML",
    )
    await state.set_state(InviteStates.waiting_phone)
    await callback.answer()


@router.message(InviteStates.waiting_phone)
async def handle_invite_phone(message: Message, state: FSMContext) -> None:
    """Обробляє номер телефону друга."""
    phone = message.text.strip()

    if len(phone) < 7 or len(phone) > 20:
        await message.answer(
            "❌ Номер телефону має бути від 7 до 20 символів.\n"
            "<i>Приклад: +380991234567</i>",
            parse_mode="HTML",
        )
        return

    if not phone.replace("+", "").replace("-", "").replace(" ", "").isdigit():
        await message.answer(
            "❌ Номер може містити тільки цифри, '+', '-' та пробіли:"
        )
        return

    await state.update_data(invite_phone=phone)

    await message.answer(
        f"Надіслати запрошення на номер <b>{phone}</b>?",
        parse_mode="HTML",
        reply_markup=confirm_keyboard(),
    )
    await state.set_state(InviteStates.confirming)


@router.message(InviteStates.confirming, F.text == "✅ Так")
async def confirm_invite(message: Message, state: FSMContext) -> None:
    """Підтверджує запрошення друга до челенджу."""
    data = await state.get_data()

    async with db_manager.session_factory() as session:
        service = SocialService(session)
        ok, error, friend_id = await service.invite_friend_to_challenge(
            requester_id=message.from_user.id,
            addressee_phone=data["invite_phone"],
            challenge_id=data["invite_challenge_id"],
        )

    if not ok:
        await message.answer(
            f"❌ {error}",
            reply_markup=main_menu_keyboard(),
        )
    else:
        if friend_id:
            try:
                await message.bot.send_message(
                    friend_id,
                    "🏆 Вас запросили до участі у челенджі FitTrackBot!\n\n"
                    "Відкрийте меню «Челенджі», щоб переглянути участь і прогрес.",
                )
            except Exception:
                logger.exception("Не вдалося надіслати повідомлення другу.")

        await message.answer(
            f"✅ Запрошення надіслано на <b>{data['invite_phone']}</b>!\n"
            "Друг отримав сповіщення від бота.",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(),
        )

    await state.clear()


@router.message(InviteStates.confirming, F.text == "❌ Ні")
async def cancel_invite(message: Message, state: FSMContext) -> None:
    """Скасовує запрошення друга."""
    await message.answer("Скасовано.", reply_markup=main_menu_keyboard())
    await state.clear()