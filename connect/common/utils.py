import json

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def send_email(subject, to, template_txt, template_html=None, context=None):
    """
    Send email with SendGrid integration for unsubscribe list.
    """
    if not settings.SEND_EMAILS:
        return

    text_content = render_to_string(template_txt, context)
    html_content = None
    if template_html:
        html_content = render_to_string(template_html, context)

    unsubscribe_group_id = getattr(settings, "SENDGRID_UNSUBSCRIBE_GROUP_ID", None)
    headers = {}
    if unsubscribe_group_id:
        headers["X-SMTPAPI"] = json.dumps(
            {"asm": {"group_id": int(unsubscribe_group_id)}}
        )

    if not isinstance(to, list):
        to = [to]

    msg = EmailMultiAlternatives(subject, text_content, None, to, headers=headers)
    if html_content:
        msg.attach_alternative(html_content, "text/html")

    return msg.send()
