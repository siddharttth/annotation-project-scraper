"""Send the digest over SMTP. Gmail: use an App Password, not your login."""
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


def send(subject: str, html_body: str) -> None:
    # `or`, not a getenv default: CI passes unset secrets as empty strings.
    host = os.getenv("SMTP_HOST") or "smtp.gmail.com"
    port = int(os.getenv("SMTP_PORT") or "587")
    user = (os.getenv("SMTP_USER") or "").strip()
    password = (os.getenv("SMTP_PASS") or "").strip()
    # Checked here because an empty login reaches Gmail and comes back as an
    # opaque "Connection unexpectedly closed".
    missing = [k for k, v in (("SMTP_USER", user), ("SMTP_PASS", password)) if not v]
    if missing:
        raise RuntimeError(f"{' and '.join(missing)} not set — add the repository "
                           f"secrets, or fill in .env locally (see SETUP.md)")
    to_addr = os.getenv("MAIL_TO") or user

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_addr
    msg.set_content("This digest is HTML. Open it in an HTML-capable client.")
    msg.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(host, port, timeout=30) as s:
        s.starttls()
        s.login(user, password)
        s.send_message(msg)
    print(f"  mailed -> {to_addr}")
