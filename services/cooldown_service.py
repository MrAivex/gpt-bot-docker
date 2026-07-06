# services/cooldown_service.py
from collections import OrderedDict
from datetime import datetime, timedelta
from config.logger import logger

class LimitedDict(OrderedDict):
    def __init__(self, limit=10000):
        self.limit = limit
        super().__init__()

    def __setitem__(self, key, value):
        if key in self:
            del self[key]
        if len(self) >= self.limit:
            self.popitem(last=False)
        super().__setitem__(key, value)

class CooldownService:
    def __init__(self, cooldown_seconds: int = 3):
        self.cooldown_seconds = cooldown_seconds
        self.last_message_time = LimitedDict(limit=10000)

    def is_allowed(self, user_id: int) -> bool:
        now = datetime.now()
        last_time = self.last_message_time.get(user_id)
        if last_time and (now - last_time) < timedelta(seconds=self.cooldown_seconds):
            logger.warning(f"Cooldown: user {user_id} слишком часто.")
            return False
        self.last_message_time[user_id] = now
        return True