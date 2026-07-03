"""Send a business verification result email to the customer.

Triggered by the integrations-engine after it processes the
PARTNER_CLIENT_CERTIFICATION_STATUS_UPDATE webhook from Meta.
"""

import logging
from typing import Iterable, Optional

from django.conf import settings
from django.utils import translation
from django.utils.translation import ugettext_lazy as _

from connect.authentication.models import User
from connect.common.utils import send_email


logger = logging.getLogger(__name__)


APPROVED_STATUS = "APPROVED"
FAILED_STATUS = "FAILED"

TEMPLATE_TXT = "common/emails/business_verification/result.txt"
TEMPLATE_HTML = "common/emails/business_verification/result.html"

DEFAULT_SUPPORT_URL = "https://wenivtex.zendesk.com/hc/en-us"


class NotifyBusinessVerificationUseCase:
    """Render and send the verification result email respecting the user language."""

    def execute(
        self,
        user_email: str,
        status: str,
        rejection_reasons: Optional[Iterable[str]] = None,
        verification_attempts: int = 0,
        language: Optional[str] = None,
    ) -> bool:
        if not settings.SEND_EMAILS:
            logger.info(
                f"SEND_EMAILS is disabled; skipping business verification email "
                f"to user_email={user_email}"
            )
            return False

        resolved_language = self._resolve_language(user_email=user_email, language=language)
        is_approved = status == APPROVED_STATUS
        context = {
            "is_approved": is_approved,
            "support_url": getattr(
                settings, "BUSINESS_VERIFICATION_SUPPORT_URL", DEFAULT_SUPPORT_URL
            ),
        }

        with translation.override(resolved_language):
            subject = (
                _("Your WhatsApp Business account has been verified")
                if is_approved
                else _("Your business verification was not approved")
            )
            send_email(
                subject=str(subject),
                to=user_email,
                template_txt=TEMPLATE_TXT,
                template_html=TEMPLATE_HTML,
                context=context,
            )

        logger.info(
            f"Business verification email dispatched user_email={user_email} "
            f"status={status} language={resolved_language} "
            f"attempts={verification_attempts} reasons={list(rejection_reasons or [])}"
        )
        return True

    def _resolve_language(self, user_email: str, language: Optional[str]) -> str:
        if language:
            return language
        user = User.objects.filter(email=user_email).only("language").first()
        if user and user.language:
            return user.language
        return settings.DEFAULT_LANGUAGE
