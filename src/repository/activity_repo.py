"""Репозиторій журналу фізичної активності."""

from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from src.models.domain import ActivityLog
from src.repository.base_repo import BaseRepository


class ActivityRepository(BaseRepository[ActivityLog]):
    """Репозиторій для роботи із записами тренувань."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ActivityLog, session)

    async def get_by_user(
        self, user_id: int, limit: int = 50
    ) -> list[ActivityLog]:
        """Повертає останні записи активності користувача."""
        result = await self._session.execute(
            select(ActivityLog)
            .where(ActivityLog.user_id == user_id)
            .order_by(ActivityLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_time_series(
        self, user_id: int, days: int = 90
    ) -> list[ActivityLog]:
        """Повертає часовий ряд активності для аналітики."""
        from datetime import timedelta
        cutoff = date.today() - timedelta(days=days)
        result = await self._session.execute(
            select(ActivityLog)
            .where(
                ActivityLog.user_id == user_id,
                func.date(ActivityLog.created_at) >= cutoff,
            )
            .order_by(ActivityLog.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_by_date_range(
        self, user_id: int, date_from: date, date_to: date
    ) -> list[ActivityLog]:
        """Повертає записи активності користувача за вказаний період."""
        result = await self._session.execute(
            select(ActivityLog)
            .where(
                ActivityLog.user_id == user_id,
                func.date(ActivityLog.created_at) >= date_from,
                func.date(ActivityLog.created_at) <= date_to,
            )
            .order_by(ActivityLog.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_total_calories(self, user_id: int) -> float:
        """Повертає загальну кількість спалених калорій."""
        result = await self._session.execute(
            select(func.sum(ActivityLog.calories_burned))
            .where(ActivityLog.user_id == user_id)
        )
        return result.scalar_one_or_none() or 0.0

    async def count_by_user(self, user_id: int) -> int:
        """Повертає кількість записів активності користувача."""
        result = await self._session.execute(
            select(func.count()).where(ActivityLog.user_id == user_id)
        )
        return result.scalar_one() or 0
