from __future__ import annotations

import os
import smtplib
from email.mime.text import MIMEText
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


def send_email(
    subject: str,
    body: str,
    recipients: Iterable[str] | None = None,
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

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(emails)

    use_ssl = _to_bool(os.getenv("SMTP_USE_SSL"))

    try:
        if use_ssl:
            with smtplib.SMTP_SSL(host, port) as smtp:
                smtp.login(username, password)
                smtp.sendmail(sender, emails, msg.as_string())
        else:
            with smtplib.SMTP(host, port) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.login(username, password)
                smtp.sendmail(sender, emails, msg.as_string())
    except Exception as exc:  # pragma: no cover - network errors
        raise RuntimeError(f"Failed to send email digest: {exc}") from exc
    return True


__all__ = ["send_email", "default_recipients"]
