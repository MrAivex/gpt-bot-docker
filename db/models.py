from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from ai.providers import DEFAULT_MODEL


@dataclass
class User:
    user_id: int
    used_queries: int = 0
    sub_queries: int = 0
    total_queries: int = 0
    subscription_status: str = 'inactive'
    subscription_start: Optional[datetime] = None
    subscription_end: Optional[datetime] = None
    last_active: Optional[datetime] = None
    user_email: Optional[str] = None
    payment_token: Optional[str] = None
    referrer_id: Optional[int] = None
    chat_id: Optional[int] = None
    subscribe_on_channel: Optional[str] = None
    bonus_queries: int = 10
    selected_model: str = DEFAULT_MODEL