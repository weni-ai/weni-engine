"""Send the data export ready email to a commerce user.

Triggered by the commerce module once an export file is processed and
available for download.
"""

import logging
from datetime import date

from django.conf import settings
from django.utils import translation
from django.utils.translation import ugettext_lazy as _

from connect.authentication.models import User
from connect.common.utils import send_email
from connect.usecases.commerce.dto import SendDataExportEmailDTO


logger = logging.getLogger(__name__)


TEMPLATE_TXT = "common/emails/data_export/email.txt"
TEMPLATE_HTML = "common/emails/data_export/email.html"

ENGLISH_LANGUAGE = "en-us"
ALL_TEMPLATE_OPTION = "all"

STATUS_LABELS = {
    "all": _("All"),
    "processing": _("Processing"),
    "skipped": _("Skipped"),
    "error": _("Error"),
    "sent": _("Sent"),
    "delivered": _("Delivered"),
    "read": _("Read"),
}


class SendDataExportEmailUseCase:
    """Render and send the data export email respecting the user language."""

    def execute(self, dto: SendDataExportEmailDTO) -> bool:
        if not settings.SEND_EMAILS:
            logger.info(
                f"SEND_EMAILS is disabled; skipping data export email "
                f"to user_email={dto.user_email}"
            )
            return False

        language = self._resolve_language(dto.user_email, dto.language)

        with translation.override(language):
            context = {
                "file_url": dto.file_url,
                "period": self._build_period(dto.start_date, dto.end_date, language),
                "template_label": self._build_template_label(dto.template),
                "status_label": str(STATUS_LABELS[dto.status]),
            }
            send_email(
                subject=str(_("Your data export is ready")),
                to=dto.user_email,
                template_txt=TEMPLATE_TXT,
                template_html=TEMPLATE_HTML,
                context=context,
            )

        logger.info(
            f"Data export email dispatched user_email={dto.user_email} "
            f"status={dto.status} template={dto.template} language={language}"
        )
        return True

    def _resolve_language(self, user_email: str, language: str) -> str:
        if language:
            return language
        user = User.objects.filter(email=user_email).only("language").first()
        if user and user.language:
            return user.language
        return settings.DEFAULT_LANGUAGE

    def _build_period(self, start_date: date, end_date: date, language: str) -> str:
        date_format = "%m/%d/%Y" if language == ENGLISH_LANGUAGE else "%d/%m/%Y"
        return f"{start_date.strftime(date_format)} ~ {end_date.strftime(date_format)}"

    def _build_template_label(self, template: str) -> str:
        if template.lower() == ALL_TEMPLATE_OPTION:
            return str(_("All"))
        return template
