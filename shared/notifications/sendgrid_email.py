from __future__ import annotations

import base64
import mimetypes
import os
from pathlib import Path
from typing import Iterable

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (
    Attachment,
    Disposition,
    FileContent,
    FileName,
    FileType,
    Mail,
    ReplyTo,
)


def send_email(
    *,
    subject: str,
    body: str,
    recipient: str | None = None,
    attachments: Iterable[str | Path] | None = None,
    html: bool = False,
) -> int:
    api_key = os.getenv("SENDGRID_API_KEY")
    sender_email = os.getenv("SENDGRID_FROM_EMAIL")
    sender_name = os.getenv("SENDGRID_FROM_NAME", "AI CIO Dividend Bot")
    reply_to = os.getenv("SENDGRID_REPLY_TO")
    recipient_email = recipient or os.getenv("REPORT_RECIPIENT")

    if not api_key:
        raise RuntimeError("SENDGRID_API_KEY is not configured")

    if not sender_email:
        raise RuntimeError("SENDGRID_FROM_EMAIL is not configured")

    if not recipient_email:
        raise RuntimeError("REPORT_RECIPIENT is not configured")

    message = Mail(
        from_email=(sender_email, sender_name),
        to_emails=recipient_email,
        subject=subject,
        html_content=body if html else None,
        plain_text_content=None if html else body,
    )

    if reply_to:
        message.reply_to = ReplyTo(reply_to)

    for attachment_path in attachments or []:
        path = Path(attachment_path)

        if not path.is_file():
            raise FileNotFoundError(f"Attachment not found: {path}")

        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        mime_type, _ = mimetypes.guess_type(path.name)

        message.add_attachment(
            Attachment(
                FileContent(encoded),
                FileName(path.name),
                FileType(mime_type or "application/octet-stream"),
                Disposition("attachment"),
            )
        )

    response = SendGridAPIClient(api_key).send(message)

    if response.status_code != 202:
        raise RuntimeError(
            f"SendGrid rejected the message with status "
            f"{response.status_code}: {response.body!r}"
        )

    return response.status_code