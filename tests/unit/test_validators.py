"""Модульні тести PydanticValidator."""

import pytest
from src.validators.pydantic_validator import PydanticValidator


class TestRegistrationValidation:
    """Тести валідації реєстрації."""

    def test_valid_registration(self):
        """Коректні дані успішно проходять валідацію."""
        validator = PydanticValidator()
        data = {
            "telegram_id": 123456,
            "weight": 70.0,
            "height": 175.0,
            "age": 25,
            "gender": "male",
            "activity_level": "medium",
            "target_goal": "maintain",
        }
        dto, error = validator.validate_registration(data)
        assert dto is not None
        assert error == ""

    def test_invalid_weight(self):
        """Від'ємна вага не проходить валідацію."""
        validator = PydanticValidator()
        data = {
            "telegram_id": 1,
            "weight": -10.0,
            "height": 175.0,
            "age": 25,
            "gender": "male",
            "activity_level": "medium",
            "target_goal": "maintain",
        }
        dto, error = validator.validate_registration(data)
        assert dto is None
        assert error != ""

    def test_invalid_gender(self):
        """Некоректний гендер не проходить валідацію."""
        validator = PydanticValidator()
        data = {
            "telegram_id": 1,
            "weight": 70.0,
            "height": 175.0,
            "age": 25,
            "gender": "robot",  # невалідне
            "activity_level": "medium",
            "target_goal": "maintain",
        }
        dto, error = validator.validate_registration(data)
        assert dto is None
        assert "gender" in error or error != ""


class TestActivityValidation:
    """Тести валідації активності."""

    def test_valid_activity(self):
        data = {
            "user_id": 1,
            "activity_type": "running",
            "duration_minutes": 30,
        }
        validator = PydanticValidator()
        dto, error = validator.validate_activity(data)
        assert dto is not None
        assert error == ""

    def test_invalid_activity_type(self):
        data = {
            "user_id": 1,
            "activity_type": "teleportation",
            "duration_minutes": 30,
        }
        validator = PydanticValidator()
        dto, error = validator.validate_activity(data)
        assert dto is None
        assert error != ""

    def test_zero_duration_invalid(self):
        data = {
            "user_id": 1,
            "activity_type": "cardio",
            "duration_minutes": 0,
        }
        validator = PydanticValidator()
        dto, error = validator.validate_activity(data)
        assert dto is None
