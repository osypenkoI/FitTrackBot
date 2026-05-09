"""
DTO-об'єкти FitTrackBot для передачі даних між шарами та валідації через Pydantic.
"""

from datetime import date, datetime
from pydantic import BaseModel, Field, field_validator
from typing import Optional


# ── Вхідні DTO ────────────────────────────────────────────────────────────────

class UserRegistrationDTO(BaseModel):
    """DTO реєстрації нового користувача."""
    telegram_id: int
    username: Optional[str] = None
    phone_number: Optional[str] = None
    weight: float = Field(gt=20, lt=500, description="Вага в кг")
    height: float = Field(gt=50, lt=300, description="Зріст в см")
    age: int = Field(gt=5, lt=120, description="Вік у роках")
    gender: str = Field(pattern="^(male|female)$")
    activity_level: str = Field(
        pattern="^(low|medium|high|very_high)$"
    )
    target_goal: str = Field(
        pattern="^(weight_loss|muscle_gain|maintain)$"
    )

    @field_validator("weight", "height")
    @classmethod
    def round_float(cls, v: float) -> float:
        return round(v, 1)


class ActivityInputDTO(BaseModel):
    """DTO введення фізичної активності."""
    user_id: int
    activity_type: str = Field(min_length=2, max_length=64)
    duration_minutes: int = Field(gt=0, lt=1440)
    distance: Optional[float] = Field(default=None, gt=0)
    weight_kg: Optional[float] = Field(default=None, gt=0)
    repetitions: Optional[int] = Field(default=None, gt=0)
    created_at: Optional[datetime] = None

    @field_validator("activity_type")
    @classmethod
    def validate_activity_type(cls, v: str) -> str:
        allowed = {
            "cardio", "strength", "yoga", "cycling",
            "swimming", "running", "walking", "other"
        }
        if v.lower() not in allowed:
            raise ValueError(f"Невідомий тип активності: {v}")
        return v.lower()


class NutritionInputDTO(BaseModel):
    """DTO введення даних про харчування."""
    user_id: int
    meal_type: str = Field(pattern="^(breakfast|lunch|dinner|snack)$")
    food_name: str = Field(min_length=1, max_length=128)
    amount_grams: float = Field(gt=0, lt=5000)
    calories_intake: float = Field(gt=0, lt=10000)
    proteins: Optional[float] = Field(default=None, ge=0)
    fats: Optional[float] = Field(default=None, ge=0)
    carbohydrates: Optional[float] = Field(default=None, ge=0)
    date: Optional[date] = None


class ChallengeCreateDTO(BaseModel):
    """DTO створення челенджу."""
    creator_id: int
    title: str = Field(min_length=3, max_length=128)
    description: Optional[str] = Field(default=None, max_length=512)
    goal_value: float = Field(gt=0)
    metric: str = Field(min_length=2, max_length=64)
    start_date: date
    end_date: date

    @field_validator("end_date")
    @classmethod
    def end_after_start(cls, v: date, info) -> date:
        if "start_date" in info.data and v <= info.data["start_date"]:
            raise ValueError("Дата завершення має бути пізніше дати початку")
        return v


class FriendRequestDTO(BaseModel):
    """DTO запиту дружби."""
    requester_id: int
    addressee_phone: str = Field(min_length=7, max_length=20)


# ── Вихідні DTO ───────────────────────────────────────────────────────────────

class ForecastRequestDTO(BaseModel):
    """DTO запиту прогнозу активності."""
    user_id: int
    days_ahead: int = Field(default=14, gt=0, lt=90)
    metric: str = Field(default="calories_burned")


class ReportRequestDTO(BaseModel):
    """DTO запиту звіту."""
    user_id: int
    format: str = Field(pattern="^(pdf|excel)$")
    date_from: date
    date_to: date
