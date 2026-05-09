"""
Базовий репозиторій із загальними CRUD-операціями.
Патерн Template Method — визначає кістяк операцій, дочірні класи реалізують деталі.
"""

from typing import TypeVar, Generic, Type
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from src.database.connection import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Базовий клас репозиторію з типізованими CRUD-операціями."""

    def __init__(self, model: Type[ModelType], session: AsyncSession) -> None:
        self._model = model
        self._session = session

    async def get_by_id(self, record_id: int) -> ModelType | None:
        """Отримує запис за первинним ключем."""
        result = await self._session.get(self._model, record_id)
        return result

    async def get_all(self) -> list[ModelType]:
        """Повертає всі записи таблиці."""
        result = await self._session.execute(select(self._model))
        return list(result.scalars().all())

    async def save(self, entity: ModelType) -> ModelType:
        """Зберігає новий або оновлює існуючий запис."""
        self._session.add(entity)
        await self._session.commit()
        await self._session.refresh(entity)
        return entity

    async def delete_by_id(self, record_id: int) -> bool:
        """Видаляє запис за первинним ключем. Повертає True якщо успішно."""
        stmt = delete(self._model).where(
            self._model.__mapper__.primary_key[0] == record_id
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.rowcount > 0
