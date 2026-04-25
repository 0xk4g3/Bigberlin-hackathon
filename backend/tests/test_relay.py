"""Tests for websocket/relay.py — Twilio ↔ ElevenLabs bridge."""

import asyncio
import base64
import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch

import numpy as np

from websocket.relay import CallRelay, RelayState


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

SILENCE_MULAW_B64 = base64.b64encode(bytes([0x7F] * 160)).decode()
SILENCE_PCM16_B64 = base64.b64encode(np.zeros(160, dtype=np.int16).tobytes()).decode()


def make_supabase_mock():
    sb = AsyncMock()
    sb.create_call = AsyncMock(return_value="mock-call-uuid")
    sb.update_call_stream_sid = AsyncMock()
    sb.update_call_el_conversation_id = AsyncMock()
    sb.save_transcript_chunk = AsyncMock()
    sb.complete_call = AsyncMock()
    return sb


def make_twilio_mock():
    tw = AsyncMock()
    tw.send_sms = AsyncMock()
    return tw


class MockELClient:
    """EL client that yields configurable events then stops."""

    def __init__(self, events=None):
        self.sent_audio: list[bytes] = []
        self.pongs_sent: list[int] = []
        self._events = events or []

    async def connect(self):
        return self

    async def send_audio(self, pcm16: bytes):
        self.sent_audio.append(pcm16)

    async def send_pong(self, event_id: int):
        self.pongs_sent.append(event_id)

    async def receive(self):
        for evt in self._events:
            await asyncio.sleep(0)
            yield evt

    async def close(self):
        pass

    @property
    def connected(self):
        return True


def make_twilio_ws(messages: list[str]):
    class WS:
        sent: list[str] = []

        async def iter_text(self):
            for m in messages:
                await asyncio.sleep(0)
                yield m

        async def send_text(self, data: str):
            self.sent.append(data)

    return WS()


def make_relay(supabase=None, twilio=None):
    return CallRelay(
        call_sid="CA_TEST",
        agent_id="ag_test",
        api_key="key_test",
        supabase=supabase or make_supabase_mock(),
        twilio_sms=twilio or make_twilio_mock(),
        aic_processor=None,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestRelayState:
    def test_initial_state(self):
        relay = make_relay()
        assert relay.state.call_sid == "CA_TEST"
        assert relay.state.stream_sid == ""
        assert relay.state.transcript == []
        assert not relay.state.stop_event.is_set()


class TestTwilioEventHandling:
    @pytest.mark.asyncio
    async def test_start_event_creates_call(self):
        sb = make_supabase_mock()
        relay = make_relay(supabase=sb)
        messages = [
            json.dumps({"event": "connected"}),
            json.dumps({"event": "start", "start": {
                "streamSid": "MZ_STREAM",
                "callSid": "CA_REAL",
                "customParameters": {"from": "+4917600000", "to": "+49800000"},
            }}),
            json.dumps({"event": "stop"}),
        ]
        el = MockELClient()
        with patch("websocket.relay.ElevenLabsClient", return_value=el):
            await relay.run(make_twilio_ws(messages))
        sb.create_call.assert_called_once()
        call_args = sb.create_call.call_args
        assert call_args[1].get("call_sid") == "CA_REAL" or call_args[0][0] == "CA_REAL"

    @pytest.mark.asyncio
    async def test_media_event_sends_audio_to_el(self):
        relay = make_relay()
        messages = [
            json.dumps({"event": "start", "start": {
                "streamSid": "MZ1", "callSid": "CA_MEDIA",
                "customParameters": {},
            }}),
            json.dumps({"event": "media", "media": {"payload": SILENCE_MULAW_B64}}),
            json.dumps({"event": "stop"}),
        ]
        el = MockELClient()
        with patch("websocket.relay.ElevenLabsClient", return_value=el):
            await relay.run(make_twilio_ws(messages))
        assert len(el.sent_audio) > 0
        # PCM16 chunk should be 320 bytes (160 mulaw samples × 2)
        assert len(el.sent_audio[0]) == 320

    @pytest.mark.asyncio
    async def test_stop_event_triggers_call_complete(self):
        sb = make_supabase_mock()
        relay = make_relay(supabase=sb)
        messages = [
            json.dumps({"event": "start", "start": {
                "streamSid": "MZ1", "callSid": "CA_STOP",
                "customParameters": {},
            }}),
            json.dumps({"event": "stop"}),
        ]
        el = MockELClient()
        with patch("websocket.relay.ElevenLabsClient", return_value=el):
            await relay.run(make_twilio_ws(messages))
        sb.complete_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_malformed_json_is_skipped(self):
        relay = make_relay()
        messages = [
            "not json at all {{{",
            json.dumps({"event": "stop"}),
        ]
        el = MockELClient()
        with patch("websocket.relay.ElevenLabsClient", return_value=el):
            await relay.run(make_twilio_ws(messages))  # should not raise


class TestElevenLabsEventHandling:
    @pytest.mark.asyncio
    async def test_ping_triggers_pong(self):
        relay = make_relay()
        messages = [json.dumps({"event": "stop"})]
        el = MockELClient(events=[
            {"type": "ping", "ping_event": {"event_id": 99}},
        ])
        with patch("websocket.relay.ElevenLabsClient", return_value=el):
            await relay.run(make_twilio_ws(messages))
        assert 99 in el.pongs_sent

    @pytest.mark.asyncio
    async def test_agent_response_captured_in_transcript(self):
        relay = make_relay()
        messages = [
            json.dumps({"event": "start", "start": {
                "streamSid": "MZ1", "callSid": "CA_TR",
                "customParameters": {},
            }}),
            json.dumps({"event": "stop"}),
        ]
        el = MockELClient(events=[
            {"type": "agent_response", "agent_response_event": {"agent_response": "Hello, I am Sophie"}},
        ])
        with patch("websocket.relay.ElevenLabsClient", return_value=el):
            await relay.run(make_twilio_ws(messages))
        assert any(t["speaker"] == "agent" for t in relay.state.transcript)
        assert any("Sophie" in t["text"] for t in relay.state.transcript)

    @pytest.mark.asyncio
    async def test_user_transcript_captured(self):
        relay = make_relay()
        messages = [
            json.dumps({"event": "start", "start": {
                "streamSid": "MZ1", "callSid": "CA_UTR",
                "customParameters": {},
            }}),
            json.dumps({"event": "stop"}),
        ]
        el = MockELClient(events=[
            {"type": "user_transcript", "user_transcription_event": {"user_transcript": "I had an accident"}},
        ])
        with patch("websocket.relay.ElevenLabsClient", return_value=el):
            await relay.run(make_twilio_ws(messages))
        assert any(t["speaker"] == "caller" for t in relay.state.transcript)
        assert any("accident" in t["text"] for t in relay.state.transcript)

    @pytest.mark.asyncio
    async def test_audio_event_sent_to_twilio(self):
        relay = make_relay()
        messages = [
            json.dumps({"event": "start", "start": {
                "streamSid": "MZ_AUDIO", "callSid": "CA_AUD",
                "customParameters": {},
            }}),
            json.dumps({"event": "stop"}),
        ]
        ws = make_twilio_ws(messages)
        el = MockELClient(events=[
            {"type": "audio", "audio_event": {"audio_base_64": SILENCE_PCM16_B64}},
        ])
        with patch("websocket.relay.ElevenLabsClient", return_value=el):
            await relay.run(ws)
        audio_msgs = [json.loads(m) for m in ws.sent if "media" in m]
        assert len(audio_msgs) > 0
        assert audio_msgs[0]["event"] == "media"
        assert audio_msgs[0]["streamSid"] == "MZ_AUDIO"

    @pytest.mark.asyncio
    async def test_conversation_id_stored(self):
        sb = make_supabase_mock()
        relay = make_relay(supabase=sb)
        messages = [
            json.dumps({"event": "start", "start": {
                "streamSid": "MZ1", "callSid": "CA_CONV",
                "customParameters": {},
            }}),
            json.dumps({"event": "stop"}),
        ]
        el = MockELClient(events=[
            {"type": "conversation_initiation_metadata",
             "conversation_initiation_metadata_event": {"conversation_id": "EL-CONV-XYZ"}},
        ])
        with patch("websocket.relay.ElevenLabsClient", return_value=el):
            await relay.run(make_twilio_ws(messages))
        assert relay.state.el_conversation_id == "EL-CONV-XYZ"


class TestCallComplete:
    @pytest.mark.asyncio
    async def test_complete_call_called_with_transcript(self):
        sb = make_supabase_mock()
        relay = make_relay(supabase=sb)
        messages = [
            json.dumps({"event": "start", "start": {
                "streamSid": "MZ1", "callSid": "CA_CPL",
                "customParameters": {"from": "+4917600001"},
            }}),
            json.dumps({"event": "stop"}),
        ]
        el = MockELClient(events=[
            {"type": "agent_response", "agent_response_event": {"agent_response": "Hello"}},
            {"type": "user_transcript", "user_transcription_event": {"user_transcript": "Hi there"}},
        ])
        with patch("websocket.relay.ElevenLabsClient", return_value=el):
            await relay.run(make_twilio_ws(messages))
        sb.complete_call.assert_called_once()
        _, kwargs = sb.complete_call.call_args
        assert kwargs.get("duration_seconds", 0) >= 0
        assert isinstance(kwargs.get("transcript", []), list)

    @pytest.mark.asyncio
    async def test_sms_sent_to_caller(self):
        sb = make_supabase_mock()
        tw = make_twilio_mock()
        relay = make_relay(supabase=sb, twilio=tw)
        messages = [
            json.dumps({"event": "start", "start": {
                "streamSid": "MZ1", "callSid": "CA_SMS",
                "customParameters": {"from": "+4917699999"},
            }}),
            json.dumps({"event": "stop"}),
        ]
        el = MockELClient()
        with patch("websocket.relay.ElevenLabsClient", return_value=el):
            await relay.run(make_twilio_ws(messages))
        tw.send_sms.assert_called_once()
        call_kwargs = tw.send_sms.call_args[1]
        assert call_kwargs["to"] == "+4917699999"
        assert "claim" in call_kwargs["body"].lower()
