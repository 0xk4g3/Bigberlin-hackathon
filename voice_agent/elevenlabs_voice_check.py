"""List ElevenLabs voice IDs available to your API key.

  python3 -m voice_agent.elevenlabs_voice_check
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

from dotenv import load_dotenv

load_dotenv()


def main() -> int:
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("Set ELEVENLABS_API_KEY in .env", file=sys.stderr)
        return 1

    want = (os.getenv("ELEVENLABS_VOICE_ID") or "").strip()
    req = urllib.request.Request(
        "https://api.elevenlabs.io/v1/voices",
        headers={"xi-api-key": api_key},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            body = json.load(resp)
    except urllib.error.HTTPError as e:
        print("HTTP", e.code, e.read().decode()[:800], file=sys.stderr)
        return 1

    voices = body.get("voices") or []
    print(f"Voices ({len(voices)}):\n")
    found = False
    for v in sorted(voices, key=lambda x: (x.get("name") or "").lower()):
        vid = v.get("voice_id", "")
        name = v.get("name", "?")
        cat = v.get("category") or ""
        tag = "  <-- ELEVENLABS_VOICE_ID" if want and vid == want else ""
        if want and vid == want:
            found = True
        line = f"  {vid}  {name}"
        if cat:
            line += f"  ({cat})"
        print(line + tag)
    print()
    if want and not found:
        print(f"PROBLEM: ELEVENLABS_VOICE_ID={want!r} not in list above.")
        return 1
    if want:
        print("OK — voice id matches your account.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
