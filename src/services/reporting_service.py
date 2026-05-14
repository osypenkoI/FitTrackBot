"""
Сервіс генерації звітів у форматах PDF та Excel.
"""

import io
import os
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.repository.activity_repo import ActivityRepository
from src.repository.nutrition_repo import NutritionRepository
from src.repository.profile_repo import ProfileRepository
from src.utils.formatters import format_activity_type, format_meal_type


class ReportingService:
    """Сервіс генерації PDF та Excel-звітів з даними активності й харчування."""

    def __init__(self, session: AsyncSession) -> None:
        self._activity_repo = ActivityRepository(session)
        self._nutrition_repo = NutritionRepository(session)
        self._profile_repo = ProfileRepository(session)

    @staticmethod
    def _num(value: Any, default: float = 0.0) -> float:
        """Безпечно перетворює число або None у float."""
        if value is None:
            return default

        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _text(value: Any, default: str = "-") -> str:
        """Безпечно перетворює значення у текст."""
        if value is None:
            return default
        return str(value)

    @staticmethod
    def _date_text(value: Any) -> str:
        """Безпечно форматує date/datetime для звіту."""
        if value is None:
            return "-"

        if hasattr(value, "date"):
            return str(value.date())

        return str(value)

    @staticmethod
    def _format_activity(value: Any) -> str:
        """Безпечно форматує тип активності."""
        if value is None:
            return "-"

        try:
            return format_activity_type(value)
        except Exception:
            return str(value)

    @staticmethod
    def _format_meal(value: Any) -> str:
        """Безпечно форматує тип прийому їжі."""
        if value is None:
            return "-"

        try:
            return format_meal_type(value)
        except Exception:
            return str(value)

    @staticmethod
    def _register_cyrillic_fonts() -> tuple[str, str]:
        """
        Реєструє шрифти з підтримкою кирилиці для PDF-звіту.

        На Windows використовується Arial, на Linux — DejaVu Sans.
        Якщо шрифт не знайдено, застосовується стандартний Helvetica.
        """
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        regular_candidates = [
            r"C:\Windows\Fonts\arial.ttf",
            r"C:\Windows\Fonts\DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]

        bold_candidates = [
            r"C:\Windows\Fonts\arialbd.ttf",
            r"C:\Windows\Fonts\DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]

        regular_path = next(
            (path for path in regular_candidates if os.path.exists(path)),
            None,
        )
        bold_path = next(
            (path for path in bold_candidates if os.path.exists(path)),
            None,
        )

        if not regular_path:
            return "Helvetica", "Helvetica-Bold"

        pdfmetrics.registerFont(TTFont("CyrillicFont", regular_path))

        if bold_path:
            pdfmetrics.registerFont(TTFont("CyrillicFont-Bold", bold_path))
            return "CyrillicFont", "CyrillicFont-Bold"

        return "CyrillicFont", "CyrillicFont"

    async def generate_pdf(
        self, user_id: int, date_from: date, date_to: date
    ) -> bytes:
        """Генерує PDF-звіт з антропометрією, активністю та харчуванням."""
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            Table,
            TableStyle,
        )

        activities = await self._activity_repo.get_by_date_range(
            user_id, date_from, date_to
        )
        nutrition = await self._nutrition_repo.get_by_date_range(
            user_id, date_from, date_to
        )
        metrics = await self._profile_repo.get_latest_metrics(user_id)

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4)

        styles = getSampleStyleSheet()
        font_name, bold_font_name = self._register_cyrillic_fonts()

        styles["Title"].fontName = bold_font_name
        styles["Heading2"].fontName = bold_font_name
        styles["Normal"].fontName = font_name

        story = []

        story.append(Paragraph("FitTrackBot — Аналітичний звіт", styles["Title"]))
        story.append(Spacer(1, 12))

        story.append(
            Paragraph(f"Період: {date_from} — {date_to}", styles["Normal"])
        )
        story.append(Spacer(1, 12))

        if metrics:
            story.append(Paragraph("Антропометричні дані:", styles["Heading2"]))
            story.append(
                Paragraph(
                    f"Вага: {self._num(metrics.weight):.1f} кг | "
                    f"Зріст: {self._num(metrics.height):.1f} см | "
                    f"BMR: {self._num(metrics.bmr):.0f} ккал | "
                    f"TDEE: {self._num(metrics.tdee):.0f} ккал",
                    styles["Normal"],
                )
            )
            story.append(Spacer(1, 12))

        if activities:
            story.append(Paragraph("Активність:", styles["Heading2"]))

            activity_data = [["Тип", "Тривалість (хв)", "Калорії", "Дата"]]

            for activity in activities[:20]:
                activity_data.append(
                    [
                        self._format_activity(activity.activity_type),
                        str(int(self._num(activity.duration_minutes))),
                        f"{self._num(activity.calories_burned):.0f}",
                        self._date_text(activity.created_at),
                    ]
                )

            activity_table = Table(
                activity_data,
                repeatRows=1,
                colWidths=[130, 120, 80, 80],
            )
            activity_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                        ("FONTNAME", (0, 0), (-1, -1), font_name),
                        ("FONTNAME", (0, 0), (-1, 0), bold_font_name),
                        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ]
                )
            )

            story.append(activity_table)
            story.append(Spacer(1, 16))

        if nutrition:
            story.append(Paragraph("Харчування:", styles["Heading2"]))

            nutrition_data = [
                ["Прийом", "Страва", "Грами", "Калорії", "Б/Ж/В", "Дата"]
            ]

            for item in nutrition[:20]:
                nutrition_data.append(
                    [
                        self._format_meal(item.meal_type),
                        self._text(item.food_name),
                        f"{self._num(item.amount_grams):.0f}",
                        f"{self._num(item.calories_intake):.0f}",
                        (
                            f"{self._num(item.proteins):.1f}/"
                            f"{self._num(item.fats):.1f}/"
                            f"{self._num(item.carbohydrates):.1f}"
                        ),
                        self._date_text(item.date),
                    ]
                )

            nutrition_table = Table(
                nutrition_data,
                repeatRows=1,
                colWidths=[70, 115, 55, 60, 75, 70],
            )
            nutrition_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                        ("FONTNAME", (0, 0), (-1, -1), font_name),
                        ("FONTNAME", (0, 0), (-1, 0), bold_font_name),
                        ("ALIGN", (2, 1), (-1, -1), "CENTER"),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ]
                )
            )

            story.append(nutrition_table)
            story.append(Spacer(1, 12))

        if not activities and not nutrition:
            story.append(
                Paragraph(
                    "За обраний період записи активності та харчування відсутні.",
                    styles["Normal"],
                )
            )

        doc.build(story)
        buf.seek(0)
        return buf.read()

    async def generate_excel(
        self, user_id: int, date_from: date, date_to: date
    ) -> bytes:
        """Генерує Excel-файл з сирими даними активності та харчування."""
        import openpyxl

        activities = await self._activity_repo.get_by_date_range(
            user_id, date_from, date_to
        )
        nutrition = await self._nutrition_repo.get_by_date_range(
            user_id, date_from, date_to
        )

        wb = openpyxl.Workbook()

        ws_act = wb.active
        ws_act.title = "Активність"
        ws_act.append(["ID", "Тип", "Тривалість (хв)", "Калорії", "Дата"])

        for activity in activities:
            ws_act.append(
                [
                    activity.id,
                    self._format_activity(activity.activity_type),
                    int(self._num(activity.duration_minutes)),
                    float(self._num(activity.calories_burned)),
                    self._date_text(activity.created_at),
                ]
            )

        ws_nut = wb.create_sheet("Харчування")
        ws_nut.append(
            [
                "ID",
                "Прийом",
                "Страва",
                "Грами",
                "Калорії",
                "Білки",
                "Жири",
                "Вуглеводи",
                "Дата",
            ]
        )

        for item in nutrition:
            ws_nut.append(
                [
                    item.id,
                    self._format_meal(item.meal_type),
                    self._text(item.food_name),
                    float(self._num(item.amount_grams)),
                    float(self._num(item.calories_intake)),
                    float(self._num(item.proteins)),
                    float(self._num(item.fats)),
                    float(self._num(item.carbohydrates)),
                    self._date_text(item.date),
                ]
            )

        for sheet in wb.worksheets:
            for column_cells in sheet.columns:
                max_length = 0
                column_letter = column_cells[0].column_letter

                for cell in column_cells:
                    value = cell.value
                    if value is not None:
                        max_length = max(max_length, len(str(value)))

                sheet.column_dimensions[column_letter].width = min(max_length + 2, 35)

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf.read()

    async def find_recipient_by_phone(self, phone: str):
        """Знаходить користувача-отримувача за номером телефону."""
        return await self._profile_repo.get_by_phone(phone)

    async def get_user_by_id(self, user_id: int):
        """Повертає користувача за Telegram ID."""
        return await self._profile_repo.get_by_telegram_id(user_id)