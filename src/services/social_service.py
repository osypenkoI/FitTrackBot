"""Сервіс соціальної взаємодії: челенджі, друзі, лідерборд."""

from sqlalchemy.ext.asyncio import AsyncSession
from src.models.domain import Challenge, Friendship
from src.models.dto import ChallengeCreateDTO
from src.repository.social_repo import SocialRepository
from src.repository.analytics_repo import AnalyticsRepository
from src.repository.profile_repo import ProfileRepository
from src.validators.pydantic_validator import PydanticValidator


class SocialService:
    """Сервіс управління соціальними функціями FitTrackBot."""

    def __init__(self, session: AsyncSession) -> None:
        self._social_repo = SocialRepository(session)
        self._analytics_repo = AnalyticsRepository(session)
        self._profile_repo = ProfileRepository(session)
        self._validator = PydanticValidator()

    async def create_challenge(
        self, data: dict
    ) -> tuple[Challenge | None, str]:
        """Створює новий челендж."""
        dto, error = self._validator.validate_challenge(data)
        if error:
            return None, error

        challenge = Challenge(
            creator_id=dto.creator_id,
            title=dto.title,
            description=dto.description,
            goal_value=dto.goal_value,
            metric=dto.metric,
            start_date=dto.start_date,
            end_date=dto.end_date,
        )
        saved = await self._social_repo.create_challenge(challenge)
        return saved, ""

    async def join_challenge(
        self, challenge_id: int, user_id: int
    ) -> tuple[bool, str]:
        """Додає користувача до челенджу."""
        challenge = await self._social_repo.get_challenge_by_id(challenge_id)
        if not challenge:
            return False, "Челендж не знайдено."

        existing = await self._social_repo.get_participant(challenge_id, user_id)
        if existing:
            return False, "Ви вже берете участь у цьому челенджі."

        await self._social_repo.join_challenge(challenge_id, user_id)
        return True, ""

    async def get_leaderboard(self, metric: str = "calories_burned") -> list[dict]:
        """Повертає рейтинг користувачів за метрикою."""
        return await self._analytics_repo.get_leaderboard(metric)

    async def send_friend_request(
        self, requester_id: int, addressee_phone: str
    ) -> tuple[bool, str]:
        """Надсилає запит дружби за номером телефону."""
        addressee = await self._profile_repo.get_by_phone(addressee_phone)
        if not addressee:
            return False, "Користувача з таким номером телефону не знайдено."

        if addressee.user_id == requester_id:
            return False, "Не можна надіслати запит дружби самому собі."

        existing = await self._social_repo.get_existing_friendship(
            requester_id, addressee.user_id
        )
        if existing:
            return False, "Запит дружби або зв'язок із цим користувачем уже існує."

        friendship = Friendship(
            requester_id=requester_id,
            addressee_id=addressee.user_id,
        )
        await self._social_repo.send_friend_request(friendship)
        return True, ""

    async def get_user_challenges(self, user_id: int) -> list[Challenge]:
        """Повертає список челенджів користувача."""
        return await self._social_repo.get_user_challenges(user_id)

    async def get_challenge_progress(self, challenge_id: int) -> list[dict]:
        """
        Повертає прогрес усіх учасників челенджу у реальному часі (ФВ 5.1.4).
        """
        challenge = await self._social_repo.get_challenge_by_id(challenge_id)
        if not challenge:
            return []
        # Беремо учасників
        from sqlalchemy import select
        from src.models.domain import ChallengeParticipant, User
        result = await self._social_repo._session.execute(
            select(ChallengeParticipant, User)
            .join(User, ChallengeParticipant.user_id == User.user_id)
            .where(ChallengeParticipant.challenge_id == challenge_id)
        )
        rows = result.all()
        entries = []
        for participant, user in rows:
            # Оновлюємо прогрес з реальних даних
            if challenge.metric == "calories_burned":
                from src.repository.activity_repo import ActivityRepository
                act_repo = ActivityRepository(self._social_repo._session)
                current = await act_repo.get_total_calories(user.user_id)
            elif challenge.metric == "duration_minutes":
                from src.repository.activity_repo import ActivityRepository
                act_repo = ActivityRepository(self._social_repo._session)
                records = await act_repo.get_time_series(user.user_id, days=30)
                current = float(sum(r.duration_minutes for r in records))
            else:
                current = participant.progress

            await self._social_repo.update_progress(challenge_id, user.user_id, current)
            entries.append({
                "user_id": user.user_id,
                "username": user.username,
                "progress": round(current, 1),
                "target": challenge.goal_value,
            })
        # Сортуємо за прогресом спадаючи
        entries.sort(key=lambda x: x["progress"], reverse=True)
        return entries
