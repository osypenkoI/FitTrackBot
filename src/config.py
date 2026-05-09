"""
Модуль конфігурації FitTrackBot.
Завантажує змінні середовища та надає централізований доступ до параметрів.
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    """Клас конфігурації телеграм-боту FitTrackBot."""

    bot_token: str
    database_url: str
    admin_ids: list[int]

    # Параметри аналітики
    min_records_forecast: int = 7
    min_records_anomaly: int = 20
    forecast_days: int = 14
    anomaly_contamination: float = 0.1

    @classmethod
    def from_env(cls) -> "Config":
        """Створює екземпляр Config із змінних середовища."""
        token = os.getenv("BOT_TOKEN")
        if not token:
            raise ValueError("BOT_TOKEN не встановлено у .env")

        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise ValueError("DATABASE_URL не встановлено у .env")

        admin_str = os.getenv("ADMIN_IDS", "")
        admin_ids = [int(x) for x in admin_str.split(",") if x.strip()]

        return cls(bot_token=token, database_url=db_url, admin_ids=admin_ids)


# Singleton — єдиний екземпляр конфігурації (патерн Singleton)
config = Config.from_env()
