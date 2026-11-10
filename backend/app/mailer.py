"""Gửi email qua SMTP (tuỳ chọn). Không cấu hình SMTP → trả False, caller tự xử lý."""
import asyncio
import logging
import smtplib
from email.message import EmailMessage

from .config import settings

log = logging.getLogger("mailer")


def _send_sync(to: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = settings.smtp_from, to, subject
    msg.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as s:
        if settings.smtp_starttls:
            s.starttls()
        if settings.smtp_user:
            s.login(settings.smtp_user, settings.smtp_password)
        s.send_message(msg)


async def send(to: str, subject: str, body: str) -> bool:
    if not settings.smtp_enabled:
        return False
    try:
        await asyncio.to_thread(_send_sync, to, subject, body)
        return True
    except Exception as e:  # lỗi mail không được làm lộ việc tài khoản có tồn tại hay không
        log.warning("SMTP gửi thất bại: %s", e)
        return False
