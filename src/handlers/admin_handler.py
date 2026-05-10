"""
Адміністраторський обробник FitTrackBot.
Реалізує A2 (статистика), A3 (розсилки), A4 (блокування/скидання кешу).
Доступ лише для user_id із config.admin_ids.
"""

import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from src.services.admin_service import AdminService
from src.config import config
from src.database.connection import db_manager
from src.utils.keyboards import main_menu_keyboard, confirm_keyboard

logger = logging.getLogger(__name__)
router = Router()


# ── Middleware: перевірка доступу адміністратора ──────────────────────────────

def is_admin(user_id: int) -> bool:
    """Перевіряє чи є користувач адміністратором."""
    return user_id in config.admin_ids


def admin_menu_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="📊 Статистика")
    builder.button(text="📢 Розсилка")
    builder.button(text="🚫 Заблокувати")
    builder.button(text="🏠 Menu")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


class AdminStates(StatesGroup):
    waiting_broadcast_text = State()
    broadcast_confirming = State()
    waiting_block_id = State()
    block_confirming = State()


# ── Вхід до адмін-панелі ────────────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає доступу до адмін-панелі.")
        return
    await message.answer(
        "👨‍💼 <b>Адмін-панель FitTrackBot</b>\nОберіть дію:",
        parse_mode="HTML",
        reply_markup=admin_menu_keyboard(),
    )


# ── A2: Статистика використання ──────────────────────────────────────────────

@router.message(F.text == "📊 Статистика")
async def show_admin_stats(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return

    async with db_manager.session_factory() as session:
        service = AdminService(session)
        stats = await service.get_statistics()

    await message.answer(
        f"📊 <b>Статистика FitTrackBot</b>\n\n"
        f"👥 Всього користувачів: <b>{stats['total_users']}</b>\n"
        f"🟢 Активних за 7 днів: <b>{stats['active_7d']}</b>\n"
        f"🆕 Нових сьогодні: <b>{stats['new_today']}</b>\n"
        f"📝 Всього записів активності: <b>{stats['total_logs']}</b>",
        parse_mode="HTML",
        reply_markup=admin_menu_keyboard(),
    )


# ── A3: Масова розсилка ──────────────────────────────────────────────────────

@router.message(F.text == "📢 Розсилка")
async def start_broadcast(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "✏️ Введіть текст для масової розсилки всім користувачам:\n"
        "<i>(Підтримується HTML-розмітка: &lt;b&gt;, &lt;i&gt;, &lt;a&gt;)</i>",
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.waiting_broadcast_text)


@router.message(AdminStates.waiting_broadcast_text)
async def handle_broadcast_text(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    text_to_send = message.text.strip()
    if len(text_to_send) < 3:
        await message.answer("❌ Текст занадто короткий (мінімум 3 символи):")
        return
    if len(text_to_send) > 4096:
        await message.answer("❌ Текст занадто довгий (максимум 4096 символів):")
        return
    await state.update_data(broadcast_text=text_to_send)
    await message.answer(
        f"Надіслати всім користувачам:\n\n{text_to_send}\n\n—\nПідтвердіть розсилку:",
        reply_markup=confirm_keyboard(),
    )
    await state.set_state(AdminStates.broadcast_confirming)


@router.message(AdminStates.broadcast_confirming, F.text == "✅ Так")
async def confirm_broadcast(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    broadcast_text = data["broadcast_text"]

    async with db_manager.session_factory() as session:
        service = AdminService(session)
        user_ids = await service.get_all_user_ids()

    bot = message.bot
    sent = 0
    failed = 0
    for uid in user_ids:
        try:
            await bot.send_message(uid, broadcast_text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1

    await message.answer(
        f"✅ Розсилку завершено.\nНадіслано: {sent}\nПомилок: {failed}",
        reply_markup=admin_menu_keyboard(),
    )
    await state.clear()


@router.message(AdminStates.broadcast_confirming, F.text == "❌ Ні")
async def cancel_broadcast(message: Message, state: FSMContext) -> None:
    await message.answer("Розсилку скасовано.", reply_markup=admin_menu_keyboard())
    await state.clear()


# ── A4: Блокування користувача ───────────────────────────────────────────────

@router.message(F.text == "🚫 Заблокувати")
async def start_block_user(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "Введіть Telegram ID користувача для блокування:\n"
        "<i>Дізнатися ID можна через /stats або через бота @userinfobot</i>",
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.waiting_block_id)


@router.message(AdminStates.waiting_block_id)
async def handle_block_id(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    text = message.text.strip()
    if not text.isdigit():
        await message.answer("❌ Введіть числовий Telegram ID:")
        return
    target_id = int(text)
    if target_id in config.admin_ids:
        await message.answer("❌ Неможливо заблокувати адміністратора.")
        return
    await state.update_data(block_target_id=target_id)
    await message.answer(
        f"Заблокувати користувача ID <code>{target_id}</code>?\n"
        f"Це видалить його з бази даних.",
        parse_mode="HTML",
        reply_markup=confirm_keyboard(),
    )
    await state.set_state(AdminStates.block_confirming)


@router.message(AdminStates.block_confirming, F.text == "✅ Так")
async def confirm_block(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    target_id = data["block_target_id"]

    async with db_manager.session_factory() as session:
        service = AdminService(session)
        blocked = await service.block_user(target_id)

    if blocked:
        await message.answer(
            f"✅ Користувача <code>{target_id}</code> заблоковано та видалено.",
            parse_mode="HTML",
            reply_markup=admin_menu_keyboard(),
        )
    else:
        await message.answer(
            f"❌ Користувача з ID {target_id} не знайдено.",
            reply_markup=admin_menu_keyboard(),
        )

    await state.clear()


@router.message(AdminStates.block_confirming, F.text == "❌ Ні")
async def cancel_block(message: Message, state: FSMContext) -> None:
    await message.answer("Скасовано.", reply_markup=admin_menu_keyboard())
    await state.clear()


# ── A4: Скидання кешу ────────────────────────────────────────────────────────

@router.message(F.text == "🔄 Скинути кеш")
async def reset_cache(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    # Скидаємо пул підключень (реініціалізуємо з'єднання)
    await db_manager.close()
    # Повторна ініціалізація відбудеться при наступному запиті автоматично
    await message.answer(
        "✅ Кеш підключень до бази даних скинуто.",
        reply_markup=admin_menu_keyboard(),
    )
