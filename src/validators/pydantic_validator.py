"""
Валідатор вхідних даних через Pydantic.
Патерн Adapter — адаптує raw Telegram-дані до DTO-об'єктів.
"""

from pydantic import ValidationError
from src.models.dto import (
    UserRegistrationDTO, ActivityInputDTO,
    NutritionInputDTO, ChallengeCreateDTO,
)


class PydanticValidator:
    """
    Централізований валідатор вхідних даних.
    Перетворює словники з Telegram-повідомлень на перевірені DTO-об'єкти.
    """

    @staticmethod
    def validate_registration(data: dict) -> tuple[UserRegistrationDTO | None, str]:
        """
        Валідує дані реєстрації.
        Повертає (DTO, '') якщо успішно, або (None, повідомлення_про_помилку).
        """
        try:
            dto = UserRegistrationDTO(**data)
            return dto, ""
        except ValidationError as e:
            errors = "; ".join(
                f"{err['loc'][0]}: {err['msg']}" for err in e.errors()
            )
            return None, f"Помилка валідації: {errors}"

    @staticmethod
    def validate_activity(data: dict) -> tuple[ActivityInputDTO | None, str]:
        """Валідує дані про фізичну активність."""
        try:
            dto = ActivityInputDTO(**data)
            return dto, ""
        except ValidationError as e:
            errors = "; ".join(
                f"{err['loc'][0]}: {err['msg']}" for err in e.errors()
            )
            return None, f"Помилка валідації активності: {errors}"

    @staticmethod
    def validate_nutrition(data: dict) -> tuple[NutritionInputDTO | None, str]:
        """Валідує дані про харчування."""
        try:
            dto = NutritionInputDTO(**data)
            return dto, ""
        except ValidationError as e:
            errors = "; ".join(
                f"{err['loc'][0]}: {err['msg']}" for err in e.errors()
            )
            return None, f"Помилка валідації харчування: {errors}"

    @staticmethod
    def validate_challenge(data: dict) -> tuple[ChallengeCreateDTO | None, str]:
        """Валідує дані нового челенджу."""
        try:
            dto = ChallengeCreateDTO(**data)
            return dto, ""
        except ValidationError as e:
            errors = "; ".join(
                f"{err['loc'][0]}: {err['msg']}" for err in e.errors()
            )
            return None, f"Помилка валідації челенджу: {errors}"
