"""Service for sending resume emails through Resend."""
import base64
from html import escape

import requests

from application.domain.exceptions.domain_exceptions import DomainException
from application.domain.services.resume_pdf_service import ResumePdfService
from configuration.settings_configuration import settings


class ResumeEmailService:
    API_URL = "https://api.resend.com/emails"

    def send_resume_email(
        self,
        *,
        to_email: str,
        subject: str,
        message: str,
        sender_profile: str,
        reply_to_email: str,
        resume_payload: dict,
        filename: str,
        locale: str = "pt",
    ) -> str:
        if not settings.resend_api_key:
            raise DomainException("RESEND_API_KEY nao configurada", status_code=500)
        if not settings.resend_from_email:
            raise DomainException("RESEND_FROM_EMAIL nao configurado", status_code=500)

        pdf_bytes = ResumePdfService().render_resume_pdf(resume_payload=resume_payload, locale=locale)
        pdf_base64 = base64.b64encode(pdf_bytes).decode("ascii")
        normalized_message = self._normalize_plaintext_message(message)
        html_body = self._build_html_body(normalized_message)
        sender = self._resolve_sender(sender_profile=sender_profile, reply_to_email=reply_to_email)
        payload = {
            "from": sender["from"],
            "to": [to_email.strip()],
            "subject": subject.strip(),
            "text": normalized_message or "Curriculo em anexo.",
            "html": (
                '<div style="font-family:Trebuchet MS,Tahoma,Verdana,Arial,sans-serif;'
                'font-size:14px;line-height:1.6;color:#111">'
                f"{html_body}"
                "</div>"
            ),
            "attachments": [
                {
                    "filename": filename.strip() or "curriculo.pdf",
                    "content": pdf_base64,
                }
            ],
        }
        if sender["reply_to"]:
            payload["reply_to"] = sender["reply_to"]
        response = requests.post(
            self.API_URL,
            headers={
                "Authorization": f"Bearer {settings.resend_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        if response.status_code >= 400:
            raise DomainException(f"Falha ao enviar email via Resend: {response.text}", status_code=502)
        data = response.json()
        email_id = data.get("id")
        if not email_id:
            raise DomainException("Resposta invalida do Resend ao enviar email", status_code=502)
        return email_id

    @staticmethod
    def _normalize_plaintext_message(message: str | None) -> str:
        raw = (message or "").strip()
        if not raw:
            return ""

        paragraphs = []
        for block in raw.split("\n\n"):
            lines = [line.strip() for line in block.splitlines() if line.strip()]
            if not lines:
                continue
            paragraphs.append("\n".join(lines))

        return "\n\n".join(paragraphs)

    @staticmethod
    def _build_html_body(message: str | None) -> str:
        raw = (message or "").strip()
        if not raw:
            return "Curriculo em anexo."

        paragraphs = []
        for block in raw.split("\n\n"):
            lines = [escape(line.strip()) for line in block.splitlines() if line.strip()]
            if not lines:
                continue
            paragraphs.append(f'<div style="margin:0;">{"<br/>".join(lines)}</div>')

        return '<div style="height:16px;line-height:16px;">&nbsp;</div>'.join(paragraphs) or "Curriculo em anexo."

    @staticmethod
    def _format_from_email(name: str, email: str) -> str:
        if name:
            return f"{name} <{email}>"
        return email

    def _resolve_sender(self, *, sender_profile: str, reply_to_email: str) -> dict[str, str]:
        sanitized_reply_to = (reply_to_email or "").strip()

        if sender_profile == "personal":
            from_email = (settings.resend_personal_from_email or settings.resend_from_email).strip()
            from_name = (settings.resend_personal_from_name or settings.resend_from_name).strip()
            reply_to = sanitized_reply_to or (settings.resend_personal_reply_to_email or settings.resend_from_email).strip()
            return {
                "from": self._format_from_email(from_name, from_email),
                "reply_to": reply_to,
            }

        from_email = settings.resend_from_email.strip()
        from_name = settings.resend_from_name.strip()
        reply_to = sanitized_reply_to or settings.resend_company_reply_to_email.strip()
        return {
            "from": self._format_from_email(from_name, from_email),
            "reply_to": reply_to,
        }
