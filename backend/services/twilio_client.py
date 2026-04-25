"""
Twilio SMS sender — thin async wrapper over the synchronous Twilio SDK.
"""

import asyncio
import logging
from functools import partial

from twilio.rest import Client as TwilioSDKClient
from config import Settings

logger = logging.getLogger(__name__)


class TwilioClient:
    def __init__(self, settings: Settings):
        self._client = TwilioSDKClient(
            settings.twilio_api_key_sid,
            settings.twilio_api_key_secret,
            account_sid=settings.twilio_account_sid,
        )
        self._from_number = settings.twilio_phone_number

    async def send_sms(self, to: str, body: str) -> None:
        """Send SMS via Twilio. Runs sync SDK call in thread executor."""
        if not to:
            logger.warning("send_sms called with empty 'to' number — skipping")
            return
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                partial(
                    self._client.messages.create,
                    to=to,
                    from_=self._from_number,
                    body=body,
                ),
            )
            logger.info("SMS sent to %s", to)
        except Exception as exc:
            logger.error("Failed to send SMS to %s: %s", to, exc)
