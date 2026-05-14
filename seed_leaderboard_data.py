"""Додає тестових користувачів і записи активності для скріншота лідерборду."""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import text

from src.database.connection import db_manager


async def get_enum_defaults(session) -> tuple[str, str]:
    """Бере коректні enum-значення activity_level і target_goal з існуючого користувача."""
    result = await session.execute(
        text(
            """
            SELECT activity_level::text AS activity_level,
                   target_goal::text AS target_goal
            FROM users
            WHERE activity_level IS NOT NULL
              AND target_goal IS NOT NULL
            LIMIT 1
            """
        )
    )
    row = result.first()

    if row:
        return row.activity_level, row.target_goal

    # Резервний варіант, якщо в users раптом немає жодного повного профілю
    activity_result = await session.execute(
        text(
            """
            SELECT e.enumlabel
            FROM pg_enum e
            JOIN pg_type t ON e.enumtypid = t.oid
            WHERE t.typname = 'activitylevel'
            ORDER BY e.enumsortorder
            """
        )
    )
    activity_labels = [r.enumlabel for r in activity_result.fetchall()]

    goal_result = await session.execute(
        text(
            """
            SELECT e.enumlabel
            FROM pg_enum e
            JOIN pg_type t ON e.enumtypid = t.oid
            WHERE t.typname = 'targetgoal'
            ORDER BY e.enumsortorder
            """
        )
    )
    goal_labels = [r.enumlabel for r in goal_result.fetchall()]

    activity_level = (
        "MEDIUM"
        if "MEDIUM" in activity_labels
        else activity_labels[0]
    )

    target_goal = (
        "MAINTAIN"
        if "MAINTAIN" in goal_labels
        else goal_labels[0]
    )

    return activity_level, target_goal


async def main() -> None:
    async with db_manager.session_factory() as session:
        today = datetime.now()

        activity_level, target_goal = await get_enum_defaults(session)

        print(f"✅ Використовую activity_level={activity_level}")
        print(f"✅ Використовую target_goal={target_goal}")

        users = [
            (910000001, "Ілона", 2450),
            (910000002, "Марія", 2100),
            (910000003, "Олександр", 1850),
            (910000004, "Анна", 1620),
            (910000005, "Дмитро", 1390),
            (910000006, "Софія", 1210),
        ]

        for user_id, username, weekly_calories in users:
            await session.execute(
                text(
                    """
                    INSERT INTO users
                    (user_id, username, phone_number, registered_at, activity_level, target_goal)
                    VALUES
                    (:user_id, :username, :phone_number, :registered_at, :activity_level, :target_goal)
                    ON CONFLICT (user_id) DO UPDATE
                    SET
                        username = EXCLUDED.username,
                        phone_number = EXCLUDED.phone_number,
                        activity_level = EXCLUDED.activity_level,
                        target_goal = EXCLUDED.target_goal
                    """
                ),
                {
                    "user_id": user_id,
                    "username": username,
                    "phone_number": f"+38099000{str(user_id)[-3:]}",
                    "registered_at": today,
                    "activity_level": activity_level,
                    "target_goal": target_goal,
                },
            )

            await session.execute(
                text(
                    """
                    DELETE FROM activity_logs
                    WHERE user_id = :user_id
                    """
                ),
                {"user_id": user_id},
            )

            daily_calories = weekly_calories / 7

            for i in range(7):
                created_at = today - timedelta(days=6 - i)

                await session.execute(
                    text(
                        """
                        INSERT INTO activity_logs
                        (user_id, activity_type, duration_minutes, calories_burned,
                         distance, weight_kg, repetitions, created_at)
                        VALUES
                        (:user_id, :activity_type, :duration_minutes, :calories_burned,
                         :distance, :weight_kg, :repetitions, :created_at)
                        """
                    ),
                    {
                        "user_id": user_id,
                        "activity_type": "cardio" if i % 2 == 0 else "strength",
                        "duration_minutes": 35 + i * 3,
                        "calories_burned": daily_calories,
                        "distance": 3.0 if i % 2 == 0 else 0.0,
                        "weight_kg": 0.0 if i % 2 == 0 else 25.0,
                        "repetitions": 0 if i % 2 == 0 else 40,
                        "created_at": created_at,
                    },
                )

        await session.commit()
        print("✅ Готово: тестові користувачі та дані для лідерборду додані.")

    await db_manager.close()


if __name__ == "__main__":
    asyncio.run(main())