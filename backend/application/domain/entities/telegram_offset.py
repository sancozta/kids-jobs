from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class TelegramOffset:
    source_name: str
    chat_id: str
    last_message_id: int = 0
    id: Optional[int] = None
    updated_at: Optional[datetime] = None
