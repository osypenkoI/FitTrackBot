"""Репозиторій для аналітичних запитів."""

from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class AnalyticsRepository:
    """Репозиторій аналітичних запитів до бази даних."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_weekly_summary(self, user_id: int) -> list[dict]:
        """Повертає тижневу агрегацію активності."""
        stmt = text(
            """
            SELECT
                DATE_TRUNC('week', created_at) AS week,
                SUM(calories_burned)           AS total_calories,
                SUM(duration_minutes)          AS total_minutes,
                COUNT(*)                       AS sessions
            FROM activity_logs
            WHERE user_id = :uid
            GROUP BY week
            ORDER BY week ASC
            """
        )
        result = await self._session.execute(stmt, {"uid": user_id})
        return [dict(row._mapping) for row in result.all()]

    async def get_activity_distribution(self, user_id: int) -> list[dict]:
        """Повертає розподіл за типами активності."""
        stmt = text(
            """
            SELECT
                activity_type,
                COUNT(*)             AS count,
                SUM(calories_burned) AS total_calories
            FROM activity_logs
            WHERE user_id = :uid
            GROUP BY activity_type
            ORDER BY count DESC
            """
        )
        result = await self._session.execute(stmt, {"uid": user_id})
        return [dict(row._mapping) for row in result.all()]

    async def get_leaderboard(self, metric: str = "calories_burned") -> list[dict]:
        """
        Повертає топ-10 користувачів за обраною метрикою за останні 7 днів.

        Підтримувані метрики:
        - calories_burned: сума спалених калорій;
        - duration_minutes: сумарна тривалість тренувань;
        - workouts_count: кількість тренувань.
        """
        allowed_metrics = {
            "calories_burned",
            "duration_minutes",
            "workouts_count",
        }

        if metric not in allowed_metrics:
            metric = "calories_burned"

        date_from = datetime.now() - timedelta(days=7)

        if metric == "duration_minutes":
            value_expression = "COALESCE(SUM(a.duration_minutes), 0)"
            order_expression = "COALESCE(SUM(a.duration_minutes), 0)"
        elif metric == "workouts_count":
            value_expression = "COUNT(a.id)"
            order_expression = "COUNT(a.id)"
        else:
            value_expression = "COALESCE(SUM(a.calories_burned), 0)"
            order_expression = "COALESCE(SUM(a.calories_burned), 0)"

        stmt = text(
            f"""
            SELECT
                u.user_id,
                COALESCE(u.username, CONCAT('user_', u.user_id)) AS username,
                {value_expression} AS value
            FROM users u
            JOIN activity_logs a ON u.user_id = a.user_id
            WHERE a.created_at >= :date_from
            GROUP BY u.user_id, u.username
            ORDER BY {order_expression} DESC
            LIMIT 10
            """
        )

        result = await self._session.execute(stmt, {"date_from": date_from})
        rows = result.all()

        return [
            {
                "user_id": row.user_id,
                "username": row.username,
                "value": float(row.value or 0),
                "metric": metric,
            }
            for row in rows
        ]