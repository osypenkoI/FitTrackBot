"""
Аналітичне ядро FitTrackBot.
Реалізує прогнозування часових рядів (Prophet, Holt-Winters),
виявлення аномалій (Isolation Forest + PyOD KNN) та
статистичний аналіз даних (SciPy).
Патерн Strategy — алгоритм прогнозування можна змінити без зміни інтерфейсу.
"""

import io
import logging
from typing import Protocol
import numpy as np
import pandas as pd
from scipy import stats as scipy_stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sqlalchemy.ext.asyncio import AsyncSession
from src.config import config
from src.repository.activity_repo import ActivityRepository

logger = logging.getLogger(__name__)


# ── Патерн Strategy: інтерфейс алгоритму прогнозування ────────────────────────

class ForecastStrategy(Protocol):
    """Інтерфейс стратегії прогнозування."""

    def fit_predict(self, df: pd.DataFrame, days: int) -> pd.DataFrame: ...


class ProphetStrategy:
    """Стратегія прогнозування на основі Facebook Prophet."""

    def fit_predict(self, df: pd.DataFrame, days: int) -> pd.DataFrame:
        from prophet import Prophet
        model = Prophet(
            yearly_seasonality=False,
            weekly_seasonality=True,
            daily_seasonality=False,
            interval_width=0.80,
        )
        model.fit(df)
        future = model.make_future_dataframe(periods=days)
        forecast = model.predict(future)
        return forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]]


class HoltWintersStrategy:
    """Стратегія прогнозування Holt-Winters."""

    def fit_predict(self, df: pd.DataFrame, days: int) -> pd.DataFrame:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
        series = df["y"].values
        model = ExponentialSmoothing(
            series, trend="add", seasonal=None, initialization_method="estimated"
        ).fit()
        forecast_values = model.forecast(days)
        last_date = df["ds"].iloc[-1]
        future_dates = pd.date_range(
            start=last_date + pd.Timedelta(days=1), periods=days
        )
        result_df = pd.DataFrame({"ds": future_dates, "yhat": forecast_values})
        result_df["yhat_lower"] = result_df["yhat"] * 0.85
        result_df["yhat_upper"] = result_df["yhat"] * 1.15
        return result_df


# ── Аналітичне ядро ────────────────────────────────────────────────────────────

class AnalyticsCore:
    """
    Аналітичне ядро: прогнозування та виявлення аномалій.
    Патерн Strategy — стратегія передається при ініціалізації.
    """

    def __init__(
        self,
        session: AsyncSession,
        strategy: ForecastStrategy | None = None,
    ) -> None:
        self._repo = ActivityRepository(session)
        self._strategy: ForecastStrategy = strategy or ProphetStrategy()

    def set_strategy(self, strategy: ForecastStrategy) -> None:
        """Змінює стратегію прогнозування (патерн Strategy)."""
        self._strategy = strategy

    async def build_forecast(
        self, user_id: int, days: int = 14
    ) -> tuple[bytes | None, dict, str]:
        """
        Будує прогноз активності.
        Повертає (PNG-графік, метрики, повідомлення_про_помилку).
        """
        records = await self._repo.get_time_series(user_id)
        count = await self._repo.count_by_user(user_id)

        if count < config.min_records_forecast:
            return (
                None, {},
                f"Недостатньо даних для прогнозу. "
                f"Потрібно мінімум {config.min_records_forecast} записів, "
                f"є {count}.",
            )

        df = pd.DataFrame(
            [
                {
                    "ds": r.created_at.date(),
                    "y": r.calories_burned,
                }
                for r in records
            ]
        )
        df = df.groupby("ds").sum().reset_index()

        try:
            forecast = self._strategy.fit_predict(df, days)
        except Exception as exc:
            logger.error("Помилка прогнозування: %s", exc)
            return None, {}, f"Помилка побудови прогнозу: {exc}"

        chart = self._build_chart(df, forecast)

        # ── Статистичний аналіз за допомогою SciPy ────────────────────────
        y_values = df["y"].values

        # Лінійний тренд (scipy.stats.linregress)
        x_numeric = np.arange(len(y_values), dtype=float)
        slope, intercept, r_value, p_value, std_err = scipy_stats.linregress(
            x_numeric, y_values
        )
        trend_direction = "зростання" if slope > 0 else "спадання"
        trend_strength = abs(round(float(r_value), 2))  # R — коефіцієнт кореляції

        # Перевірка нормальності розподілу (Shapiro-Wilk, до 50 значень)
        if len(y_values) <= 50:
            stat_sw, p_normal = scipy_stats.shapiro(y_values)
            is_normal = p_normal > 0.05
        else:
            # Для більших вибірок — D'Agostino-Pearson
            stat_sw, p_normal = scipy_stats.normaltest(y_values)
            is_normal = p_normal > 0.05

        # Коефіцієнт варіації (відносний розкид даних)
        mean_val = float(np.mean(y_values))
        std_val = float(np.std(y_values))
        cv = round(std_val / mean_val * 100, 1) if mean_val != 0 else 0.0

        # Медіана та перцентилі (25-й та 75-й)
        p25, median_val, p75 = [
            round(float(v), 1)
            for v in scipy_stats.mstats.mquantiles(y_values, [0.25, 0.5, 0.75])
        ]

        metrics = {
            "mean_forecast": round(float(forecast["yhat"].mean()), 1),
            "max_forecast": round(float(forecast["yhat"].max()), 1),
            "trend": trend_direction,
            "trend_strength": trend_strength,        # R-коефіцієнт
            "slope": round(float(slope), 2),         # калорій/день зміна
            "p_value": round(float(p_value), 4),     # значущість тренду
            "is_normal": is_normal,                  # нормальний розподіл?
            "cv_percent": cv,                        # коефіцієнт варіації %
            "median": median_val,                    # медіана
            "p25": p25,                              # 25-й перцентиль
            "p75": p75,                              # 75-й перцентиль
        }
        return chart, metrics, ""

    def detect_anomalies(self, values: list[float]) -> dict:
        """
        Виявляє аномалії трьома алгоритмами паралельно:
        — Z-score (SciPy) як попередній відбір екстремальних значень (|z| > 2.5)
        — Isolation Forest (sklearn) як основний
        — KNN (PyOD) як додатковий для перехресної перевірки.
        Аномалія підтверджується якщо виявлена хоча б одним алгоритмом.
        """
        if len(values) < config.min_records_anomaly:
            return {
                "anomalies": [],
                "labels": [],
                "message": (
                    f"Недостатньо даних. Потрібно ≥ {config.min_records_anomaly} записів."
                ),
            }

        X = np.array(values).reshape(-1, 1)
        mean_val = float(np.mean(values))

        # ── Попередній аналіз: Z-score (SciPy) ───────────────────────────
        # Z-score виявляє екстремальні значення (|z| > 2.5 → потенційна аномалія)
        z_scores = np.abs(scipy_stats.zscore(values))
        zscore_flags = set(int(i) for i in np.where(z_scores > 2.5)[0])

        # ── Алгоритм 1: Isolation Forest (sklearn) ────────────────────────
        from sklearn.ensemble import IsolationForest
        iso = IsolationForest(
            contamination=config.anomaly_contamination,
            n_estimators=100,
            random_state=42,
        )
        iso_labels = iso.fit_predict(X).tolist()  # 1=норма, -1=аномалія
        iso_anomalies = set(i for i, l in enumerate(iso_labels) if l == -1)

        # ── Алгоритм 2: KNN (PyOD) ────────────────────────────────────────
        try:
            from pyod.models.knn import KNN
            n_neighbors = min(5, len(values) - 1)
            knn = KNN(
                contamination=config.anomaly_contamination,
                n_neighbors=n_neighbors,
            )
            knn.fit(X)
            knn_labels_raw = knn.labels_.tolist()  # 0=норма, 1=аномалія
            knn_anomalies = set(i for i, l in enumerate(knn_labels_raw) if l == 1)
        except Exception as e:
            logger.warning("PyOD KNN недоступний, використовується лише IsoForest: %s", e)
            knn_anomalies = set()

        # ── Об'єднання результатів ─────────────────────────────────────────
        # Аномалія — якщо виявлена хоча б одним з трьох алгоритмів
        all_anomaly_indices = sorted(iso_anomalies | knn_anomalies | zscore_flags)

        # Фінальні мітки: -1 якщо аномалія, 1 якщо норма
        final_labels = [
            -1 if i in all_anomaly_indices else 1
            for i in range(len(values))
        ]

        anomaly_types = []
        for idx in all_anomaly_indices:
            val = values[idx]
            detected_by = []
            if idx in iso_anomalies:
                detected_by.append("IsolationForest")
            if idx in knn_anomalies:
                detected_by.append("KNN")
            if idx in zscore_flags:
                detected_by.append("Z-score")
            atype = "пікове навантаження" if val > mean_val * 1.5 else "критичний спад активності"
            anomaly_types.append({
                "index": idx,
                "type": atype,
                "value": round(val, 1),
                "detected_by": ", ".join(detected_by),
                "z_score": round(float(z_scores[idx]), 2),
            })

        return {
            "anomalies": anomaly_types,
            "labels": final_labels,
            "iso_anomalies": sorted(iso_anomalies),
            "knn_anomalies": sorted(knn_anomalies),
            "zscore_anomalies": sorted(zscore_flags),
            "message": (
                f"Виявлено {len(all_anomaly_indices)} аномалій "
                f"(IsolationForest: {len(iso_anomalies)}, "
                f"KNN: {len(knn_anomalies)}, "
                f"Z-score: {len(zscore_flags)})."
                if all_anomaly_indices
                else "Аномалій не виявлено. Ваші показники в межах норми."
            ),
        }

    async def generate_recommendations(self, user_id: int) -> str:
        """
        Генерує персоналізовані рекомендації (ФВ 4.2.1).
        Аналізує тренд активності та енергетичний баланс.
        """
        from datetime import date as dt, timedelta

        records = await self._repo.get_time_series(user_id, days=14)
        if len(records) < 3:
            return "💡 Додайте більше записів активності для отримання рекомендацій."

        recent_calories = [r.calories_burned for r in records[-7:]]
        older_calories = [r.calories_burned for r in records[-14:-7]]
        recent_avg = sum(recent_calories) / len(recent_calories) if recent_calories else 0
        older_avg = sum(older_calories) / len(older_calories) if older_calories else 0

        recommendations = []

        # Аналіз тренду активності
        if older_avg > 0 and recent_avg < older_avg * 0.8:
            recommendations.append(
                "📉 Ваша активність знизилась за останній тиждень. "
                "Спробуйте додати хоча б одне тренування сьогодні."
            )
        elif recent_avg > older_avg * 1.3:
            recommendations.append(
                "📈 Відмінна динаміка! Ваша активність зростає. "
                "Збережіть темп і додайте день відпочинку, якщо відчуваєте втому."
            )

        # Аналіз частоти тренувань за останні 7 днів
        week_start = dt.today() - timedelta(days=7)
        workouts_per_week = len(
            [r for r in records if r.created_at and r.created_at.date() >= week_start]
        )
        if workouts_per_week < 3:
            recommendations.append(
                "🗓 Рекомендується тренуватись мінімум 3 рази на тиждень. "
                "Спробуйте додати ще одне тренування."
            )

        if not recommendations:
            recommendations.append(
                "✅ Ваші показники в нормі. Продовжуйте у тому самому темпі!"
            )

        return "💡 <b>Персоналізовані рекомендації:</b>\n\n" + "\n\n".join(recommendations)

    @staticmethod
    def _build_chart(historical: pd.DataFrame, forecast: pd.DataFrame) -> bytes:
        """Будує графік тренду у форматі PNG."""
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(historical["ds"], historical["y"], "b-o", label="Факт", markersize=4)
        ax.plot(forecast["ds"], forecast["yhat"], "r--", label="Прогноз")
        if "yhat_lower" in forecast.columns:
            ax.fill_between(
                forecast["ds"],
                forecast["yhat_lower"],
                forecast["yhat_upper"],
                alpha=0.2, color="red", label="Довірчий інтервал",
            )
        ax.set_xlabel("Дата")
        ax.set_ylabel("Калорії (ккал)")
        ax.set_title("Прогноз фізичної активності")
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=150)
        plt.close(fig)
        buf.seek(0)
        return buf.read()
