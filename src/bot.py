"""
Точка входу FitTrackBot.
Ініціалізує Dispatcher, реєструє всі роутери,
запускає планувальник нагадувань як фонову задачу.
"""

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, MenuButtonCommands
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
    navigation_handler,
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

    # Налаштування системної кнопки Telegram Menu та базових команд.
    # Команда /menu доступна з будь-якого сценарію та скидає поточний FSM-стан.
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Запустити бота"),
            BotCommand(command="menu", description="Повернутися до головного меню"),
        ]
    )
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())

    # Реєстрація роутерів (Dispatcher — патерн Observer/Command)
    dp.include_router(navigation_handler.router)  # першим — глобальне повернення в меню
    dp.include_router(admin_handler.router)       # /admin має власний доступ
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