"""
Модуль підключення до бази даних PostgreSQL через SQLAlchemy (async).
Реалізує патерн Singleton для менеджера підключення.
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from src.config import config


class Base(DeclarativeBase):
    """Базовий клас для всіх ORM-моделей."""
    pass


class DatabaseManager:
    """
    Менеджер підключення до бази даних.
    Патерн Singleton — гарантує єдиний екземпляр пулу з'єднань.
    """

    _instance: "DatabaseManager | None" = None

    def __new__(cls) -> "DatabaseManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._engine = create_async_engine(
            config.database_url,
            echo=False,
            pool_size=10,
            max_overflow=20,
        )
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        self._initialized = True

    @property
    def session_factory(self) -> async_sessionmaker:
        return self._session_factory

    async def create_tables(self) -> None:
        """Створює всі таблиці в базі даних."""
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        """Закриває пул з'єднань."""
        await self._engine.dispose()


# Глобальний екземпляр менеджера БД (Singleton)
db_manager = DatabaseManager()
