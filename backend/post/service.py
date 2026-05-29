from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from django.conf import settings
from django.core.mail import EmailMultiAlternatives


@dataclass(frozen=True)
class EmailDelivery:
    subject: str
    recipients: tuple[str, ...]
    sent_count: int


def _normalize_recipients(value: str | Iterable[str], field_name: str) -> tuple[str, ...]:
    if isinstance(value, str):
        recipients = (value.strip(),)
    else:
        recipients = tuple(str(item).strip() for item in value)

    recipients = tuple(item for item in recipients if item)
    if not recipients:
        raise ValueError(f"{field_name} must contain at least one email address")
    return recipients


def send_email(
    *,
    subject: str,
    to: str | Iterable[str],
    text: str = "",
    html: str = "",
    from_email: str | None = None,
    reply_to: Iterable[str] | None = None,
    headers: Mapping[str, str] | None = None,
    fail_silently: bool = False,
) -> EmailDelivery:
    subject = subject.strip()
    if not subject:
        raise ValueError("subject is required")

    text = text or ""
    html = html or ""
    if not text and not html:
        raise ValueError("text or html body is required")

    recipients = _normalize_recipients(to, "to")
    reply_to_recipients = (
        _normalize_recipients(reply_to, "reply_to") if reply_to is not None else None
    )
    message = EmailMultiAlternatives(
        subject=subject,
        body=text,
        from_email=from_email or settings.DEFAULT_FROM_EMAIL,
        to=list(recipients),
        reply_to=list(reply_to_recipients) if reply_to_recipients else None,
        headers=dict(headers or {}),
    )
    if html:
        message.attach_alternative(html, "text/html")

    sent_count = message.send(fail_silently=fail_silently)
    return EmailDelivery(subject=subject, recipients=recipients, sent_count=sent_count)
