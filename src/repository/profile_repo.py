"""Репозиторій профілю користувача."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.models.domain import User, BodyMetrics
from src.repository.base_repo import BaseRepository


class ProfileRepository(BaseRepository[User]):
    """Репозиторій для роботи з профілями користувачів."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(User, session)

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        """Знаходить користувача за Telegram ID."""
        result = await self._session.execute(
            select(User).where(User.user_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_by_phone(self, phone: str) -> User | None:
        """Знаходить користувача за номером телефону."""
        result = await self._session.execute(
            select(User).where(User.phone_number == phone)
        )
        return result.scalar_one_or_none()

    async def get_latest_metrics(self, user_id: int) -> BodyMetrics | None:
        """Повертає останній запис антропометричних даних."""
        result = await self._session.execute(
            select(BodyMetrics)
            .where(BodyMetrics.user_id == user_id)
            .order_by(BodyMetrics.date_recorded.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def save_metrics(self, metrics: BodyMetrics) -> BodyMetrics:
        """Зберігає антропометричні дані."""
        self._session.add(metrics)
        await self._session.commit()
        await self._session.refresh(metrics)
        return metrics
