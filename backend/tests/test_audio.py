"""Tests for services/audio.py — mulaw codec and bandpass filter."""

import base64
import numpy as np
import pytest

from services.audio import (
    apply_telephone_bandpass,
    elevenlabs_audio_to_twilio_payload,
    mulaw_base64_to_pcm16_base64,
    mulaw_to_pcm16,
    pcm16_to_mulaw,
    pcm16_to_base64,
    base64_to_mulaw,
    _get_bandpass_sos,
)


SILENCE_MULAW = bytes([0x7F] * 160)   # G.711 silence
SILENCE_PCM16 = b"\x00" * 320         # 160 int16 zeros


class TestMulawCodec:
    def test_mulaw_to_pcm16_length(self):
        pcm = mulaw_to_pcm16(SILENCE_MULAW)
        assert len(pcm) == 320  # 160 samples × 2 bytes

    def test_pcm16_to_mulaw_length(self):
        mulaw = pcm16_to_mulaw(SILENCE_PCM16)
        assert len(mulaw) == 160

    def test_round_trip_preserves_shape(self):
        pcm = mulaw_to_pcm16(SILENCE_MULAW)
        back = pcm16_to_mulaw(pcm)
        assert len(back) == len(SILENCE_MULAW)

    def test_round_trip_silence_stays_near_zero(self):
        # mulaw 0x7F → PCM ~0 → mulaw ~0x7F — minor quantization OK
        pcm = mulaw_to_pcm16(SILENCE_MULAW)
        samples = np.frombuffer(pcm, dtype=np.int16)
        assert np.abs(samples).max() < 100  # all near zero

    def test_round_trip_tone_stable(self):
        # 1kHz sine at 8kHz sample rate
        t = np.linspace(0, 1, 160, endpoint=False)
        sine_int16 = (np.sin(2 * np.pi * 1000 * t) * 10000).astype(np.int16)
        mulaw = pcm16_to_mulaw(sine_int16.tobytes())
        pcm_rt = mulaw_to_pcm16(mulaw)
        samples_rt = np.frombuffer(pcm_rt, dtype=np.int16)
        # Round-trip correlation with original — expect > 0.99
        corr = np.corrcoef(sine_int16, samples_rt)[0, 1]
        assert corr > 0.99, f"Round-trip correlation too low: {corr:.4f}"

    def test_empty_input(self):
        assert mulaw_to_pcm16(b"") == b""
        assert pcm16_to_mulaw(b"") == b""


class TestBase64Helpers:
    def test_base64_to_mulaw(self):
        b64 = base64.b64encode(SILENCE_MULAW).decode()
        assert base64_to_mulaw(b64) == SILENCE_MULAW

    def test_pcm16_to_base64(self):
        b64 = pcm16_to_base64(SILENCE_PCM16)
        assert base64.b64decode(b64) == SILENCE_PCM16

    def test_mulaw_base64_to_pcm16_base64_roundtrip(self):
        b64_mulaw = base64.b64encode(SILENCE_MULAW).decode()
        b64_pcm = mulaw_base64_to_pcm16_base64(b64_mulaw)
        decoded = base64.b64decode(b64_pcm)
        assert len(decoded) == 320


class TestBandpassFilter:
    def test_preserves_length(self):
        pcm = np.random.randint(-5000, 5000, 160, dtype=np.int16).tobytes()
        filtered = apply_telephone_bandpass(pcm, sample_rate=8000)
        assert len(filtered) == len(pcm)

    def test_preserves_dtype(self):
        pcm = np.zeros(160, dtype=np.int16).tobytes()
        filtered = apply_telephone_bandpass(pcm)
        samples = np.frombuffer(filtered, dtype=np.int16)
        assert samples.dtype == np.int16

    def test_silence_stays_silent(self):
        filtered = apply_telephone_bandpass(SILENCE_PCM16)
        samples = np.frombuffer(filtered, dtype=np.int16)
        assert np.abs(samples).max() < 10

    def test_attenuates_out_of_band_low(self):
        # 50Hz tone (below 300Hz cutoff) should be attenuated
        t = np.linspace(0, 1, 8000, endpoint=False)
        low = (np.sin(2 * np.pi * 50 * t) * 10000).astype(np.int16)
        filtered = apply_telephone_bandpass(low.tobytes(), sample_rate=8000)
        filtered_samples = np.frombuffer(filtered, dtype=np.int16).astype(np.float32)
        attenuation = np.abs(filtered_samples).mean() / (np.abs(low).mean() + 1e-9)
        assert attenuation < 0.1, f"Low-freq not attenuated enough: {attenuation:.3f}"

    def test_attenuates_out_of_band_high(self):
        # 4000Hz tone (above 3400Hz cutoff) should be attenuated
        t = np.linspace(0, 1, 8000, endpoint=False)
        high = (np.sin(2 * np.pi * 4000 * t) * 10000).astype(np.int16)
        filtered = apply_telephone_bandpass(high.tobytes(), sample_rate=8000)
        filtered_samples = np.frombuffer(filtered, dtype=np.int16).astype(np.float32)
        attenuation = np.abs(filtered_samples).mean() / (np.abs(high).mean() + 1e-9)
        assert attenuation < 0.2, f"High-freq not attenuated enough: {attenuation:.3f}"

    def test_passes_in_band(self):
        # 1kHz tone (in 300-3400Hz band) should pass mostly unchanged
        t = np.linspace(0, 1, 8000, endpoint=False)
        tone = (np.sin(2 * np.pi * 1000 * t) * 10000).astype(np.int16)
        filtered = apply_telephone_bandpass(tone.tobytes(), sample_rate=8000)
        filtered_samples = np.frombuffer(filtered, dtype=np.int16).astype(np.float32)
        ratio = np.abs(filtered_samples).mean() / (np.abs(tone).mean() + 1e-9)
        assert ratio > 0.8, f"In-band signal too attenuated: {ratio:.3f}"

    def test_coefficients_cached(self):
        # Same params → same object (lru_cache)
        sos1 = _get_bandpass_sos(4, 300, 3400, 8000)
        sos2 = _get_bandpass_sos(4, 300, 3400, 8000)
        assert sos1 is sos2


class TestElevenLabsToTwilioPipeline:
    def test_full_pipeline_length(self):
        # EL sends PCM16 → we return mulaw (1:2 compression)
        pcm16 = np.zeros(160, dtype=np.int16).tobytes()
        b64_pcm = base64.b64encode(pcm16).decode()
        result_b64 = elevenlabs_audio_to_twilio_payload(b64_pcm)
        decoded = base64.b64decode(result_b64)
        assert len(decoded) == 160  # mulaw = half PCM16 bytes

    def test_pipeline_no_filter(self):
        pcm16 = np.zeros(160, dtype=np.int16).tobytes()
        b64 = base64.b64encode(pcm16).decode()
        result = elevenlabs_audio_to_twilio_payload(b64, apply_filter=False)
        assert base64.b64decode(result) == pcm16_to_mulaw(pcm16)
