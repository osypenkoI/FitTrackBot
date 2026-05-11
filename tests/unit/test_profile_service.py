"""
Модульні тести ProfileService.
Перевіряє розрахунок BMR/TDEE та логіку валідації.
"""

from dbm import error

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.profile_service import ProfileService


class TestBMRCalculation:
    """Тести розрахунку базального метаболічного рівня."""

    def test_bmr_male(self):
        """BMR для чоловіка 25 років, 75 кг, 180 см."""
        # Arrange
        weight, height, age, gender = 75.0, 180.0, 25, "male"
        # Act
        result = ProfileService.calculate_bmr(weight, height, age, gender)
        # Assert — формула: 10*75 + 6.25*180 - 5*25 + 5 = 1755
        assert result == pytest.approx(1755.0, abs=1)

    def test_bmr_female(self):
        """BMR для жінки 22 роки, 55 кг, 165 см."""
        # Arrange
        weight, height, age, gender = 55.0, 165.0, 22, "female"
        # Act
        result = ProfileService.calculate_bmr(weight, height, age, gender)
        # Assert — формула: 10*55 + 6.25*165 - 5*22 - 161 = 1310.25
        assert result == pytest.approx(1310.25, abs=1)

    def test_bmr_invalid_gender_defaults_female(self):
        """Невідомий гендер повертає жіночий BMR."""
        result_unknown = ProfileService.calculate_bmr(60, 165, 25, "unknown")
        result_female = ProfileService.calculate_bmr(60, 165, 25, "female")
        assert result_unknown == result_female


class TestTDEECalculation:
    """Тести розрахунку добової норми калорій."""

    def test_tdee_low_activity(self):
        """TDEE для низького рівня активності (коефіцієнт 1.2)."""
        bmr = 1500.0
        result = ProfileService.calculate_tdee(bmr, "low")
        assert result == pytest.approx(1800.0, abs=1)

    def test_tdee_medium_activity(self):
        """TDEE для середнього рівня активності (коефіцієнт 1.375)."""
        bmr = 1500.0
        result = ProfileService.calculate_tdee(bmr, "medium")
        assert result == pytest.approx(2062.5, abs=1)

    def test_tdee_high_activity(self):
        """TDEE для високого рівня активності (коефіцієнт 1.55)."""
        bmr = 1500.0
        result = ProfileService.calculate_tdee(bmr, "high")
        assert result == pytest.approx(2325.0, abs=1)

    def test_tdee_unknown_level_uses_medium(self):
        """Невідомий рівень активності використовує середній коефіцієнт."""
        bmr = 1500.0
        result = ProfileService.calculate_tdee(bmr, "unknown_level")
        assert result == pytest.approx(2062.5, abs=1)


class TestProfileServiceAsync:
    """Тести асинхронних методів ProfileService з mock-сесією."""

    @pytest.mark.asyncio
    async def test_register_user_success(self):
        """Успішна реєстрація нового користувача."""
        # Arrange
        mock_session = AsyncMock()
        service = ProfileService(mock_session)

        valid_data = {
            "telegram_id": 123456,
            "username": "testuser",
            "phone_number": "+380991234567",
            "weight": 70.0,
            "height": 175.0,
            "age": 25,
            "gender": "male",
            "activity_level": "medium",
            "target_goal": "maintain",
        }

        with patch.object(service._repo, "get_by_telegram_id", return_value=None), \
             patch.object(service._repo, "save", new_callable=AsyncMock) as mock_save, \
             patch.object(service._repo, "save_metrics", new_callable=AsyncMock):
            from src.models.domain import User
            mock_user = MagicMock(spec=User)
            mock_user.user_id = 123456
            mock_save.return_value = mock_user

            # Act
            user, error = await service.register_user(valid_data)

        # Assert
        assert error == ""
        assert user is not None

    @pytest.mark.asyncio
    async def test_register_user_already_exists(self):
        """Реєстрація вже існуючого користувача повертає помилку."""
        mock_session = AsyncMock()
        service = ProfileService(mock_session)
        existing = MagicMock()

        valid_data = {
            "telegram_id": 123456,
            "username": "testuser",
            "phone_number": "+380991234567",
            "weight": 75.0,
            "height": 180.0,
            "age": 25,
            "gender": "male",
            "activity_level": "medium",
            "target_goal": "maintain",
        }

        with patch.object(service._repo, "get_by_telegram_id", return_value=existing):
            user, error = await service.register_user(valid_data)

        assert user is None
        assert "вже зареєстрований" in error

    @pytest.mark.asyncio
    async def test_register_user_invalid_data(self):
        """Реєстрація з некоректними даними повертає помилку валідації."""
        mock_session = AsyncMock()
        service = ProfileService(mock_session)

        invalid_data = {
            "telegram_id": 123456,
            "weight": -10,   # невалідна вага
            "height": 175.0,
            "age": 25,
            "gender": "male",
            "activity_level": "medium",
            "target_goal": "maintain",
        }
        user, error = await service.register_user(invalid_data)
        assert user is None
        assert error != ""
