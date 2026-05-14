"""Клавіатури для Telegram Bot API (aiogram 3.x)."""

from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Клавіатура головного меню."""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="📊 Аналітика"),
        KeyboardButton(text="🏃 Додати активність"),
    )
    builder.row(
        KeyboardButton(text="🥗 Додати харчування"),
        KeyboardButton(text="📄 Звіти"),
    )
    builder.row(
        KeyboardButton(text="🎯 Мої цілі"),
        KeyboardButton(text="🏆 Челенджі"),
    )
    builder.row(
        KeyboardButton(text="👤 Профіль"),
        KeyboardButton(text="📋 Історія"),
    )
    return builder.as_markup(resize_keyboard=True)


def share_phone_keyboard() -> ReplyKeyboardMarkup:
    """Клавіатура з кнопкою поділитися номером телефону."""
    return ReplyKeyboardMarkup(
        keyboard=[[
            KeyboardButton(
                text="📱 Поділитися номером телефону",
                request_contact=True,
            )
        ]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def confirm_keyboard() -> ReplyKeyboardMarkup:
    """Клавіатура підтвердження дії."""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="✅ Так"),
        KeyboardButton(text="❌ Ні"),
    )
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def registration_confirm_keyboard() -> ReplyKeyboardMarkup:
    """
    Клавіатура підтвердження реєстрації.
    Містить «Зберегти», «Змінити» (перезаповнити) та «Скасувати».
    """
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="✅ Зберегти"))
    builder.row(KeyboardButton(text="🔄 Змінити"))
    builder.row(KeyboardButton(text="❌ Скасувати"))
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def activity_type_keyboard() -> InlineKeyboardMarkup:
    """Інлайн-клавіатура вибору типу активності."""
    builder = InlineKeyboardBuilder()
    types = [
        ("🏃 Кардіо", "activity:cardio"),
        ("💪 Силові", "activity:strength"),
        ("🧘 Йога", "activity:yoga"),
        ("🚴 Велосипед", "activity:cycling"),
        ("🏊 Плавання", "activity:swimming"),
        ("🚶 Ходьба", "activity:walking"),
    ]
    for text, callback in types:
        builder.button(text=text, callback_data=callback)
    builder.adjust(2)
    return builder.as_markup()


def report_format_keyboard() -> InlineKeyboardMarkup:
    """Інлайн-клавіатура вибору формату звіту та поділення (позначка 26)."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📕 Отримати звіт PDF", callback_data="report:pdf")
    builder.button(text="📗 Отримати звіт Excel", callback_data="report:excel")
    builder.button(text="📤 Поділитися звітом", callback_data="report:share")
    builder.adjust(2, 1)
    return builder.as_markup()


def menu_button() -> ReplyKeyboardMarkup:
    """Кнопка повернення до головного меню."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🏠 Menu")]],
        resize_keyboard=True,
    )