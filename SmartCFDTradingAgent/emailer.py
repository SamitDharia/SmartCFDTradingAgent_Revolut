from __future__ import annotations

import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Iterable, Sequence


def _to_bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def default_recipients() -> list[str]:
    raw = os.getenv("DIGEST_EMAILS", "").strip()
    if not raw:
        return []
    return [addr.strip() for addr in raw.split(",") if addr.strip()]


def _build_message(
    subject: str,
    sender: str,
    recipients: Sequence[str],
    body_text: str,
    html_body: str | None = None,
    attachments: Iterable[Path | str] | None = None,
) -> MIMEMultipart | MIMEText:
    if html_body or attachments:
        outer = MIMEMultipart()
        alt_part = MIMEMultipart('alternative')
        alt_part.attach(MIMEText(body_text, 'plain', 'utf-8'))
        if html_body:
            alt_part.attach(MIMEText(html_body, 'html', 'utf-8'))
        outer.attach(alt_part)
    else:
        outer = MIMEText(body_text, 'plain', 'utf-8')

    if attachments:
        if not isinstance(outer, MIMEMultipart):
            container = MIMEMultipart()
            container.attach(outer)
            outer = container
        for item in attachments:
            path = Path(item)
            if not path.exists():
                continue
            with path.open('rb') as fh:
                part = MIMEApplication(fh.read(), Name=path.name)
            part['Content-Disposition'] = f'attachment; filename="{path.name}"'
            outer.attach(part)

    outer['Subject'] = subject
    outer['From'] = sender
    outer['To'] = ', '.join(recipients)
    return outer


def send_email(
    subject: str,
    body_text: str,
    recipients: Iterable[str] | None = None,
    *,
    html_body: str | None = None,
    attachments: Iterable[Path | str] | None = None,
) -> bool:
    emails: Sequence[str] = list(recipients) if recipients is not None else default_recipients()
    emails = [addr for addr in emails if addr]
    if not emails:
        return False

    host = os.getenv("SMTP_HOST", "").strip()
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    sender = os.getenv("SMTP_SENDER", username).strip()
    if not (host and username and password and sender):
        raise RuntimeError("SMTP credentials missing (check SMTP_HOST/SMTP_USER/SMTP_PASSWORD)")

    use_ssl = _to_bool(os.getenv("SMTP_USE_SSL"))
    message = _build_message(subject, sender, emails, body_text, html_body, attachments)

    try:
        if use_ssl:
            with smtplib.SMTP_SSL(host, port) as smtp:
                smtp.login(username, password)
                smtp.sendmail(sender, emails, message.as_string())
        else:
            with smtplib.SMTP(host, port) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.login(username, password)
                smtp.sendmail(sender, emails, message.as_string())
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"Failed to send email digest: {exc}")
    return True


__all__ = ["send_email", "default_recipients"]
