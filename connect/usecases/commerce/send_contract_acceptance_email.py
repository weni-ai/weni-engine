"""Send the self-serve contract acceptance email to a commerce user.

Triggered by the retail module once a customer accepts a self-serve
contract. The retail owns subject/body composition and translation; this
use case only delivers the message with the contract PDF attached.
"""

import base64
import logging

from django.conf import settings
from django.core.cache import cache

from connect.common.utils import send_html_email
from connect.usecases.commerce.dto import SendContractAcceptanceEmailDTO


logger = logging.getLogger(__name__)


PDF_MIME_TYPE = "application/pdf"

IDEMPOTENCY_KEY_PREFIX = "contract-acceptance-email"
IDEMPOTENCY_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days


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

        attachment = self._build_attachment(dto.file_name, dto.file_base64)
        send_html_email(
            subject=dto.subject,
            to=dto.user_email,
            html_content=dto.body_html,
            attachments=[attachment],
        )

        cache.set(idempotency_key, True, IDEMPOTENCY_TTL_SECONDS)
        logger.info(
            f"Contract acceptance email dispatched user_email={dto.user_email} "
            f"acceptance_id={dto.acceptance_id}"
        )
        return True

    def _build_attachment(self, file_name: str, file_base64: str) -> tuple:
        return (file_name, base64.b64decode(file_base64), PDF_MIME_TYPE)
