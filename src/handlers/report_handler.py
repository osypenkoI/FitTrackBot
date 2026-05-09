"""
Обробник генерації та відправки звітів.
Реалізує ФВ 4.1.1–4.1.2 та кнопку «Поділитися» (позначка 26) — надсилання звіту іншому користувачу.
"""

import logging
from datetime import date, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from src.database.connection import db_manager
from src.services.reporting_service import ReportingService
from src.repository.profile_repo import ProfileRepository
from src.utils.keyboards import main_menu_keyboard, report_format_keyboard, confirm_keyboard

logger = logging.getLogger(__name__)
router = Router()


class ShareStates(StatesGroup):
    waiting_phone = State()
    confirming = State()


# ── Меню звітів ──────────────────────────────────────────────────────────────

@router.message(F.text == "📄 Звіти")
async def show_reports_menu(message: Message) -> None:
    await message.answer(
        "Оберіть варіант отримання звіту за останні 7 днів:",
        reply_markup=report_format_keyboard(),
    )


# ── PDF звіт (ФВ 4.1.1) ──────────────────────────────────────────────────────

@router.callback_query(F.data == "report:pdf")
async def generate_pdf_report(callback: CallbackQuery) -> None:
    await callback.message.answer("⏳ Створення звіту у PDF-форматі...")
    date_to = date.today()
    date_from = date_to - timedelta(days=7)

    async with db_manager.session_factory() as session:
        service = ReportingService(session)
        try:
            pdf_bytes = await service.generate_pdf(
                callback.from_user.id, date_from, date_to
            )
        except Exception as e:
            logger.error("PDF generation error: %s", e)
            await callback.message.answer(
                f"❌ Помилка генерації PDF: {e}",
                reply_markup=main_menu_keyboard(),
            )
            await callback.answer()
            return

    file = BufferedInputFile(
        pdf_bytes,
        filename=f"fittrackbot_report_{date_from}_{date_to}.pdf",
    )
    await callback.message.answer_document(
        document=file,
        caption="📕 <b>PDF-звіт створено!</b> Натисніть щоб переглянути або завантажити.",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


# ── Excel звіт (ФВ 4.1.2) ────────────────────────────────────────────────────

@router.callback_query(F.data == "report:excel")
async def generate_excel_report(callback: CallbackQuery) -> None:
    await callback.message.answer("⏳ Створення звіту у форматі Excel...")
    date_to = date.today()
    date_from = date_to - timedelta(days=30)

    async with db_manager.session_factory() as session:
        service = ReportingService(session)
        try:
            excel_bytes = await service.generate_excel(
                callback.from_user.id, date_from, date_to
            )
        except Exception as e:
            logger.error("Excel generation error: %s", e)
            await callback.message.answer(
                f"❌ Помилка генерації Excel: {e}",
                reply_markup=main_menu_keyboard(),
            )
            await callback.answer()
            return

    file = BufferedInputFile(
        excel_bytes,
        filename=f"fittrackbot_data_{date_from}_{date_to}.xlsx",
    )
    await callback.message.answer_document(
        document=file,
        caption="📗 <b>Excel-файл створено!</b> Натисніть щоб переглянути або завантажити.",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


# ── Поділитися звітом (позначка 26, ФВ 4.1.1) ────────────────────────────────

@router.callback_query(F.data == "report:share")
async def start_share_report(callback: CallbackQuery, state: FSMContext) -> None:
    """Ініціює процес надсилання звіту іншому користувачу."""
    await callback.message.answer(
        "📤 <b>Поділитися звітом</b>\n\n"
        "Введіть номер телефону користувача, якому хочете надіслати звіт:\n"
        "<i>Приклад: +380991234567</i>",
        parse_mode="HTML",
    )
    await state.update_data(share_sender_id=callback.from_user.id)
    await state.set_state(ShareStates.waiting_phone)
    await callback.answer()


@router.message(ShareStates.waiting_phone)
async def handle_share_phone(message: Message, state: FSMContext) -> None:
    """Валідує номер телефону отримувача звіту."""
    phone = message.text.strip()

    # Валідація номера
    if len(phone) < 7 or len(phone) > 20:
        await message.answer(
            "❌ Номер телефону має бути від 7 до 20 символів.\n"
            "<i>Приклад: +380991234567</i>",
            parse_mode="HTML",
        )
        return
    if not phone.replace("+", "").replace("-", "").replace(" ", "").isdigit():
        await message.answer(
            "❌ Номер може містити тільки цифри та символи '+', '-', пробіл:"
        )
        return

    # Перевіряємо чи існує такий користувач
    async with db_manager.session_factory() as session:
        prof_repo = ProfileRepository(session)
        recipient = await prof_repo.get_by_phone(phone)

    if not recipient:
        await message.answer(
            "❌ Користувача з таким номером не знайдено в FitTrackBot.\n"
            "Переконайтеся що ваш друг зареєстрований у боті.",
            reply_markup=main_menu_keyboard(),
        )
        await state.clear()
        return

    await state.update_data(
        share_phone=phone,
        share_recipient_id=recipient.user_id,
        share_recipient_name=recipient.username or f"User {recipient.user_id}",
    )
    await message.answer(
        f"Надіслати PDF-звіт користувачу "
        f"<b>{recipient.username or phone}</b>?",
        parse_mode="HTML",
        reply_markup=confirm_keyboard(),
    )
    await state.set_state(ShareStates.confirming)


@router.message(ShareStates.confirming, F.text == "✅ Так")
async def confirm_share(message: Message, state: FSMContext) -> None:
    """Генерує PDF та надсилає отримувачу."""
    data = await state.get_data()
    sender_id = data["share_sender_id"]
    recipient_id = data["share_recipient_id"]
    recipient_name = data["share_recipient_name"]

    await message.answer("⏳ Генерую звіт для надсилання...")

    date_to = date.today()
    date_from = date_to - timedelta(days=7)

    async with db_manager.session_factory() as session:
        service = ReportingService(session)
        try:
            pdf_bytes = await service.generate_pdf(sender_id, date_from, date_to)
        except Exception as e:
            logger.error("Share PDF error: %s", e)
            await message.answer(
                f"❌ Помилка генерації звіту: {e}",
                reply_markup=main_menu_keyboard(),
            )
            await state.clear()
            return

    # Отримуємо ім'я відправника
    async with db_manager.session_factory() as session:
        prof_repo = ProfileRepository(session)
        sender = await prof_repo.get_by_telegram_id(sender_id)
    sender_name = sender.username if sender else "Користувач"

    # Надсилаємо файл отримувачу
    from aiogram import Bot
    bot = Bot.get_current()
    file = BufferedInputFile(
        pdf_bytes,
        filename=f"fittrackbot_shared_report_{date_from}_{date_to}.pdf",
    )
    try:
        await bot.send_document(
            chat_id=recipient_id,
            document=file,
            caption=(
                f"📤 <b>Вам надіслали звіт!</b>\n\n"
                f"Користувач <b>{sender_name}</b> поділився своїм "
                f"аналітичним звітом FitTrackBot.\n"
                f"Період: {date_from} — {date_to}"
            ),
            parse_mode="HTML",
        )
        await message.answer(
            f"✅ Звіт успішно надіслано користувачу <b>{recipient_name}</b>!",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(),
        )
    except Exception as e:
        logger.error("Cannot send to recipient %d: %s", recipient_id, e)
        await message.answer(
            "❌ Не вдалося надіслати звіт. Можливо, користувач заблокував бота.",
            reply_markup=main_menu_keyboard(),
        )

    await state.clear()


@router.message(ShareStates.confirming, F.text == "❌ Ні")
async def cancel_share(message: Message, state: FSMContext) -> None:
    await message.answer("Скасовано.", reply_markup=main_menu_keyboard())
    await state.clear()
