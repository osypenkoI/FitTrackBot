"""
Планувальник нагадувань FitTrackBot.
Запускається як фонова задача asyncio.
Кожну хвилину перевіряє нагадування та надсилає їх у потрібний час.
Реалізує Timer/Планувальник — внутрішній автоматизований актор (табл. 2.1).
"""

import asyncio
import logging
from datetime import datetime
from aiogram import Bot
from sqlalchemy import select
from src.database.connection import db_manager
from src.models.domain import Reminder, User

logger = logging.getLogger(__name__)


async def check_and_send_reminders(bot: Bot) -> None:
    """
    Перевіряє всі активні нагадування та надсилає ті,
    які збігаються з поточним часом та днем тижня.
    """
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    current_day = now.isoweekday()  # 1=пн, 7=нд

    async with db_manager.session_factory() as session:
        result = await session.execute(
            select(Reminder).where(Reminder.is_active == True)
        )
        reminders = result.scalars().all()

        for reminder in reminders:
            # Перевіряємо чи збігається час
            if reminder.remind_time != current_time:
                continue
            # Перевіряємо чи збігається день тижня
            days = [int(d) for d in reminder.days_of_week.split(",") if d.strip()]
            if current_day not in days:
                continue

            # Формуємо текст нагадування
            if reminder.reminder_type == "workout":
                text = (
                    "🏋️ <b>Час тренування!</b>\n\n"
                    "Не забудьте зафіксувати вашу активність.\n"
                    "Натисніть «🏃 Додати активність» у меню."
                )
            elif reminder.reminder_type == "nutrition":
                text = (
                    "🥗 <b>Нагадування про харчування!</b>\n\n"
                    "Не забудьте внести дані про прийом їжі.\n"
                    "Натисніть «🥗 Додати харчування» у меню."
                )
            else:
                text = (
                    "🔔 <b>Нагадування FitTrackBot!</b>\n\n"
                    "Час внести дані про тренування та харчування."
                )

            try:
                await bot.send_message(
                    reminder.user_id,
                    text,
                    parse_mode="HTML",
                )
                logger.info(
                    "Нагадування надіслано: user=%d type=%s",
                    reminder.user_id,
                    reminder.reminder_type,
                )
            except Exception as e:
                logger.warning(
                    "Не вдалося надіслати нагадування user=%d: %s",
                    reminder.user_id, e,
                )


async def run_scheduler(bot: Bot) -> None:
    """
    Основний цикл планувальника.
    Запускається при старті бота як фонова задача asyncio.
    Перевіряє нагадування кожну хвилину.
    """
    logger.info("Планувальник нагадувань запущено.")
    while True:
        try:
            await check_and_send_reminders(bot)
        except Exception as e:
            logger.error("Помилка в планувальнику: %s", e)
        # Чекаємо до наступної хвилини
        now = datetime.now()
        seconds_to_next_minute = 60 - now.second
        await asyncio.sleep(seconds_to_next_minute)
