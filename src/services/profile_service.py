"""
Сервіс профілю користувача.
Реалізує бізнес-логіку реєстрації, авторизації та управління профілем.
"""

import math
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.domain import User, BodyMetrics
from src.models.dto import UserRegistrationDTO
from src.repository.profile_repo import ProfileRepository
from src.validators.pydantic_validator import PydanticValidator


class ProfileService:
    """
    Сервіс управління профілем та авторизацією.
    Патерн Dependency Injection — отримує сесію через конструктор.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._repo = ProfileRepository(session)
        self._validator = PydanticValidator()

    @staticmethod
    def calculate_bmr(
        weight: float, height: float, age: int, gender: str
    ) -> float:
        """
        Розраховує базальний метаболічний рівень (BMR) за формулою Маффіна-Джеора.
        Чоловіки: 10*вага + 6.25*зріст - 5*вік + 5
        Жінки: 10*вага + 6.25*зріст - 5*вік - 161
        """
        bmr = 10 * weight + 6.25 * height - 5 * age
        return bmr + 5 if gender == "male" else bmr - 161

    @staticmethod
    def calculate_tdee(bmr: float, activity_level: str) -> float:
        """
        Розраховує добову норму калорій (TDEE) з урахуванням рівня активності.
        Коефіцієнти: low=1.2, medium=1.375, high=1.55, very_high=1.725
        """
        coefficients = {
            "low": 1.2,
            "medium": 1.375,
            "high": 1.55,
            "very_high": 1.725,
        }
        return round(bmr * coefficients.get(activity_level, 1.375), 1)

    async def register_user(self, data: dict) -> tuple[User | None, str]:
        """
        Реєструє нового користувача.
        Повертає (User, '') при успіху або (None, повідомлення_про_помилку).
        """
        dto, error = self._validator.validate_registration(data)
        if error:
            return None, error

        existing = await self._repo.get_by_telegram_id(dto.telegram_id)
        if existing:
            return None, "Користувач вже зареєстрований."

        user = User(
            user_id=dto.telegram_id,
            username=dto.username,
            phone_number=dto.phone_number,
            activity_level=dto.activity_level,
            target_goal=dto.target_goal,
        )
        saved_user = await self._repo.save(user)

        bmr = self.calculate_bmr(dto.weight, dto.height, dto.age, dto.gender)
        tdee = self.calculate_tdee(bmr, dto.activity_level)

        metrics = BodyMetrics(
            user_id=dto.telegram_id,
            weight=dto.weight,
            height=dto.height,
            age=dto.age,
            gender=dto.gender,
            bmr=round(bmr, 1),
            tdee=tdee,
        )
        await self._repo.save_metrics(metrics)

        return saved_user, ""

    async def authorize_user(self, phone: str) -> User | None:
        """Авторизує зареєстрованого користувача за номером телефону."""
        return await self._repo.get_by_phone(phone)

    async def get_profile(self, telegram_id: int) -> dict | None:
        """Повертає повні дані профілю для відображення."""
        user = await self._repo.get_by_telegram_id(telegram_id)
        if not user:
            return None
        metrics = await self._repo.get_latest_metrics(telegram_id)
        return {
            "user": user,
            "metrics": metrics,
        }

    async def update_profile(self, telegram_id: int, updates: dict) -> bool:
        """Оновлює антропометричні дані користувача та перераховує BMR/TDEE."""
        user = await self._repo.get_by_telegram_id(telegram_id)
        if not user:
            return False
        metrics = await self._repo.get_latest_metrics(telegram_id)
        if not metrics:
            return False

        for key, value in updates.items():
            if key == "activity_level":
                user.activity_level = value
            elif hasattr(metrics, key):
                setattr(metrics, key, value)

        # Перераховуємо BMR/TDEE зі збереженою статтю
        bmr = self.calculate_bmr(
            metrics.weight, metrics.height, metrics.age,
            metrics.gender  # використовуємо збережену стать
        )
        metrics.bmr = round(bmr, 1)
        metrics.tdee = self.calculate_tdee(bmr, user.activity_level)

        await self._repo.save(user)
        await self._repo.save_metrics(metrics)
        return True
