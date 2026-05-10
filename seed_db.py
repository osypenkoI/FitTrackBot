"""
seed_db.py — скрипт наповнення бази даних тестовими даними для тестування обсягом.

Генерує:
  - NUM_USERS користувачів з антропометричними даними
  - NUM_ACTIVITY_LOGS записів активності (розподілених між користувачами)
  - NUM_NUTRITION_LOGS записів харчування
  - NUM_GOALS цілей

Використання:
    python seed_db.py

Змінні середовища (файл .env):
    DATABASE_URL — рядок підключення до PostgreSQL
"""

import asyncio
import random
import os
import sys
from datetime import datetime, date, timedelta

# Додаємо кореневу директорію до PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from src.models.domain import (
    Base, User, BodyMetrics, ActivityLog, NutritionLog, Goal,
    ActivityLevel, TargetGoal
)

# ===== ПАРАМЕТРИ НАПОВНЕННЯ =====
NUM_USERS = 10
RECORDS_PER_USER = 10_000   # 10 000 записів на користувача → ~100 000 загалом
BATCH_SIZE = 500            # розмір пакету для вставки

ACTIVITY_TYPES = ["running", "cardio", "strength", "yoga", "cycling", "swimming", "walking"]
MEAL_TYPES = ["breakfast", "lunch", "dinner", "snack"]
FOOD_NAMES = ["Вівсянка", "Куряча грудка", "Гречка", "Яйця", "Салат", "Рис", "Банан", "Творог"]
GOAL_TYPES = ["calories_per_day", "workouts_per_week", "calories_burned_total", "duration_minutes_total"]
ACTIVITY_LEVELS = [a.value for a in ActivityLevel]
TARGET_GOALS = [t.value for t in TargetGoal]


def random_date(days_back: int = 365) -> date:
    """Повертає випадкову дату за останній рік."""
    return date.today() - timedelta(days=random.randint(0, days_back))


def random_datetime(days_back: int = 365) -> datetime:
    """Повертає випадковий datetime за останній рік."""
    return datetime.now() - timedelta(
        days=random.randint(0, days_back),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59)
    )


async def seed(database_url: str) -> None:
    """Основна функція наповнення бази даних."""
    engine = create_async_engine(database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print(f"Створення {NUM_USERS} користувачів...")
    user_ids = []

    async with session_factory() as session:
        for i in range(NUM_USERS):
            user_id = 900_000_000 + i
            user = User(
                user_id=user_id,
                username=f"test_user_{i}",
                phone_number=f"+38050{str(i).zfill(7)}",
                activity_level=random.choice(ACTIVITY_LEVELS),
                target_goal=random.choice(TARGET_GOALS),
                registered_at=random_datetime(365),
            )
            session.add(user)
            user_ids.append(user_id)

            weight = round(random.uniform(55.0, 110.0), 1)
            height = round(random.uniform(160.0, 195.0), 1)
            age = random.randint(18, 60)
            gender = random.choice(["male", "female"])
            base = 10 * weight + 6.25 * height - 5 * age
            bmr = round(base + 5 if gender == "male" else base - 161, 2)
            tdee = round(bmr * 1.375, 2)

            metrics = BodyMetrics(
                user_id=user_id,
                weight=weight,
                height=height,
                age=age,
                gender=gender,
                bmr=bmr,
                tdee=tdee,
                date_recorded=random_date(30),
            )
            session.add(metrics)

        await session.commit()
    print(f"  ✓ {NUM_USERS} користувачів створено")

    # ===== ACTIVITY LOGS =====
    total_activity = NUM_USERS * RECORDS_PER_USER
    print(f"Генерація {total_activity:,} записів активності...")

    batch = []
    count = 0
    async with session_factory() as session:
        for user_id in user_ids:
            for _ in range(RECORDS_PER_USER):
                duration = random.randint(15, 120)
                weight_kg = round(random.uniform(55.0, 110.0), 1)
                coeff = {"running": 10.0, "cardio": 8.0, "strength": 5.0,
                         "yoga": 3.0, "cycling": 7.0, "swimming": 9.0, "walking": 4.0}
                activity_type = random.choice(ACTIVITY_TYPES)
                calories = round(coeff[activity_type] * (weight_kg / 70) * duration, 2)

                batch.append(ActivityLog(
                    user_id=user_id,
                    activity_type=activity_type,
                    duration_minutes=duration,
                    calories_burned=calories,
                    distance=round(random.uniform(1.0, 20.0), 2) if activity_type in ["running", "cycling", "walking"] else None,
                    weight_kg=weight_kg,
                    created_at=random_datetime(365),
                ))
                count += 1

                if len(batch) >= BATCH_SIZE:
                    session.add_all(batch)
                    await session.commit()
                    batch = []
                    print(f"  {count:,} / {total_activity:,} записів активності...", end="\r")

        if batch:
            session.add_all(batch)
            await session.commit()
    print(f"\n  ✓ {total_activity:,} записів активності створено")

    # ===== NUTRITION LOGS =====
    total_nutrition = NUM_USERS * RECORDS_PER_USER
    print(f"Генерація {total_nutrition:,} записів харчування...")

    batch = []
    count = 0
    async with session_factory() as session:
        for user_id in user_ids:
            for _ in range(RECORDS_PER_USER):
                amount = round(random.uniform(50.0, 500.0), 1)
                calories = round(amount * random.uniform(1.0, 5.0), 2)

                batch.append(NutritionLog(
                    user_id=user_id,
                    meal_type=random.choice(MEAL_TYPES),
                    food_name=random.choice(FOOD_NAMES),
                    amount_grams=amount,
                    calories_intake=calories,
                    proteins=round(random.uniform(2.0, 40.0), 1),
                    fats=round(random.uniform(1.0, 30.0), 1),
                    carbohydrates=round(random.uniform(5.0, 80.0), 1),
                    date=random_date(365),
                ))
                count += 1

                if len(batch) >= BATCH_SIZE:
                    session.add_all(batch)
                    await session.commit()
                    batch = []
                    print(f"  {count:,} / {total_nutrition:,} записів харчування...", end="\r")

        if batch:
            session.add_all(batch)
            await session.commit()
    print(f"\n  ✓ {total_nutrition:,} записів харчування створено")

    # ===== GOALS =====
    print(f"Генерація цілей...")
    async with session_factory() as session:
        for user_id in user_ids:
            for goal_type in GOAL_TYPES:
                start = random_date(60)
                end = start + timedelta(days=random.choice([7, 14, 30]))
                session.add(Goal(
                    user_id=user_id,
                    goal_type=goal_type,
                    target_value=round(random.uniform(5.0, 100.0), 1),
                    current_value=round(random.uniform(0.0, 80.0), 1),
                    period_days=30,
                    start_date=start,
                    end_date=end,
                    is_active=random.choice([True, False]),
                    created_at=random_datetime(60),
                ))
        await session.commit()
    print(f"  ✓ Цілі створено")

    await engine.dispose()

    total = total_activity + total_nutrition
    print(f"\n{'='*50}")
    print(f"Наповнення завершено!")
    print(f"  Користувачів:          {NUM_USERS:>10,}")
    print(f"  Записів активності:    {total_activity:>10,}")
    print(f"  Записів харчування:    {total_nutrition:>10,}")
    print(f"  Всього записів у БД:   {total:>10,}")
    print(f"{'='*50}")


if __name__ == "__main__":
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("Помилка: DATABASE_URL не встановлено у .env")
        sys.exit(1)
    asyncio.run(seed(database_url))
