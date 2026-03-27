from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint

from application.domain.entities.telegram_offset import TelegramOffset
from configuration.database_configuration import Base


class TelegramOffsetModel(Base):
    __tablename__ = "telegram_offsets"
    __table_args__ = (
        UniqueConstraint("source_name", "chat_id", name="uq_telegram_offsets_source_chat"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_name = Column(String, nullable=False, index=True)
    chat_id = Column(String, nullable=False, index=True)
    last_message_id = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_entity(self) -> TelegramOffset:
        return TelegramOffset(
            id=self.id,
            source_name=self.source_name,
            chat_id=self.chat_id,
            last_message_id=self.last_message_id,
            updated_at=self.updated_at,
        )

    @staticmethod
    def from_entity(entity: TelegramOffset) -> "TelegramOffsetModel":
        return TelegramOffsetModel(
            id=entity.id,
            source_name=entity.source_name,
            chat_id=entity.chat_id,
            last_message_id=entity.last_message_id,
        )
