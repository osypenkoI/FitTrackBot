"""Сервіс адміністративних функцій FitTrackBot."""

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.domain import User, ActivityLog


class AdminService:
    """Бізнес-логіка адміністративних функцій."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_statistics(self) -> dict:
        """Повертає загальну статистику використання телеграм-боту."""
        total_users_result = await self._session.execute(
            select(func.count()).select_from(User)
        )
        total_users = total_users_result.scalar_one() or 0

        active_result = await self._session.execute(
            text("""
                SELECT COUNT(DISTINCT user_id)
                FROM activity_logs
                WHERE created_at >= NOW() - INTERVAL '7 days'
            """)
        )
        active_7d = active_result.scalar_one() or 0

        total_logs_result = await self._session.execute(
            select(func.count()).select_from(ActivityLog)
        )
        total_logs = total_logs_result.scalar_one() or 0

        new_today_result = await self._session.execute(
            text("""
                SELECT COUNT(*)
                FROM users
                WHERE DATE(registered_at) = CURRENT_DATE
            """)
        )
        new_today = new_today_result.scalar_one() or 0

        return {
            "total_users": total_users,
            "active_7d": active_7d,
            "new_today": new_today,
            "total_logs": total_logs,
        }

    async def get_all_user_ids(self) -> list[int]:
        """Повертає список Telegram ID усіх користувачів."""
        result = await self._session.execute(select(User.user_id))
        return [row[0] for row in result.all()]

    async def block_user(self, target_id: int) -> bool:
        """Видаляє користувача з бази даних за Telegram ID."""
        user = await self._session.get(User, target_id)
        if user is None:
            return False

        await self._session.delete(user)
        await self._session.commit()
        return True