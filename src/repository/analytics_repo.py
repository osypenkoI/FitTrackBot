"""Репозиторій для кешування результатів аналітики."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from src.repository.base_repo import BaseRepository
from src.models.domain import ActivityLog


class AnalyticsRepository:
    """Репозиторій аналітичних запитів до бази даних."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_weekly_summary(self, user_id: int) -> list[dict]:
        """Повертає тижневу агрегацію активності."""
        stmt = text("""
            SELECT
                DATE_TRUNC('week', created_at) AS week,
                SUM(calories_burned)           AS total_calories,
                SUM(duration_minutes)          AS total_minutes,
                COUNT(*)                       AS sessions
            FROM activity_logs
            WHERE user_id = :uid
            GROUP BY week
            ORDER BY week ASC
        """)
        result = await self._session.execute(stmt, {"uid": user_id})
        return [dict(row._mapping) for row in result.all()]

    async def get_activity_distribution(self, user_id: int) -> list[dict]:
        """Повертає розподіл за типами активності."""
        stmt = text("""
            SELECT
                activity_type,
                COUNT(*)             AS count,
                SUM(calories_burned) AS total_calories
            FROM activity_logs
            WHERE user_id = :uid
            GROUP BY activity_type
            ORDER BY count DESC
        """)
        result = await self._session.execute(stmt, {"uid": user_id})
        return [dict(row._mapping) for row in result.all()]

    async def get_leaderboard(self, metric: str = "calories_burned") -> list[dict]:
        """Повертає топ-10 користувачів за обраною метрикою."""
        allowed = {"calories_burned", "duration_minutes"}
        if metric not in allowed:
            metric = "calories_burned"
        stmt = text(f"""
            SELECT
                u.user_id,
                u.username,
                SUM(a.{metric}) AS total
            FROM users u
            JOIN activity_logs a ON u.user_id = a.user_id
            GROUP BY u.user_id, u.username
            ORDER BY total DESC
            LIMIT 10
        """)
        result = await self._session.execute(stmt)
        return [dict(row._mapping) for row in result.all()]
