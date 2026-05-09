"""Модульні тести ActivityService."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.activity_service import ActivityService, CALORIES_PER_MINUTE


class TestCaloriesEstimation:
    """Тести розрахунку калорій."""

    def test_running_calories(self):
        """Розрахунок калорій для бігу 30 хв, вага 70 кг."""
        mock_session = AsyncMock()
        service = ActivityService(mock_session)
        result = service.estimate_calories("running", 30, 70.0)
        expected = CALORIES_PER_MINUTE["running"] * (70.0 / 70.0) * 30
        assert result == pytest.approx(expected, abs=0.5)

    def test_calories_scale_with_weight(self):
        """Більша вага — більше калорій."""
        mock_session = AsyncMock()
        service = ActivityService(mock_session)
        light = service.estimate_calories("cardio", 30, 60.0)
        heavy = service.estimate_calories("cardio", 30, 90.0)
        assert heavy > light

    def test_unknown_activity_uses_default(self):
        """Невідомий тип активності використовує значення за замовчуванням."""
        mock_session = AsyncMock()
        service = ActivityService(mock_session)
        result = service.estimate_calories("unknown_sport", 30, 70.0)
        expected = 5.0 * 1.0 * 30  # default коефіцієнт 5.0
        assert result == pytest.approx(expected, abs=0.5)


class TestActivityLogging:
    """Тести збереження записів активності."""

    @pytest.mark.asyncio
    async def test_log_activity_success(self):
        """Успішне збереження запису активності."""
        mock_session = AsyncMock()
        service = ActivityService(mock_session)

        valid_data = {
            "user_id": 1,
            "activity_type": "running",
            "duration_minutes": 45,
        }
        from src.models.domain import ActivityLog
        mock_log = MagicMock(spec=ActivityLog)
        mock_log.activity_type = "running"
        mock_log.calories_burned = 450.0

        with patch.object(service._activity_repo, "save", return_value=mock_log):
            log, error = await service.log_activity(valid_data, user_weight=70.0)

        assert error == ""
        assert log is not None

    @pytest.mark.asyncio
    async def test_log_activity_invalid_type(self):
        """Невалідний тип активності повертає помилку."""
        mock_session = AsyncMock()
        service = ActivityService(mock_session)

        invalid_data = {
            "user_id": 1,
            "activity_type": "flying",   # не існує
            "duration_minutes": 30,
        }
        log, error = await service.log_activity(invalid_data)
        assert log is None
        assert error != ""

    @pytest.mark.asyncio
    async def test_log_activity_negative_duration(self):
        """Від'ємна тривалість повертає помилку валідації."""
        mock_session = AsyncMock()
        service = ActivityService(mock_session)

        data = {
            "user_id": 1,
            "activity_type": "cardio",
            "duration_minutes": -10,
        }
        log, error = await service.log_activity(data)
        assert log is None
        assert error != ""
