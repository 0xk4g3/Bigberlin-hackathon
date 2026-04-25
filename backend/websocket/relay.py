"""
Core audio relay: Twilio ↔ AI-Coustics ↔ ElevenLabs

Two concurrent async tasks:
  Task A: Twilio → AI-Coustics → ElevenLabs   (caller voice, cleaned)
  Task B: ElevenLabs → bandpass → Twilio       (Sophie voice, telephonic)

Uses asyncio.wait(FIRST_COMPLETED) for clean shutdown when either side disconnects.
Transcript DB writes dispatched via create_task — never block the EL receive loop.
Ping/pong is handled first in every EL receive loop iteration.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import WebSocket

from config import get_settings
from services.audio import (
    apply_telephone_bandpass,
    elevenlabs_audio_to_twilio_payload,
    enhance_with_aicoustics,
    mulaw_to_pcm16,
)
from services.elevenlabs import ElevenLabsClient
from services.supabase_client import SupabaseService
from services.twilio_client import TwilioClient

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class RelayState:
    call_sid: str
    stream_sid: str = ""
    call_db_id: str = ""
    caller_number: str = ""
    el_conversation_id: str = ""
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    transcript: list[dict] = field(default_factory=list)
    stop_event: asyncio.Event = field(default_factory=asyncio.Event)


class CallRelay:
    def __init__(
        self,
        call_sid: str,
        agent_id: str,
        api_key: str,
        supabase: SupabaseService,
        twilio_sms: TwilioClient,
        aic_processor=None,
    ):
        self.call_sid = call_sid
        self.agent_id = agent_id
        self.api_key = api_key
        self.supabase = supabase
        self.twilio_sms = twilio_sms
        self.aic_processor = aic_processor
        self.state = RelayState(call_sid=call_sid)

    async def run(self, twilio_ws: WebSocket) -> None:
        """Entry point. Called from the FastAPI WebSocket route."""
        el_client = ElevenLabsClient(self.agent_id, self.api_key)
        try:
            await el_client.connect()
            task_a = asyncio.create_task(
                self._handle_twilio_events(twilio_ws, el_client),
                name=f"twilio→el:{self.call_sid}",
            )
            task_b = asyncio.create_task(
                self._handle_elevenlabs_events(el_client, twilio_ws),
                name=f"el→twilio:{self.call_sid}",
            )
            done, pending = await asyncio.wait(
                {task_a, task_b},
                return_when=asyncio.FIRST_COMPLETED,
            )
            # Give the other task a brief window to flush buffered events
            await asyncio.sleep(0.5)
            for t in pending:
                t.cancel()
                try:
                    await t
                except (asyncio.CancelledError, Exception):
                    pass
            for t in done:
                exc = t.exception()
                if exc:
                    logger.error("Relay task %s raised: %s", t.get_name(), exc)
            # Call completion handler once, after both tasks settle
            await self._on_call_complete()
        except Exception as exc:
            logger.error("CallRelay.run error for %s: %s", self.call_sid, exc)
        finally:
            await el_client.close()

    async def _handle_twilio_events(
        self, twilio_ws: WebSocket, el_client: ElevenLabsClient
    ) -> None:
        """Receive Twilio Media Stream events and forward cleaned audio to EL."""
        async for raw in twilio_ws.iter_text():
            if self.state.stop_event.is_set():
                break
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            event = msg.get("event")

            if event == "connected":
                logger.info("Twilio stream connected for %s", self.call_sid)

            elif event == "start":
                meta = msg.get("start", {})
                self.state.stream_sid = meta.get("streamSid", "")
                self.state.caller_number = meta.get("customParameters", {}).get(
                    "from", meta.get("callSid", self.call_sid)
                )
                # Call SID from start event overrides the one from TwiML if present
                actual_sid = meta.get("callSid", self.call_sid)
                try:
                    self.state.call_db_id = await self.supabase.create_call(
                        call_sid=actual_sid,
                        from_number=meta.get("customParameters", {}).get("from"),
                        to_number=meta.get("customParameters", {}).get("to"),
                    )
                    await self.supabase.update_call_stream_sid(actual_sid, self.state.stream_sid)
                except Exception as exc:
                    logger.error("DB error on call start: %s", exc)
                logger.info(
                    "Stream started: call_sid=%s stream_sid=%s db_id=%s",
                    actual_sid, self.state.stream_sid, self.state.call_db_id,
                )

            elif event == "media":
                payload_b64 = msg.get("media", {}).get("payload", "")
                if not payload_b64:
                    continue
                try:
                    import base64
                    mulaw_bytes = base64.b64decode(payload_b64)
                    pcm16 = mulaw_to_pcm16(mulaw_bytes)
                    enhanced = await enhance_with_aicoustics(
                        pcm16, self.aic_processor, sample_rate=8000
                    )
                    await el_client.send_audio(enhanced)
                except Exception as exc:
                    logger.warning("Media forwarding error: %s", exc)

            elif event == "stop":
                logger.info("Twilio stream stop event for %s", self.call_sid)
                self.state.stop_event.set()
                break

    async def _handle_elevenlabs_events(
        self, el_client: ElevenLabsClient, twilio_ws: WebSocket
    ) -> None:
        """Receive EL events, send audio back to Twilio, capture transcript."""
        async for msg in el_client.receive():
            msg_type = msg.get("type", "")

            # Ping must be ponged before anything else — even if stopping.
            # EL disconnects if pong not sent within 5s.
            if msg_type == "ping":
                ping_event = msg.get("ping_event", {})
                event_id = ping_event.get("event_id", 0)
                await el_client.send_pong(event_id)
                continue

            if self.state.stop_event.is_set():
                break

            if msg_type == "conversation_initiation_metadata":
                meta = msg.get("conversation_initiation_metadata_event", {})
                self.state.el_conversation_id = meta.get("conversation_id", "")
                if self.state.call_db_id and self.state.el_conversation_id:
                    asyncio.create_task(
                        self.supabase.update_call_el_conversation_id(
                            self.call_sid, self.state.el_conversation_id
                        )
                    )
                logger.info("EL conversation started: %s", self.state.el_conversation_id)

            elif msg_type == "audio":
                audio_event = msg.get("audio_event", {})
                audio_b64 = audio_event.get("audio_base_64", "")
                if not audio_b64:
                    continue
                try:
                    twilio_payload = elevenlabs_audio_to_twilio_payload(
                        audio_b64,
                        el_is_mulaw=settings.el_is_mulaw,
                        apply_filter=settings.apply_telephone_filter,
                        filter_order=settings.telephone_filter_order,
                    )
                    await twilio_ws.send_text(json.dumps({
                        "event": "media",
                        "streamSid": self.state.stream_sid,
                        "media": {"payload": twilio_payload},
                    }))
                except Exception as exc:
                    logger.warning("Audio forwarding EL→Twilio error: %s", exc)

            elif msg_type == "agent_response":
                agent_event = msg.get("agent_response_event", {})
                text = agent_event.get("agent_response", "")
                if text:
                    chunk = {"speaker": "agent", "text": text, "timestamp_ms": self._now_ms()}
                    self.state.transcript.append(chunk)
                    if self.state.call_db_id:
                        asyncio.create_task(
                            self.supabase.save_transcript_chunk(
                                self.state.call_db_id, "agent", text, chunk["timestamp_ms"]
                            )
                        )

            elif msg_type == "user_transcript":
                user_event = msg.get("user_transcription_event", {})
                text = user_event.get("user_transcript", "")
                if text:
                    chunk = {"speaker": "caller", "text": text, "timestamp_ms": self._now_ms()}
                    self.state.transcript.append(chunk)
                    if self.state.call_db_id:
                        asyncio.create_task(
                            self.supabase.save_transcript_chunk(
                                self.state.call_db_id, "caller", text, chunk["timestamp_ms"]
                            )
                        )

            elif msg_type == "interruption":
                logger.debug("EL interruption event for %s", self.call_sid)

    async def _on_call_complete(self) -> None:
        """Finalize call in DB and send SMS to caller."""
        try:
            ended_at = datetime.now(timezone.utc)
            duration = int((ended_at - self.state.started_at).total_seconds())
            if self.state.call_db_id:
                await self.supabase.complete_call(
                    call_sid=self.call_sid,
                    duration_seconds=duration,
                    transcript=self.state.transcript,
                    elevenlabs_conversation_id=self.state.el_conversation_id or None,
                )
                logger.info(
                    "Call %s completed: duration=%ds transcript_chunks=%d",
                    self.call_sid, duration, len(self.state.transcript),
                )
            caller_phone = self.state.caller_number
            if caller_phone and self.state.call_db_id:
                await self.twilio_sms.send_sms(
                    to=caller_phone,
                    body=(
                        f"Thank you for contacting Allianz. Your claim reference is "
                        f"{self.state.call_db_id[:8].upper()}. "
                        f"An assessor will contact you within 48 hours."
                    ),
                )
        except Exception as exc:
            logger.error("_on_call_complete error for %s: %s", self.call_sid, exc)

    def _now_ms(self) -> int:
        return int((datetime.now(timezone.utc) - self.state.started_at).total_seconds() * 1000)
