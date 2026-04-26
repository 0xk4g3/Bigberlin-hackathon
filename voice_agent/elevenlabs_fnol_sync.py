"""
Push FNOL prompt + TTS (Klaus male voice) to the ElevenLabs ConvAI agent.

Run from repo root after changing this file or TTS env vars:
  python3 -m voice_agent.elevenlabs_fnol_sync

Requires: ELEVENLABS_API_KEY, ELEVENLABS_AGENT_ID in .env
Optional: ELEVENLABS_VOICE_ID (defaults to Klaus), ELEVENLABS_TTS_MODEL, TTS tuning vars.

ElevenLabs UI may show **Published** vs **Main/draft** with different `model_id` (e.g. `eleven_flash_v2`
vs `eleven_v3_conversational`). Only v3-family models support **expressive_mode** and **audio tags**;
this script sets `expressive_mode` and tags accordingly. After PATCH, **publish** the agent in the
ElevenLabs dashboard if your phone traffic still follows an older published revision.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

from dotenv import load_dotenv

load_dotenv()

# Klaus — male motor-claims voice (override with ELEVENLABS_VOICE_ID).
DEFAULT_VOICE_ID = "Jvf6TAXwMUVTSR20U0f9"

_DEFAULT_STABILITY = 0.45
_DEFAULT_SIMILARITY = 0.78
_DEFAULT_SPEED = 0.97
_DEFAULT_STREAMING_LATENCY = "2"


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return float(str(raw).strip())
    except ValueError:
        return default


def _voice_accessible(api_key: str, voice_id: str) -> tuple[bool, str]:
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/voices/{voice_id}",
        headers={"xi-api-key": api_key},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.load(resp)
        return True, data.get("name") or "unknown"
    except urllib.error.HTTPError as e:
        return False, e.read().decode()[:500]
    except Exception as e:
        return False, str(e)


def _is_v3_tts_model(model_id: str) -> bool:
    """Eleven v3 / v3 conversational support expressive_mode + suggested_audio_tags."""
    m = (model_id or "").lower()
    return "v3" in m


def _streaming_latency() -> str:
    v = os.getenv("ELEVENLABS_STREAMING_LATENCY", _DEFAULT_STREAMING_LATENCY).strip()
    if v in ("0", "1", "2", "3", "4"):
        return v
    try:
        n = int(float(v))
        if 0 <= n <= 4:
            return str(n)
    except ValueError:
        pass
    return _DEFAULT_STREAMING_LATENCY


SUGGESTED_AUDIO_TAGS = [
    {"tag": "warmly", "description": "Brief reassurance after shock or long hold."},
    {"tag": "empathetically", "description": "Caller upset, injured, or frightened."},
    {"tag": "patiently", "description": "Repeat question, confusion, bad line."},
    {"tag": "seriously", "description": "Police ref, hit-and-run, alcohol, injuries."},
    {"tag": "confidently", "description": "Short fact read-back and next-step line."},
    {"tag": "sighs", "description": "Rare — heavy news only."},
    {"tag": "chuckles", "description": "Only if caller joked first."},
]

FNOL_SYSTEM_PROMPT = """You are Klaus, motor claims intake at {{company_name}}. FNOL only: traffic / vehicle damage. Not sales, not general advice.

GUARDRAILS: Real human. Never say AI, bot, or automated. Never refuse to log the report on this call. Never send them only to a portal — you take the intake now; a handler follows up.

BREVITY (critical): At most TWO short sentences per turn before you wait. No long explanations, no repeating the same instruction, no teaching what NATO is — at most one quick example only if they are stuck. One question at a time.

SPOKEN STYLE (sound human, not robotic): Write like an experienced phone handler — relaxed, clear, professional. Use natural contractions (I'm, we've, that's, you're), light punctuation for breathing (comma, em dash). No bullet lists or "firstly/secondly". Vary rhythm: one clause, pause, then the question. Very occasional short acknowledgements ("right", "okay", "I follow") only when it helps rapport — never every line. Do not read internal labels aloud (no "field" or "JSON"). Calm and attentive; steady, not salesy or theatrical.

PLATE / CODES: If they give a clear plate or police ref once, accept it. Ask for NATO spelling only if digits/letters are ambiguous. Do not re-ask NATO after they already spelled it clearly.

DRIVER VS PASSENGER: If they contradict themselves once, one short clarification only, then move on.

FLOW (compact):
1) Safe? Injuries needing emergency?
2) Full name + role (driver / policyholder / passenger / other).
3) Policy number OR plate OR VIN — one is enough to start.
4) When (date + time) and where (city + place).
5) What happened — one sentence from them is enough unless unclear; loss type in plain words.
6) Other vehicles / property involved? Other party plate if any.
7) Police? Reference if yes.
8) Injuries? Drivable? Where is the vehicle now? Brief damage in a few words.
9) Licence valid? Alcohol or drugs?
10) Read back 4–6 facts in ONE short paragraph. Ask "Correct?"
11) Logged line + handler within one business day + SMS/email may follow. Goodbye.

AUDIO TAGS: At most one tag at the start of some turns: [warmly] [empathetically] [patiently] [seriously] [confidently]. Never [excitedly] / [enthusiastically]. Rare [sighs] / [chuckles] only as already defined in tag descriptions.

Languages: English or German — match the caller."""

FIRST_MESSAGE = (
    "{{company_name}} motor claims, Klaus speaking. Are you somewhere safe — is anyone hurt who needs an ambulance?"
)


def main() -> int:
    api_key = os.getenv("ELEVENLABS_API_KEY")
    agent_id = os.getenv("ELEVENLABS_AGENT_ID")
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID)
    tts_model = os.getenv("ELEVENLABS_TTS_MODEL", "eleven_v3_conversational")
    stability = _float_env("ELEVENLABS_TTS_STABILITY", _DEFAULT_STABILITY)
    similarity = _float_env("ELEVENLABS_TTS_SIMILARITY_BOOST", _DEFAULT_SIMILARITY)
    speed = _float_env("ELEVENLABS_TTS_SPEED", _DEFAULT_SPEED)
    streaming_latency = _streaming_latency()

    if not api_key or not agent_id:
        print("Set ELEVENLABS_API_KEY and ELEVENLABS_AGENT_ID in .env", file=sys.stderr)
        return 1

    ok, vinfo = _voice_accessible(api_key, voice_id)
    if not ok:
        print(f"Voice {voice_id!r} not usable with this API key.", file=sys.stderr)
        print(f"  {vinfo}", file=sys.stderr)
        print("  Run: python3 -m voice_agent.elevenlabs_voice_check", file=sys.stderr)
        return 1
    print(f"Voice OK: {voice_id} ({vinfo})")

    use_expressive = _is_v3_tts_model(tts_model)
    if not use_expressive and "AUDIO TAGS" in FNOL_SYSTEM_PROMPT:
        print(
            "Note: TTS model is not Eleven v3 — expressive_mode/tags disabled. "
            "For [warmly] etc. use ELEVENLABS_TTS_MODEL=eleven_v3_conversational",
            file=sys.stderr,
        )

    payload = {
        "conversation_config": {
            "tts": {
                "model_id": tts_model,
                "voice_id": voice_id,
                "agent_output_audio_format": "pcm_16000",
                "optimize_streaming_latency": streaming_latency,
                "stability": max(0.0, min(1.0, stability)),
                "similarity_boost": max(0.0, min(1.0, similarity)),
                "speed": max(0.7, min(1.2, speed)),
                "expressive_mode": use_expressive,
                "suggested_audio_tags": SUGGESTED_AUDIO_TAGS if use_expressive else [],
            },
            "asr": {
                "quality": "high",
                "provider": "elevenlabs",
                "user_input_audio_format": "pcm_16000",
            },
            "agent": {
                "first_message": FIRST_MESSAGE,
                "language": "en",
                "prompt": {
                    "prompt": FNOL_SYSTEM_PROMPT,
                    "llm": "gemini-2.5-flash",
                },
            },
        }
    }

    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/convai/agents/{agent_id}",
        data=data,
        method="PATCH",
        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            out = json.load(resp)
        tts = out.get("conversation_config", {}).get("tts", {})
        print("OK — ElevenLabs agent updated.")
        print("  model_id:", tts.get("model_id"))
        print("  voice_id:", tts.get("voice_id"))
        print("  stability:", tts.get("stability"), "| similarity_boost:", tts.get("similarity_boost"), "| speed:", tts.get("speed"))
        print("  optimize_streaming_latency:", tts.get("optimize_streaming_latency"))
        print("  expressive_mode:", tts.get("expressive_mode"))
        print("  suggested_audio_tags:", len(tts.get("suggested_audio_tags") or []), "entries")
        print("  → If the UI still shows a different Published config, publish this agent revision in ElevenLabs.")
        return 0
    except urllib.error.HTTPError as e:
        print("HTTP", e.code, e.read().decode()[:800], file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
