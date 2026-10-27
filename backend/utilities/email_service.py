from django.conf import settings
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from celery import shared_task
import smtplib

EMAIL_SERVICE_MAX_RETRIES = 3


@shared_task(
    bind=True,
    autoretry_for=(smtplib.SMTPException, ConnectionError),
    retry_kwargs={
        "max_retries": EMAIL_SERVICE_MAX_RETRIES,
    },
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def send_email_task(
    self,
    subject: str,
    recipients: list,
    template_html: str,
    template_txt: str = None,
    context: dict = None,
    attachments: list = None,
):
    context = context or {}
    attachments = attachments or []

    html_content = render_to_string(template_html, context)
    text_content = (
        render_to_string(template_txt, context) if template_txt else html_content
    )

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=recipients,
    )

    msg.attach_alternative(html_content, "text/html")

    for attachment in attachments:
        msg.attach(*attachment)

    msg.send()
