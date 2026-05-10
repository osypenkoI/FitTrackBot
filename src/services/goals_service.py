"""
Сервіс персональних цілей.
Реалізує ФВ 6.1.1 – 6.1.4: встановлення, відстеження, оновлення та видалення цілей.
"""

from datetime import date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.domain import Goal, Reminder
from src.repository.goals_repo import GoalsRepository, ReminderRepository
from src.repository.activity_repo import ActivityRepository
from src.repository.nutrition_repo import NutritionRepository


GOAL_TYPES = {
    "workouts_per_week": "Тренувань на тиждень",
    "calories_per_day": "Калорій на день",
    "calories_burned_total": "Всього спалити ккал",
    "duration_minutes_total": "Всього хвилин тренувань",
}

PERIOD_MAP = {
    "1 тиждень": 7,
    "2 тижні": 14,
    "1 місяць": 30,
}


class GoalsService:
    """Сервіс управління персональними цілями."""

    def __init__(self, session: AsyncSession) -> None:
        self._goals_repo = GoalsRepository(session)
        self._activity_repo = ActivityRepository(session)
        self._nutrition_repo = NutritionRepository(session)

    async def create_goal(
        self,
        user_id: int,
        goal_type: str,
        target_value: float,
        period_days: int = 30,
    ) -> tuple[Goal | None, str]:
        """
        Створює нову персональну ціль (ФВ 6.1.1).
        Повертає (Goal, '') при успіху або (None, повідомлення_помилки).
        """
        if goal_type not in GOAL_TYPES:
            return None, f"Невідомий тип цілі. Допустимі: {', '.join(GOAL_TYPES.keys())}"
        if target_value <= 0:
            return None, "Значення цілі має бути більше нуля."

        end_date = date.today() + timedelta(days=period_days)
        goal = Goal(
            user_id=user_id,
            goal_type=goal_type,
            target_value=target_value,
            current_value=0.0,
            period_days=period_days,
            end_date=end_date,
        )
        saved = await self._goals_repo.save(goal)
        return saved, ""

    async def get_goals_with_progress(self, user_id: int) -> list[dict]:
        """
        Повертає активні цілі з актуальним прогресом (ФВ 6.1.2).
        Автоматично перераховує поточне значення з бази даних.
        """
        goals = await self._goals_repo.get_active_goals(user_id)
        result = []
        for goal in goals:
            current = await self._calculate_current(user_id, goal)
            await self._goals_repo.update_progress(goal.id, current)
            progress_pct = min(100.0, round(current / goal.target_value * 100, 1))
            days_left = (goal.end_date - date.today()).days

            result.append({
                "goal": goal,
                "current": round(current, 1),
                "progress_pct": progress_pct,
                "days_left": max(0, days_left),
                "is_done": current >= goal.target_value,
                "at_risk": progress_pct < 50 and days_left <= 3,
            })
        return result

    async def _calculate_current(self, user_id: int, goal: Goal) -> float:
        """Розраховує поточне значення прогресу за типом цілі."""
        if goal.goal_type == "workouts_per_week":
            records = await self._activity_repo.get_time_series(user_id, days=7)
            return float(len(records))
        if goal.goal_type == "calories_per_day":
            from datetime import date as dt
            daily = await self._nutrition_repo.get_daily_calories(user_id, dt.today())
            return daily
        if goal.goal_type == "calories_burned_total":
            records = await self._activity_repo.get_time_series(user_id, days=goal.period_days)
            return sum(r.calories_burned for r in records)
        if goal.goal_type == "duration_minutes_total":
            records = await self._activity_repo.get_time_series(user_id, days=goal.period_days)
            return float(sum(r.duration_minutes for r in records))
        return 0.0

    async def check_goal_notifications(self, user_id: int) -> list[str]:
        """
        Перевіряє цілі та повертає список сповіщень (ФВ 6.1.3).
        Сповіщає про досягнення або ризик невиконання.
        """
        goals_data = await self.get_goals_with_progress(user_id)
        notifications = []
        for item in goals_data:
            goal = item["goal"]
            name = GOAL_TYPES.get(goal.goal_type, goal.goal_type)
            if item["is_done"]:
                notifications.append(
                    f"🎉 Ціль досягнуто: «{name}» — {item['current']} / {goal.target_value}!"
                )
            elif item["at_risk"]:
                notifications.append(
                    f"⚠️ Ризик не виконати ціль «{name}»: "
                    f"{item['progress_pct']}% за {item['days_left']} дн."
                )
        return notifications

    async def delete_goal(self, goal_id: int, user_id: int) -> bool:
        """Видаляє (деактивує) ціль (ФВ 6.1.4)."""
        return await self._goals_repo.deactivate_goal(goal_id, user_id)

    async def get_all_goals(self, user_id: int) -> list[Goal]:
        """Повертає всі цілі користувача для перегляду та редагування."""
        return await self._goals_repo.get_all_goals(user_id)
    
    async def update_goal(
        self,
        user_id: int,
        goal_id: int,
        field: str,
        value,
    ) -> bool:
        """Оновлює ціль користувача."""
        goal = await self._goals_repo.get_by_id(goal_id)

        if not goal or goal.user_id != user_id:
            return False

        setattr(goal, field, value)

        if field == "period_days":
            goal.end_date = date.today() + timedelta(days=value)

        await self._goals_repo.save(goal)
        return True


class ReminderService:
    """Сервіс управління нагадуваннями (ФВ 5.2.1)."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = ReminderRepository(session)

    async def set_reminder(
        self,
        user_id: int,
        reminder_type: str,
        days_of_week: list[int],
        remind_time: str,
    ) -> tuple[Reminder | None, str]:
        """
        Зберігає нагадування.
        days_of_week: список чисел 1-7 (1=пн, 7=нд).
        remind_time: рядок у форматі 'ГГ:ХХ', наприклад '17:00'.
        """
        if reminder_type not in ("workout", "nutrition", "all"):
            return None, "Невідомий тип нагадування."
        if not days_of_week:
            return None, "Оберіть хоча б один день тижня."
        # Валідація формату часу
        try:
            h, m = remind_time.split(":")
            if not (0 <= int(h) <= 23 and 0 <= int(m) <= 59):
                raise ValueError
        except ValueError:
            return None, "Невірний формат часу. Введіть у форматі ГГ:ХХ (наприклад 17:00)."

        # Перед створенням нового нагадування вимикаємо попереднє такого ж типу,
        # щоб у користувача не накопичувались дублікати.
        await self._repo.deactivate_by_type(user_id, reminder_type)

        days_str = ",".join(str(d) for d in sorted(days_of_week))
        reminder = Reminder(
            user_id=user_id,
            reminder_type=reminder_type,
            days_of_week=days_str,
            remind_time=remind_time,
        )
        saved = await self._repo.save(reminder)
        return saved, ""

    async def get_reminders(self, user_id: int) -> list[Reminder]:
        return await self._repo.get_user_reminders(user_id)

    async def disable_by_type(self, user_id: int, reminder_type: str) -> None:
        await self._repo.deactivate_by_type(user_id, reminder_type)

    async def disable_all(self, user_id: int) -> None:
        await self._repo.deactivate_all(user_id)
