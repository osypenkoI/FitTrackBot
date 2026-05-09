"""
Доменні моделі FitTrackBot — ORM-класи для PostgreSQL через SQLAlchemy.
"""

from datetime import datetime, date
from sqlalchemy import (
    BigInteger, String, Float, Integer, Date, DateTime,
    ForeignKey, Enum as SAEnum, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum
from src.database.connection import Base


class ActivityLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class TargetGoal(str, enum.Enum):
    WEIGHT_LOSS = "weight_loss"
    MUSCLE_GAIN = "muscle_gain"
    MAINTAIN = "maintain"


class FriendshipStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class User(Base):
    """Користувач телеграм-боту."""
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    activity_level: Mapped[str] = mapped_column(
        SAEnum(ActivityLevel), default=ActivityLevel.MEDIUM
    )
    target_goal: Mapped[str] = mapped_column(
        SAEnum(TargetGoal), default=TargetGoal.MAINTAIN
    )
    registered_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    # Зв'язки
    body_metrics: Mapped[list["BodyMetrics"]] = relationship(back_populates="user")
    activity_logs: Mapped[list["ActivityLog"]] = relationship(back_populates="user")
    nutrition_logs: Mapped[list["NutritionLog"]] = relationship(back_populates="user")
    challenges_created: Mapped[list["Challenge"]] = relationship(back_populates="creator")
    challenge_participations: Mapped[list["ChallengeParticipant"]] = relationship(
        back_populates="user"
    )
    goals: Mapped[list["Goal"]] = relationship(back_populates="user")
    reminders: Mapped[list["Reminder"]] = relationship(back_populates="user")


class BodyMetrics(Base):
    """Антропометричні дані користувача."""
    __tablename__ = "body_metrics"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"))
    weight: Mapped[float] = mapped_column(Float)
    height: Mapped[float] = mapped_column(Float)
    age: Mapped[int] = mapped_column(Integer)
    gender: Mapped[str] = mapped_column(String(10), default="male")
    bmr: Mapped[float | None] = mapped_column(Float, nullable=True)
    tdee: Mapped[float | None] = mapped_column(Float, nullable=True)
    date_recorded: Mapped[date] = mapped_column(Date, server_default=func.current_date())

    user: Mapped["User"] = relationship(back_populates="body_metrics")


class ActivityLog(Base):
    """Журнал фізичної активності."""
    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"))
    activity_type: Mapped[str] = mapped_column(String(64))
    duration_minutes: Mapped[int] = mapped_column(Integer)
    calories_burned: Mapped[float] = mapped_column(Float)
    distance: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    repetitions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="activity_logs")


class NutritionLog(Base):
    """Журнал харчування."""
    __tablename__ = "nutrition_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"))
    meal_type: Mapped[str] = mapped_column(String(32))
    food_name: Mapped[str] = mapped_column(String(128))
    amount_grams: Mapped[float] = mapped_column(Float)
    calories_intake: Mapped[float] = mapped_column(Float)
    proteins: Mapped[float | None] = mapped_column(Float, nullable=True)
    fats: Mapped[float | None] = mapped_column(Float, nullable=True)
    carbohydrates: Mapped[float | None] = mapped_column(Float, nullable=True)
    date: Mapped[date] = mapped_column(Date, server_default=func.current_date())

    user: Mapped["User"] = relationship(back_populates="nutrition_logs")


class Challenge(Base):
    """Челендж між користувачами."""
    __tablename__ = "challenges"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    creator_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"))
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    goal_value: Mapped[float] = mapped_column(Float)
    metric: Mapped[str] = mapped_column(String(64))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    creator: Mapped["User"] = relationship(back_populates="challenges_created")
    participants: Mapped[list["ChallengeParticipant"]] = relationship(
        back_populates="challenge"
    )


class ChallengeParticipant(Base):
    """Учасник челенджу."""
    __tablename__ = "challenge_participants"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    challenge_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("challenges.id"))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"))
    joined_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    progress: Mapped[float] = mapped_column(Float, default=0.0)

    challenge: Mapped["Challenge"] = relationship(back_populates="participants")
    user: Mapped["User"] = relationship(back_populates="challenge_participations")


class Goal(Base):
    """Персональна ціль користувача."""
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"))
    goal_type: Mapped[str] = mapped_column(String(64))   # workouts_per_week, calories_per_day тощо
    target_value: Mapped[float] = mapped_column(Float)
    current_value: Mapped[float] = mapped_column(Float, default=0.0)
    period_days: Mapped[int] = mapped_column(Integer, default=30)
    start_date: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    end_date: Mapped[date] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="goals")


class Reminder(Base):
    """Налаштування нагадувань."""
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"))
    reminder_type: Mapped[str] = mapped_column(String(32))   # workout / nutrition / all
    days_of_week: Mapped[str] = mapped_column(String(20))    # "1,3,5" — пн,ср,пт
    remind_time: Mapped[str] = mapped_column(String(5))      # "17:00"
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="reminders")


class Friendship(Base):
    """Дружні зв'язки між користувачами."""
    __tablename__ = "friendships"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    requester_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"))
    addressee_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"))
    status: Mapped[str] = mapped_column(
        SAEnum(FriendshipStatus), default=FriendshipStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
