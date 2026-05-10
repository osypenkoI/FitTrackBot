"""
Сервіс генерації звітів у форматах PDF та Excel.
"""

import io
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from src.repository.activity_repo import ActivityRepository
from src.repository.nutrition_repo import NutritionRepository
from src.repository.profile_repo import ProfileRepository


class ReportingService:
    """Сервіс генерації PDF та Excel-звітів з даними активності."""

    def __init__(self, session: AsyncSession) -> None:
        self._activity_repo = ActivityRepository(session)
        self._nutrition_repo = NutritionRepository(session)
        self._profile_repo = ProfileRepository(session)

    async def generate_pdf(
        self, user_id: int, date_from: date, date_to: date
    ) -> bytes:
        """Генерує PDF-звіт з даними активності та харчування."""
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        )
        from reportlab.lib import colors
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

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
                    f"Вага: {metrics.weight} кг | Зріст: {metrics.height} см | "
                    f"BMR: {metrics.bmr} ккал | TDEE: {metrics.tdee} ккал",
                    styles["Normal"],
                )
            )
            story.append(Spacer(1, 12))

        if activities:
            story.append(Paragraph("Активність:", styles["Heading2"]))
            data = [["Тип", "Тривалість (хв)", "Калорії", "Дата"]]
            for a in activities[:20]:
                data.append([
                    a.activity_type,
                    str(a.duration_minutes),
                    f"{a.calories_burned:.0f}",
                    str(a.created_at.date()),
                ])
            table = Table(data)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ]))
            story.append(table)

        doc.build(story)
        buf.seek(0)
        return buf.read()

    async def generate_excel(
        self, user_id: int, date_from: date, date_to: date
    ) -> bytes:
        """Генерує Excel-файл з сирими даними активності."""
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
        for a in activities:
            ws_act.append([
                a.id, a.activity_type, a.duration_minutes,
                round(a.calories_burned, 1), str(a.created_at.date()),
            ])

        ws_nut = wb.create_sheet("Харчування")
        ws_nut.append(["ID", "Прийом", "Страва", "Грами", "Калорії", "Дата"])
        for n in nutrition:
            ws_nut.append([
                n.id, n.meal_type, n.food_name,
                n.amount_grams, round(n.calories_intake, 1), str(n.date),
            ])

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