import logging

logger = logging.getLogger("rag.email")


async def send_email(to: str, subject: str, body: str) -> None:
    """Stub email sender — wire SMTP/SES in production."""
    logger.info("email_stub to=%s subject=%s body=%s", to, subject, body[:200])
