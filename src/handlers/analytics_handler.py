"""Обробник аналітики та прогнозування."""

import logging
from aiogram import Router, F
from aiogram.types import Message, BufferedInputFile
from src.database.connection import db_manager
from src.services.analytics_core import AnalyticsCore
from src.utils.keyboards import main_menu_keyboard, report_format_keyboard
from src.utils.formatters import format_analytics

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text == "📊 Аналітика")
async def show_analytics(message: Message) -> None:
    """Генерує аналітичний звіт з прогнозом та виявленням аномалій."""
    await message.answer("⏳ Будую прогноз, зачекайте...")

    async with db_manager.session_factory() as session:
        core = AnalyticsCore(session)
        chart_bytes, metrics, error = await core.build_forecast(
            message.from_user.id, days=14
        )

        if error:
            await message.answer(
                f"ℹ️ {error}", reply_markup=main_menu_keyboard()
            )
            return

        # Виявлення аномалій
        anomaly_result = await core.detect_user_anomalies(message.from_user.id)

    text = format_analytics(metrics, anomaly_result)

    # Рекомендації (ФВ 4.2.1)
    async with db_manager.session_factory() as session:
        core2 = AnalyticsCore(session)
        recommendations = await core2.generate_recommendations(message.from_user.id)

    if chart_bytes:
        photo = BufferedInputFile(chart_bytes, filename="forecast.png")
        await message.answer_photo(
            photo=photo,
            caption=text,
            parse_mode="HTML",
            reply_markup=report_format_keyboard(),
        )
    else:
        await message.answer(text, parse_mode="HTML")

    await message.answer(recommendations, parse_mode="HTML", reply_markup=main_menu_keyboard())
