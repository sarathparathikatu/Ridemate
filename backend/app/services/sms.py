"""Sending text messages. Swap the provider here; nothing else in the app changes.

To go live, add a branch for a real provider (Twilio, MSG91, AWS SNS...) that makes its
HTTP call with credentials read from settings, and set SMS_PROVIDER to its name.
"""

import logging

from app.core.config import get_settings

log = logging.getLogger("ridemate.sms")


async def send_sms(phone: str, message: str) -> None:
    provider = get_settings().sms_provider
    if provider == "console":
        # Development only: the "SMS" lands in the server log.
        log.warning("SMS to %s: %s", phone, message)
        return
    raise RuntimeError(f"SMS provider {provider!r} is not configured")
