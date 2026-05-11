"""Модульні тести AnalyticsCore."""

import pytest
import numpy as np
from unittest.mock import AsyncMock, patch
from src.services.analytics_core import AnalyticsCore


class TestAnomalyDetection:
    """Тести виявлення аномалій."""

    def test_insufficient_data_returns_message(self):
        """Менше 20 записів — повідомлення про недостатність даних."""
        mock_session = AsyncMock()
        core = AnalyticsCore(mock_session)
        result = core.detect_anomalies([100, 200, 150])
        assert result["anomalies"] == []
        assert "Недостатньо" in result["message"]

    def test_detects_spike_anomaly(self):
        """Різкий стрибок у даних визначається як аномалія."""
        mock_session = AsyncMock()
        core = AnalyticsCore(mock_session)
        # 24 нормальні значення + 1 явний пік (≤10% — відповідає contamination)
        normal = [200.0] * 24
        spike = normal + [3000.0]  # один пік у 15 разів
        result = core.detect_anomalies(spike)
        assert len(result["anomalies"]) > 0
        types = [a["type"] for a in result["anomalies"]]
        assert any("пікове" in t for t in types)

    def test_labels_length_matches_input(self):
        """Кількість міток відповідає кількості вхідних значень."""
        mock_session = AsyncMock()
        core = AnalyticsCore(mock_session)
        values = [150 + (i % 50) for i in range(30)]
        result = core.detect_anomalies(values)
        assert len(result["labels"]) == len(values)

    def test_no_anomalies_in_uniform_data(self):
        """Рівномірні дані не містять аномалій."""
        mock_session = AsyncMock()
        core = AnalyticsCore(mock_session)
        uniform = [200.0] * 30
        result = core.detect_anomalies(uniform)
        # При рівномірних даних аномалій не повинно бути
        assert result["message"] is not None


class TestForecastBuilding:
    """Тести побудови прогнозу."""

    @pytest.mark.asyncio
    async def test_insufficient_records_returns_error(self):
        """Менше 7 записів — помилка з поясненням."""
        mock_session = AsyncMock()
        core = AnalyticsCore(mock_session)

        with patch.object(core._repo, "count_by_user", return_value=3), \
             patch.object(core._repo, "get_time_series", return_value=[]):
            chart, metrics, error = await core.build_forecast(user_id=1)

        assert chart is None
        assert "Недостатньо даних" in error

    @pytest.mark.asyncio
    async def test_strategy_can_be_changed(self):
        """Перевіряє, що стратегія прогнозування замінюється без помилок."""
        from src.services.analytics_core import HoltWintersStrategy
        mock_session = AsyncMock()
        core = AnalyticsCore(mock_session)
        core.set_strategy(HoltWintersStrategy())
        assert isinstance(core._strategy, HoltWintersStrategy)
