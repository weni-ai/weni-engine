"""Send the self-serve contract acceptance email to a commerce user.

Triggered by the retail module once a customer accepts a self-serve
contract. Connect owns the template, subject, and translation; retail
sends the per-acceptance facts and the contract PDF.
"""

import base64
import logging
from datetime import datetime

from django.conf import settings
from django.core.cache import cache
from django.template.loader import render_to_string
from django.utils import translation
from django.utils.translation import ugettext_lazy as _

from connect.common.utils import send_html_email
from connect.usecases.commerce.dto import SendContractAcceptanceEmailDTO


logger = logging.getLogger(__name__)


PDF_MIME_TYPE = "application/pdf"
TEMPLATE_HTML = "common/emails/contract_acceptance.html"
TEMPLATE_TXT = "common/emails/contract_acceptance.txt"

IDEMPOTENCY_KEY_PREFIX = "contract-acceptance-email"
IDEMPOTENCY_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days

ENGLISH_LANGUAGE = "en-us"
LANGUAGE_BY_PREFIX = {
    "pt": "pt-br",
    "es": "es",
    "en": ENGLISH_LANGUAGE,
}
MONTH_FIRST_DATE_FORMAT = "%m/%d/%Y"
DAY_FIRST_DATE_FORMAT = "%d/%m/%Y"
MISSING_PLAN_PLACEHOLDER = "-"


class SendContractAcceptanceEmailUseCase:
    """Deliver the contract acceptance email with the PDF attached.

    Deduplicates by ``acceptance_id`` so retail retries do not deliver the
    same contract twice.
    """

    def execute(self, dto: SendContractAcceptanceEmailDTO) -> bool:
        if not settings.SEND_EMAILS:
            logger.info(
                f"SEND_EMAILS is disabled; skipping contract acceptance email "
                f"to user_email={dto.user_email}"
            )
            return False

        idempotency_key = f"{IDEMPOTENCY_KEY_PREFIX}:{dto.acceptance_id}"
        if cache.get(idempotency_key):
            logger.info(
                f"Contract acceptance email already sent "
                f"acceptance_id={dto.acceptance_id}; skipping"
            )
            return True

        language = self._resolve_language(dto.language)
        context = self._build_context(dto, language)
        attachment = self._build_attachment(dto.file_name, dto.file_base64)
        with translation.override(language):
            send_html_email(
                subject=str(_("Your contract")),
                to=dto.user_email,
                html_content=render_to_string(TEMPLATE_HTML, context),
                text_content=render_to_string(TEMPLATE_TXT, context),
                attachments=[attachment],
            )

        cache.set(idempotency_key, True, IDEMPOTENCY_TTL_SECONDS)
        logger.info(
            f"Contract acceptance email dispatched user_email={dto.user_email} "
            f"acceptance_id={dto.acceptance_id}"
        )
        return True

    def _resolve_language(self, language: str) -> str:
        prefix = (language or "").split("-")[0].lower()
        return LANGUAGE_BY_PREFIX.get(prefix, settings.DEFAULT_LANGUAGE)

    def _build_context(
        self, dto: SendContractAcceptanceEmailDTO, language: str
    ) -> dict:
        return {
            "plan": dto.plan_name or MISSING_PLAN_PLACEHOLDER,
            "version": dto.contract_version,
            "date": self._format_accepted_at(dto.accepted_at, language),
        }

    def _format_accepted_at(self, accepted_at: datetime, language: str) -> str:
        date_format = (
            MONTH_FIRST_DATE_FORMAT
            if language == ENGLISH_LANGUAGE
            else DAY_FIRST_DATE_FORMAT
        )
        return accepted_at.strftime(date_format)

    def _build_attachment(self, file_name: str, file_base64: str) -> tuple:
        return (file_name, base64.b64decode(file_base64), PDF_MIME_TYPE)
