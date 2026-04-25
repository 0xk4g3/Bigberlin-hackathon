"""
Audio processing pipeline for ClaimCall.

Twilio → ElevenLabs path:
  base64(mulaw 8kHz) → mulaw bytes → PCM16 8kHz → [upsample 16kHz] →
  AI-Coustics enhance → [downsample 8kHz] → PCM16 → base64

ElevenLabs → Twilio path:
  base64(PCM16 from EL) → PCM16 → bandpass 300-3400Hz → mulaw 8kHz → base64

G.711 u-law implemented with numpy (audioop removed in Python 3.13).
Butterworth filter coefficients cached at module init (static — never recompute per frame).
"""

import asyncio
import base64
import logging
from functools import lru_cache
from typing import Optional

import numpy as np
from scipy.signal import butter, sosfilt, resample_poly

logger = logging.getLogger(__name__)

TWILIO_SAMPLE_RATE = 8000
EL_SAMPLE_RATE = 16000      # AI-Coustics model quail-vf-2.1-l-16khz expects 16kHz
MULAW_BIAS = 33
MULAW_CLIP = 32635


# ─────────────────────────────────────────────────────────────────────────────
# G.711 μ-law codec (numpy — no audioop dependency)
# ─────────────────────────────────────────────────────────────────────────────

def _mulaw_encode(linear: np.ndarray) -> np.ndarray:
    """ITU-T G.711 μ-law encoding. Input: int16 array. Output: uint8 array."""
    linear = linear.astype(np.int16)
    sign = np.where(linear < 0, 0x80, 0x00).astype(np.uint8)
    linear = np.clip(np.abs(linear.astype(np.int32)), 0, MULAW_CLIP)
    linear = linear + MULAW_BIAS
    exp = (np.floor(np.log2(linear + 1))).astype(np.int32)
    exp = np.clip(exp - 5, 0, 7).astype(np.int32)
    mantissa = ((linear >> (exp + 3)) & 0x0F).astype(np.uint8)
    mulaw = (~(sign | (exp.astype(np.uint8) << 4) | mantissa)).astype(np.uint8)
    return mulaw


def _mulaw_decode(mulaw: np.ndarray) -> np.ndarray:
    """ITU-T G.711 μ-law decoding. Input: uint8 array. Output: int16 array."""
    mulaw = (~mulaw.astype(np.uint8)).astype(np.int32)
    sign = mulaw & 0x80
    exp = (mulaw >> 4) & 0x07
    mantissa = mulaw & 0x0F
    linear = ((mantissa << 3) + MULAW_BIAS) << exp
    linear = linear - MULAW_BIAS
    linear = np.where(sign != 0, -linear, linear)
    return linear.astype(np.int16)


def mulaw_to_pcm16(mulaw_bytes: bytes) -> bytes:
    """G.711 μ-law bytes → linear PCM16 bytes."""
    arr = np.frombuffer(mulaw_bytes, dtype=np.uint8)
    return _mulaw_decode(arr).tobytes()


def pcm16_to_mulaw(pcm16_bytes: bytes) -> bytes:
    """Linear PCM16 bytes → G.711 μ-law bytes."""
    arr = np.frombuffer(pcm16_bytes, dtype=np.int16)
    return _mulaw_encode(arr).tobytes()


# ─────────────────────────────────────────────────────────────────────────────
# Base64 helpers
# ─────────────────────────────────────────────────────────────────────────────

def base64_to_mulaw(b64_string: str) -> bytes:
    return base64.b64decode(b64_string)


def mulaw_to_base64(mulaw_bytes: bytes) -> str:
    return base64.b64encode(mulaw_bytes).decode()


def pcm16_to_base64(pcm16_bytes: bytes) -> str:
    return base64.b64encode(pcm16_bytes).decode()


def mulaw_base64_to_pcm16_base64(mulaw_b64: str) -> str:
    """Twilio→ElevenLabs: base64(mulaw) → base64(PCM16)."""
    mulaw = base64.b64decode(mulaw_b64)
    pcm16 = mulaw_to_pcm16(mulaw)
    return base64.b64encode(pcm16).decode()


# ─────────────────────────────────────────────────────────────────────────────
# Resampling helpers
# ─────────────────────────────────────────────────────────────────────────────

def _resample_pcm16(pcm16_bytes: bytes, from_rate: int, to_rate: int) -> bytes:
    """Resample PCM16 audio between sample rates using polyphase filtering."""
    if from_rate == to_rate:
        return pcm16_bytes
    arr = np.frombuffer(pcm16_bytes, dtype=np.int16).astype(np.float32)
    from math import gcd
    g = gcd(to_rate, from_rate)
    up, down = to_rate // g, from_rate // g
    resampled = resample_poly(arr, up, down)
    return np.clip(resampled, -32768, 32767).astype(np.int16).tobytes()


# ─────────────────────────────────────────────────────────────────────────────
# AI-Coustics enhancement
# ─────────────────────────────────────────────────────────────────────────────

async def enhance_with_aicoustics(
    pcm16_bytes: bytes,
    processor,                  # aic_sdk.Processor instance from app.state
    sample_rate: int = TWILIO_SAMPLE_RATE,
) -> bytes:
    """
    Enhance PCM16 audio with AI-Coustics noise reduction.

    Pipeline:
    1. Upsample 8kHz → 16kHz (model expects 16kHz)
    2. PCM16 int16 → float32 numpy (channels × frames)
    3. AI-Coustics enhance (in thread executor with 200ms timeout)
    4. float32 → PCM16 int16
    5. Downsample 16kHz → 8kHz

    Falls back to raw audio on any error — never raises.
    """
    if processor is None:
        return pcm16_bytes
    try:
        up_bytes = _resample_pcm16(pcm16_bytes, sample_rate, EL_SAMPLE_RATE)
        arr_16k = np.frombuffer(up_bytes, dtype=np.int16).astype(np.float32)
        arr_16k /= 32768.0
        audio_2d = arr_16k.reshape(1, -1)

        def _enhance() -> np.ndarray:
            return processor.process(audio_2d)

        loop = asyncio.get_event_loop()
        enhanced_2d = await asyncio.wait_for(
            loop.run_in_executor(None, _enhance),
            timeout=0.2,
        )
        enhanced_1d = enhanced_2d.flatten()
        enhanced_int16 = np.clip(enhanced_1d * 32768.0, -32768, 32767).astype(np.int16)
        return _resample_pcm16(enhanced_int16.tobytes(), EL_SAMPLE_RATE, sample_rate)
    except Exception as exc:
        logger.warning("AI-Coustics enhancement failed, using raw audio: %s", exc)
        return pcm16_bytes


# ─────────────────────────────────────────────────────────────────────────────
# Telephone bandpass filter (cached coefficients)
# ─────────────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=8)
def _get_bandpass_sos(order: int, low_hz: int, high_hz: int, sample_rate: int) -> np.ndarray:
    """Cache Butterworth SOS coefficients — static for a given config."""
    nyq = sample_rate / 2.0
    return butter(order, [low_hz / nyq, high_hz / nyq], btype="band", output="sos")


def apply_telephone_bandpass(
    pcm16_bytes: bytes,
    sample_rate: int = TWILIO_SAMPLE_RATE,
    order: int = 4,
    low_hz: int = 300,
    high_hz: int = 3400,
) -> bytes:
    """
    Apply 300Hz–3400Hz Butterworth bandpass to ElevenLabs output audio.

    Makes Sophie sound like she's on a real phone call (G.711 telephone bandwidth)
    rather than a studio recording — removes the uncanny "too perfect" quality.
    """
    arr = np.frombuffer(pcm16_bytes, dtype=np.int16).astype(np.float32)
    arr /= 32768.0
    sos = _get_bandpass_sos(order, low_hz, high_hz, sample_rate)
    filtered = sosfilt(sos, arr)
    return np.clip(filtered * 32768.0, -32768, 32767).astype(np.int16).tobytes()


def elevenlabs_audio_to_twilio_payload(
    el_audio_b64: str,
    sample_rate: int = TWILIO_SAMPLE_RATE,
    apply_filter: bool = True,
    filter_order: int = 4,
) -> str:
    """
    ElevenLabs→Twilio full pipeline:
    base64(PCM16) → PCM16 → [bandpass] → mulaw → base64
    """
    pcm16 = base64.b64decode(el_audio_b64)
    if apply_filter:
        pcm16 = apply_telephone_bandpass(pcm16, sample_rate=sample_rate, order=filter_order)
    mulaw = pcm16_to_mulaw(pcm16)
    return base64.b64encode(mulaw).decode()
