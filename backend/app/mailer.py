"""Email delivery. Real SMTP when configured (SMTP_HOST etc.), otherwise
'dev' delivery: the code/message is logged, and verification endpoints
return the code in the API response so the demo works without a mail
server. Production must set SMTP_HOST — dev codes are demo-only."""
from __future__ import annotations

import smtplib
from email.message import EmailMessage


def delivery_mode(settings) -> str:
    return "smtp" if settings.smtp_host else "dev"


def send_email(settings, to: str, subject: str, body: str) -> bool:
    if not settings.smtp_host:
        print(f"[dev-mail] to={to} subject={subject!r} body={body!r}")
        return False
    msg = EmailMessage()
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        if settings.smtp_tls:
            smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(msg)
    return True
