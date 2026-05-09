"""Репозиторій соціальної взаємодії."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from src.models.domain import Challenge, ChallengeParticipant, Friendship, FriendshipStatus
from src.repository.base_repo import BaseRepository


class SocialRepository:
    """Репозиторій челенджів та зв'язків між користувачами."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_challenge(self, challenge: Challenge) -> Challenge:
        self._session.add(challenge)
        await self._session.commit()
        await self._session.refresh(challenge)
        return challenge

    async def get_challenge_by_id(self, challenge_id: int) -> Challenge | None:
        return await self._session.get(Challenge, challenge_id)

    async def get_user_challenges(self, user_id: int) -> list[Challenge]:
        result = await self._session.execute(
            select(Challenge).where(Challenge.creator_id == user_id)
        )
        return list(result.scalars().all())

    async def get_participant(
        self, challenge_id: int, user_id: int
    ) -> ChallengeParticipant | None:
        """Повертає участь користувача в челенджі, якщо вона вже існує."""
        result = await self._session.execute(
            select(ChallengeParticipant).where(
                ChallengeParticipant.challenge_id == challenge_id,
                ChallengeParticipant.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def join_challenge(
        self, challenge_id: int, user_id: int
    ) -> ChallengeParticipant:
        existing = await self.get_participant(challenge_id, user_id)
        if existing:
            return existing

        participant = ChallengeParticipant(
            challenge_id=challenge_id, user_id=user_id
        )
        self._session.add(participant)
        await self._session.commit()
        await self._session.refresh(participant)
        return participant

    async def update_progress(
        self, challenge_id: int, user_id: int, progress: float
    ) -> None:
        result = await self._session.execute(
            select(ChallengeParticipant).where(
                ChallengeParticipant.challenge_id == challenge_id,
                ChallengeParticipant.user_id == user_id,
            )
        )
        participant = result.scalar_one_or_none()
        if participant:
            participant.progress = progress
            await self._session.commit()

    async def get_existing_friendship(
        self, requester_id: int, addressee_id: int
    ) -> Friendship | None:
        """Перевіряє, чи існує зв'язок або запит між двома користувачами."""
        result = await self._session.execute(
            select(Friendship).where(
                or_(
                    (Friendship.requester_id == requester_id)
                    & (Friendship.addressee_id == addressee_id),
                    (Friendship.requester_id == addressee_id)
                    & (Friendship.addressee_id == requester_id),
                )
            )
        )
        return result.scalar_one_or_none()

    async def send_friend_request(self, friendship: Friendship) -> Friendship:
        self._session.add(friendship)
        await self._session.commit()
        await self._session.refresh(friendship)
        return friendship

    async def get_friends(self, user_id: int) -> list[Friendship]:
        result = await self._session.execute(
            select(Friendship).where(
                (Friendship.requester_id == user_id) |
                (Friendship.addressee_id == user_id),
                Friendship.status == FriendshipStatus.ACCEPTED,
            )
        )
        return list(result.scalars().all())
