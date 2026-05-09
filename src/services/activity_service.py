"""
Сервіс обліку фізичної активності та харчування.
"""

from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.domain import ActivityLog, NutritionLog
from src.models.dto import ActivityInputDTO, NutritionInputDTO
from src.repository.activity_repo import ActivityRepository
from src.repository.nutrition_repo import NutritionRepository
from src.validators.pydantic_validator import PydanticValidator


# Калорій на хвилину для кожного типу активності (MET * вага/60)
CALORIES_PER_MINUTE: dict[str, float] = {
    "cardio": 8.0,
    "strength": 5.0,
    "yoga": 3.0,
    "cycling": 7.5,
    "swimming": 9.0,
    "running": 10.0,
    "walking": 4.0,
    "other": 5.0,
}


class ActivityService:
    """
    Сервіс фіксації тренувань та харчування.
    Патерн Dependency Injection — сесія передається ззовні.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._activity_repo = ActivityRepository(session)
        self._nutrition_repo = NutritionRepository(session)
        self._validator = PydanticValidator()

    def estimate_calories(
        self, activity_type: str, duration_minutes: int, weight_kg: float = 70.0
    ) -> float:
        """
        Розраховує орієнтовну кількість спалених калорій.
        Формула: коефіцієнт * (вага / 70) * тривалість
        """
        coeff = CALORIES_PER_MINUTE.get(activity_type.lower(), 5.0)
        return round(coeff * (weight_kg / 70.0) * duration_minutes, 1)

    async def log_activity(
        self, data: dict, user_weight: float = 70.0
    ) -> tuple[ActivityLog | None, str]:
        """
        Зберігає запис про тренування.
        Автоматично розраховує калорії якщо не вказано вручну.
        """
        dto, error = self._validator.validate_activity(data)
        if error:
            return None, error

        calories = self.estimate_calories(
            dto.activity_type, dto.duration_minutes, user_weight
        )

        log = ActivityLog(
            user_id=dto.user_id,
            activity_type=dto.activity_type,
            duration_minutes=dto.duration_minutes,
            calories_burned=calories,
            distance=dto.distance,
            weight_kg=dto.weight_kg,
            repetitions=dto.repetitions,
            created_at=dto.created_at or datetime.now(),
        )
        saved = await self._activity_repo.save(log)
        return saved, ""

    async def log_nutrition(
        self, data: dict
    ) -> tuple[NutritionLog | None, str]:
        """Зберігає запис про харчування."""
        dto, error = self._validator.validate_nutrition(data)
        if error:
            return None, error

        from datetime import date
        log = NutritionLog(
            user_id=dto.user_id,
            meal_type=dto.meal_type,
            food_name=dto.food_name,
            amount_grams=dto.amount_grams,
            calories_intake=dto.calories_intake,
            proteins=dto.proteins,
            fats=dto.fats,
            carbohydrates=dto.carbohydrates,
            date=dto.date or date.today(),
        )
        saved = await self._nutrition_repo.save(log)
        return saved, ""

    async def get_history(self, user_id: int, history_type: str) -> list:
        """Повертає історію активності або харчування."""
        if history_type == "activity":
            return await self._activity_repo.get_by_user(user_id)
        return await self._nutrition_repo.get_by_user(user_id)

    async def delete_record(
        self, record_id: int, record_type: str
    ) -> bool:
        """Видаляє запис із журналу."""
        if record_type == "activity":
            return await self._activity_repo.delete_by_id(record_id)
        return await self._nutrition_repo.delete_by_id(record_id)
