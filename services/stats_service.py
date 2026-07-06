# services/stats_service.py
from db.repositories import UserRepository

class StatsService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def get_total_users(self) -> int:
        return await self.user_repo.get_total_users_count()

    async def get_active_subscriptions_count(self) -> int:
        return await self.user_repo.count_active_subscriptions()

    async def get_top_users(self, limit=10) -> list[dict]:
        return await self.user_repo.get_top_users_by_queries(limit)

    async def get_referral_count(self) -> int:
        return await self.user_repo.get_referral_users_count()

    async def get_active_chats_count(self) -> int:
        return await self.user_repo.get_active_chats_count()