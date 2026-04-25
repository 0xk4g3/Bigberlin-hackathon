"""
One-time setup: point the Twilio phone number at our /incoming-call endpoint.

Run from the backend directory:
    python scripts/configure_twilio_webhook.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from twilio.rest import Client
from config import get_settings

def main():
    s = get_settings()
    client = Client(s.twilio_api_key_sid, s.twilio_api_key_secret, account_sid=s.twilio_account_sid)

    app_host = s.app_host.rstrip("/")
    voice_url = f"{app_host}/incoming-call"

    numbers = client.incoming_phone_numbers.list(phone_number=s.twilio_phone_number)
    if not numbers:
        print(f"ERROR: {s.twilio_phone_number} not found on account {s.twilio_account_sid}")
        sys.exit(1)

    pn = numbers[0]
    updated = pn.update(voice_url=voice_url, voice_method="POST")
    print(f"Webhook set: {updated.sid} ({updated.phone_number}) → {updated.voice_url}")

if __name__ == "__main__":
    main()
