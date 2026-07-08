import json

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags


def _build_sendgrid_headers():
    unsubscribe_group_id = getattr(settings, "SENDGRID_UNSUBSCRIBE_GROUP_ID", None)
    if not unsubscribe_group_id:
        return {}
    return {"X-SMTPAPI": json.dumps({"asm": {"group_id": int(unsubscribe_group_id)}})}


def _dispatch_email(subject, to, text_content, html_content=None, attachments=None):
    """Build and send an email, attaching the HTML alternative and files.

    ``attachments`` is an optional iterable of ``(filename, content, mimetype)``
    tuples forwarded to ``EmailMultiAlternatives.attach``.
    """
    if not isinstance(to, list):
        to = [to]

    msg = EmailMultiAlternatives(
        subject, text_content, None, to, headers=_build_sendgrid_headers()
    )
    if html_content:
        msg.attach_alternative(html_content, "text/html")

    for attachment in attachments or []:
        msg.attach(*attachment)

    return msg.send()


def send_email(subject, to, template_txt, template_html=None, context=None):
    """
    Send email with SendGrid integration for unsubscribe list.
    """
    if not settings.SEND_EMAILS:
        return

    text_content = render_to_string(template_txt, context)
    html_content = render_to_string(template_html, context) if template_html else None

    return _dispatch_email(subject, to, text_content, html_content)


def send_html_email(subject, to, html_content, text_content="", attachments=None):
    """
    Send an email from already-rendered subject and HTML body.

    Used when the caller owns composition/translation and the platform only
    needs to deliver the message (e.g. transactional emails built upstream).
    """
    if not settings.SEND_EMAILS:
        return

    if not text_content and html_content:
        text_content = strip_tags(html_content).strip()

    return _dispatch_email(subject, to, text_content, html_content, attachments)
