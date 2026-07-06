# services/limit_service.py
from db.repositories import UserRepository
from config.main import ADMIN_ID

class LimitService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def check_and_deduct(self, user_id: int, cost: int = 1) -> tuple[bool, int]:
        """
        Возвращает (можно_ли_продолжить, оставшиеся_запросы).
        Если нельзя – возвращает (False, 0) и не списывает.
        """
        user = await self.user_repo.get_user(user_id)
        if not user:
            return False, 0

        # Администраторы безлимитны
        if user_id in ADMIN_ID:
            return True, None  # None = безлимит

        # Списываем
        success = await self.user_repo.decrement_queries(user_id, cost)
        if not success:
            balance = user.sub_queries + user.bonus_queries
            return False, balance
        
        updated = await self.user_repo.get_user(user_id)
        new_balance = updated.sub_queries + updated.bonus_queries if updated else 0
        return True, new_balance