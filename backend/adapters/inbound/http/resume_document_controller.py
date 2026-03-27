"""Resume document HTTP controller."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from adapters.inbound.http.schemas.resume_email_schema import ResumeEmailSendResponseSchema, ResumeEmailSendSchema
from adapters.inbound.http.schemas.resume_document_schema import ResumeDocumentPayloadSchema, ResumeDocumentResponseSchema
from adapters.outbound.persistence.resume_document_persistence_adapter import ResumeDocumentPersistenceAdapter
from application.domain.services.resume_email_service import ResumeEmailService
from application.domain.services.resume_document_service import ResumeDocumentService
from configuration.database_configuration import get_db

router = APIRouter(prefix="/api/v1/resume-document", tags=["resume-document"])


def _service_from_db(db: Session) -> ResumeDocumentService:
    return ResumeDocumentService(repository=ResumeDocumentPersistenceAdapter(session=db))


@router.get("/", response_model=ResumeDocumentResponseSchema)
def get_resume_document(
    locale: Literal["pt", "en"] = Query(default="pt"),
    db: Session = Depends(get_db),
):
    document = _service_from_db(db).get_default(locale=locale)
    if document is None:
        raise HTTPException(status_code=404, detail="Resume document not found")
    return ResumeDocumentResponseSchema.model_validate(document)


@router.put("/", response_model=ResumeDocumentResponseSchema, status_code=status.HTTP_200_OK)
def save_resume_document(
    body: ResumeDocumentPayloadSchema,
    locale: Literal["pt", "en"] = Query(default="pt"),
    db: Session = Depends(get_db),
):
    saved = _service_from_db(db).save_default(body.payload, locale=locale)
    db.commit()
    return ResumeDocumentResponseSchema.model_validate(saved)


@router.post("/send-email", response_model=ResumeEmailSendResponseSchema, status_code=status.HTTP_200_OK)
def send_resume_email(body: ResumeEmailSendSchema):
    email_id = ResumeEmailService().send_resume_email(
        to_email=body.to_email,
        subject=body.subject,
        message=body.message,
        sender_profile=body.sender_profile,
        reply_to_email=body.reply_to_email,
        resume_payload=body.resume_payload,
        filename=body.filename,
        locale=body.locale,
    )
    return ResumeEmailSendResponseSchema(status="sent", email_id=email_id)
