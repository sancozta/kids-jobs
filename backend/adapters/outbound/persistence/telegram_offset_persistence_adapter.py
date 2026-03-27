from __future__ import annotations

from sqlalchemy.orm import Session

from adapters.outbound.persistence.models.telegram_offset_model import TelegramOffsetModel
from application.domain.entities.telegram_offset import TelegramOffset


class TelegramOffsetPersistenceAdapter:
    def __init__(self, session: Session):
        self.session = session

    def find(self, source_name: str, chat_id: str) -> TelegramOffset | None:
        model = (
            self.session.query(TelegramOffsetModel)
            .filter_by(source_name=source_name, chat_id=chat_id)
            .first()
        )
        return model.to_entity() if model else None

    def save_or_update(self, source_name: str, chat_id: str, last_message_id: int) -> TelegramOffset:
        model = (
            self.session.query(TelegramOffsetModel)
            .filter_by(source_name=source_name, chat_id=chat_id)
            .first()
        )
        if model is None:
            model = TelegramOffsetModel(
                source_name=source_name,
                chat_id=chat_id,
                last_message_id=last_message_id,
            )
            self.session.add(model)
        else:
            model.last_message_id = last_message_id
        self.session.commit()
        self.session.refresh(model)
        return model.to_entity()
