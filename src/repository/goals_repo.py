"""Репозиторій персональних цілей та нагадувань."""

from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from src.models.domain import Goal, Reminder
from src.repository.base_repo import BaseRepository


class GoalsRepository(BaseRepository[Goal]):
    """Репозиторій для роботи з персональними цілями."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Goal, session)

    async def get_active_goals(self, user_id: int) -> list[Goal]:
        """Повертає активні цілі користувача."""
        result = await self._session.execute(
            select(Goal).where(
                Goal.user_id == user_id,
                Goal.is_active == True,
            ).order_by(Goal.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_all_goals(self, user_id: int) -> list[Goal]:
        """Повертає всі цілі користувача."""
        result = await self._session.execute(
            select(Goal)
            .where(Goal.user_id == user_id)
            .order_by(Goal.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_progress(self, goal_id: int, value: float) -> None:
        """Оновлює поточний прогрес цілі."""
        await self._session.execute(
            update(Goal)
            .where(Goal.id == goal_id)
            .values(current_value=value)
        )
        await self._session.commit()

    async def deactivate_goal(self, goal_id: int, user_id: int) -> bool:
        """Деактивує ціль (м'яке видалення)."""
        result = await self._session.execute(
            select(Goal).where(Goal.id == goal_id, Goal.user_id == user_id)
        )
        goal = result.scalar_one_or_none()
        if not goal:
            return False
        goal.is_active = False
        await self._session.commit()
        return True


class ReminderRepository(BaseRepository[Reminder]):
    """Репозиторій нагадувань."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Reminder, session)

    async def get_user_reminders(self, user_id: int) -> list[Reminder]:
        """Повертає всі активні нагадування користувача."""
        result = await self._session.execute(
            select(Reminder).where(
                Reminder.user_id == user_id,
                Reminder.is_active == True,
            )
        )
        return list(result.scalars().all())

    async def deactivate_by_type(self, user_id: int, reminder_type: str) -> None:
        """Вимикає нагадування певного типу."""
        await self._session.execute(
            update(Reminder)
            .where(
                Reminder.user_id == user_id,
                Reminder.reminder_type == reminder_type,
            )
            .values(is_active=False)
        )
        await self._session.commit()

    async def deactivate_all(self, user_id: int) -> None:
        """Вимикає всі нагадування користувача."""
        await self._session.execute(
            update(Reminder)
            .where(Reminder.user_id == user_id)
            .values(is_active=False)
        )
        await self._session.commit()
