"""Форматування відповідей для Telegram."""

from src.models.domain import User, BodyMetrics, ActivityLog, NutritionLog


ACTIVITY_LEVEL_LABELS = {
    "low": "Низький",
    "medium": "Середній",
    "high": "Високий",
    "very_high": "Дуже високий",
}

TARGET_GOAL_LABELS = {
    "weight_loss": "Схуднення",
    "muscle_gain": "Набір маси",
    "maintain": "Підтримка форми",
}

ACTIVITY_TYPE_LABELS = {
    "cardio": "🏃 Кардіо",
    "strength": "💪 Силові",
    "yoga": "🧘 Йога",
    "cycling": "🚴 Велосипед",
    "swimming": "🏊 Плавання",
    "walking": "🚶 Ходьба",
    "running": "🏃 Біг",
    "other": "Інше",
}

MEAL_TYPE_LABELS = {
    "breakfast": "Сніданок",
    "lunch": "Обід",
    "dinner": "Вечеря",
    "snack": "Перекус",
}


def _raw_value(value) -> str:
    """Повертає значення enum або рядок без технічного префікса класу."""
    if value is None:
        return ""
    if hasattr(value, "value"):
        return str(value.value)
    text = str(value)
    if "." in text:
        return text.split(".")[-1].lower()
    return text.lower()


def format_activity_level(value) -> str:
    """Форматує рівень активності для відображення користувачу."""
    raw = _raw_value(value)
    return ACTIVITY_LEVEL_LABELS.get(raw, raw)


def format_activity_type(value) -> str:
    """Форматує тип активності для відображення користувачу."""
    raw = _raw_value(value)
    return ACTIVITY_TYPE_LABELS.get(raw, raw)


def format_meal_type(value) -> str:
    """Форматує тип прийому їжі для відображення користувачу."""
    raw = _raw_value(value)
    return MEAL_TYPE_LABELS.get(raw, raw)


def format_profile(user: User, metrics: BodyMetrics | None) -> str:
    """Форматує повідомлення профілю користувача."""
    name = user.username or "Користувач"
    text = f"👤 <b>Ваш профіль</b>\n\nІм'я: {name}\n"
    if metrics:
        text += (
            f"Вік: {metrics.age}\n"
            f"Зріст: {metrics.height} см\n"
            f"Вага: {metrics.weight} кг\n"
            f"Рівень активності: {format_activity_level(user.activity_level)}\n"
            f"BMR: <b>{metrics.bmr:.0f} ккал</b>\n"
            f"TDEE: <b>{metrics.tdee:.0f} ккал</b>\n"
        )
    return text


def format_activity_log(log: ActivityLog) -> str:
    """Форматує запис активності для відображення."""
    return (
        f"✅ Активність збережено!\n\n"
        f"Тип: {format_activity_type(log.activity_type)}\n"
        f"Тривалість: {log.duration_minutes} хв\n"
        f"Спалено: <b>{log.calories_burned:.0f} ккал</b>\n"
        f"Дата: {log.created_at.strftime('%d.%m.%Y %H:%M')}"
    )


def format_nutrition_log(log: NutritionLog) -> str:
    """Форматує запис харчування для відображення."""
    return (
        f"✅ Харчування збережено!\n\n"
        f"Прийом: {format_meal_type(log.meal_type)}\n"
        f"Страва: {log.food_name} ({log.amount_grams:.0f} г)\n"
        f"Калорій: <b>{log.calories_intake:.0f} ккал</b>"
    )


def format_analytics(metrics: dict, anomaly_result: dict) -> str:
    """Форматує аналітичний звіт з розширеною статистикою (SciPy)."""
    trend = metrics.get("trend", "—")
    mean_f = metrics.get("mean_forecast", 0)
    slope = metrics.get("slope", 0)
    r = metrics.get("trend_strength", 0)
    cv = metrics.get("cv_percent", 0)
    median = metrics.get("median", 0)
    p25 = metrics.get("p25", 0)
    p75 = metrics.get("p75", 0)
    is_normal = metrics.get("is_normal", None)
    p_value = metrics.get("p_value", None)

    # Опис сили тренду
    if r >= 0.7:
        trend_desc = "сильний"
    elif r >= 0.4:
        trend_desc = "помірний"
    else:
        trend_desc = "слабкий"

    trend_emoji = "📈" if trend == "зростання" else "📉"
    normal_text = ""
    if is_normal is not None:
        normal_text = (
            "\n📐 Розподіл: <b>нормальний</b>" if is_normal
            else "\n📐 Розподіл: <b>ненормальний</b>"
        )

    sig_text = ""
    if p_value is not None:
        sig_text = (
            " (статистично значущий)" if p_value < 0.05
            else " (незначущий)"
        )

    return (
        f"📊 <b>Аналітичний звіт</b>\n\n"
        f"🔮 Середній прогноз: <b>{mean_f:.0f} ккал/день</b>\n\n"
        f"📉 <b>Статистичний аналіз (SciPy):</b>\n"
        f"{trend_emoji} Тренд: <b>{trend}</b> ({trend_desc}, R={r}){sig_text}\n"
        f"📊 Зміна: <b>{slope:+.1f} ккал/день</b>\n"
        f"📏 Медіана: <b>{median:.0f} ккал</b>\n"
        f"📦 IQR: {p25:.0f} – {p75:.0f} ккал\n"
        f"📉 Коефіцієнт варіації: <b>{cv:.1f}%</b>"
        f"{normal_text}\n\n"
        f"🔍 <b>Аномалії:</b>\n{anomaly_result.get('message', '—')}"
    )


def format_leaderboard(entries: list[dict]) -> str:
    """Форматує таблицю лідерів."""
    if not entries:
        return "🏆 Рейтинг порожній."
    lines = ["🏆 <b>Топ користувачів</b>\n"]
    medals = ["🥇", "🥈", "🥉"]
    for i, entry in enumerate(entries):
        medal = medals[i] if i < 3 else f"{i+1}."
        name = entry.get("username") or f"User {entry.get('user_id')}"
        total = entry.get("total", 0)
        lines.append(f"{medal} {name} — {total:.0f} ккал")
    return "\n".join(lines)