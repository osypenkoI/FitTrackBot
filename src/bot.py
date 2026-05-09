"""
Точка входу FitTrackBot.
Ініціалізує Dispatcher, реєструє всі роутери,
запускає планувальник нагадувань як фонову задачу.
"""

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from src.config import config
from src.database.connection import db_manager
from src.scheduler import run_scheduler
from src.handlers import (
    profile_handler,
    activity_handler,
    analytics_handler,
    report_handler,
    social_handler,
    goals_handler,
    reminders_handler,
    admin_handler,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Основна функція запуску бота."""
    logger.info("Запуск FitTrackBot...")

    # Ініціалізація таблиць БД
    await db_manager.create_tables()
    logger.info("Таблиці бази даних готові.")

    # Ініціалізація бота (Singleton)
    bot = Bot(token=config.bot_token, parse_mode=ParseMode.HTML)
    dp = Dispatcher(storage=MemoryStorage())

    # Реєстрація роутерів (Dispatcher — патерн Observer/Command)
    dp.include_router(admin_handler.router)       # першим — щоб /admin мав пріоритет
    dp.include_router(profile_handler.router)
    dp.include_router(activity_handler.router)
    dp.include_router(analytics_handler.router)
    dp.include_router(report_handler.router)
    dp.include_router(social_handler.router)
    dp.include_router(goals_handler.router)
    dp.include_router(reminders_handler.router)

    # Запускаємо планувальник нагадувань як фонову задачу asyncio
    scheduler_task = asyncio.create_task(run_scheduler(bot))
    logger.info("Планувальник нагадувань запущено як фонову задачу.")

    logger.info("Починаємо polling...")
    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )
    finally:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass
        await db_manager.close()
        await bot.session.close()
        logger.info("Бот зупинено.")


if __name__ == "__main__":
    asyncio.run(main())
