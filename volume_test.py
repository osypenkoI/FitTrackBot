"""Швидкий вимір часу виконання ключових сценаріїв на повній базі."""
import asyncio
import time
from src.database.connection import db_manager
from src.services.profile_service import ProfileService
from src.services.activity_service import ActivityService
from src.services.analytics_core import AnalyticsCore
from src.services.reporting_service import ReportingService
from src.services.social_service import SocialService
from src.services.goals_service import GoalsService
from src.services.admin_service import AdminService
from datetime import date, timedelta


async def measure(name: str, coro):
    """Вимірює час виконання асинхронної функції."""
    start = time.perf_counter()
    await coro
    elapsed = (time.perf_counter() - start) * 1000
    print(f"{name}: {elapsed:.1f} мс")


async def main():
    # Беремо першого тестового користувача (seed створює user_id=1, 2, 3...)
    test_user_id = 1

    async with db_manager.session_factory() as session:
        # 1. Прогноз
        core = AnalyticsCore(session)
        start = time.perf_counter()
        await core.build_forecast(test_user_id, days=14)
        print(f"1. Прогноз через ProphetStrategy: {(time.perf_counter()-start)*1000:.1f} мс")

        # 2. Аномалії
        start = time.perf_counter()
        await core.detect_user_anomalies(test_user_id)
        print(f"2. Виявлення аномалій (ансамбль): {(time.perf_counter()-start)*1000:.1f} мс")

        # 3. PDF
        rep = ReportingService(session)
        start = time.perf_counter()
        await rep.generate_pdf(test_user_id, date.today()-timedelta(days=30), date.today())
        print(f"3. PDF-звіт за 30 днів: {(time.perf_counter()-start)*1000:.1f} мс")

        # 4. Excel
        start = time.perf_counter()
        await rep.generate_excel(test_user_id, date.today()-timedelta(days=90), date.today())
        print(f"4. Excel-звіт за квартал: {(time.perf_counter()-start)*1000:.1f} мс")

        # 5. Лідерборд
        soc = SocialService(session)
        start = time.perf_counter()
        await soc.get_leaderboard("calories_burned")
        print(f"5. Лідерборд: {(time.perf_counter()-start)*1000:.1f} мс")

        # 6. Прогрес цілей
        goals = GoalsService(session)
        start = time.perf_counter()
        await goals.get_goals_with_progress(test_user_id)
        print(f"6. Прогрес цілей: {(time.perf_counter()-start)*1000:.1f} мс")

        # 7. Адмін-статистика
        admin = AdminService(session)
        start = time.perf_counter()
        await admin.get_statistics()
        print(f"7. Адмін-статистика: {(time.perf_counter()-start)*1000:.1f} мс")

        # 8. Історія
        act = ActivityService(session)
        start = time.perf_counter()
        await act.get_history(test_user_id, "activity")
        print(f"8. Історія активності (50 записів): {(time.perf_counter()-start)*1000:.1f} мс")

    await db_manager.close()


if __name__ == "__main__":
    asyncio.run(main())