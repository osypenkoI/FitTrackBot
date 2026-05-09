"""Репозиторій журналу харчування."""

from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from src.models.domain import NutritionLog
from src.repository.base_repo import BaseRepository


class NutritionRepository(BaseRepository[NutritionLog]):
    """Репозиторій для роботи із записами харчування."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(NutritionLog, session)

    async def get_by_user(
        self, user_id: int, limit: int = 50
    ) -> list[NutritionLog]:
        """Повертає останні записи харчування."""
        result = await self._session.execute(
            select(NutritionLog)
            .where(NutritionLog.user_id == user_id)
            .order_by(NutritionLog.date.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_daily_calories(self, user_id: int, day: date) -> float:
        """Повертає сумарні калорії за конкретний день."""
        result = await self._session.execute(
            select(func.sum(NutritionLog.calories_intake))
            .where(
                NutritionLog.user_id == user_id,
                NutritionLog.date == day,
            )
        )
        return result.scalar_one_or_none() or 0.0

    async def get_by_date_range(
        self, user_id: int, date_from: date, date_to: date
    ) -> list[NutritionLog]:
        """Повертає записи в заданому діапазоні дат."""
        result = await self._session.execute(
            select(NutritionLog)
            .where(
                NutritionLog.user_id == user_id,
                NutritionLog.date >= date_from,
                NutritionLog.date <= date_to,
            )
            .order_by(NutritionLog.date.asc())
        )
        return list(result.scalars().all())
