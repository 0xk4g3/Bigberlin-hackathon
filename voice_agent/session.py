"""
VoiceAgentSession — manages one Deepgram Voice Agent connection per call.

Bridges two WebSocket connections:
  Twilio WebSocket  ←→  VoiceAgentSession  ←→  Deepgram Voice Agent API

Audio flow:
  1. Twilio sends mulaw audio as base64 JSON → decoded → raw bytes to Deepgram
  2. Deepgram sends raw mulaw bytes back     → encoded to base64 → JSON to Twilio

Also:
  - Accumulates the full call transcript (ConversationText events)
  - Tracks caller phone and call start time
  - On cleanup, finalises the claim and broadcasts to the dashboard
  - Handles barge-in (clears Twilio audio buffer when user speaks)
  - Dispatches function calls to function_handlers.py
"""
import asyncio
import base64
import json
import logging
from datetime import datetime

from starlette.websockets import WebSocket

from deepgram import AsyncDeepgramClient
from deepgram.core.pydantic_utilities import parse_obj_as
from deepgram.agent.v1 import (
    AgentV1SettingsApplied,
    AgentV1FunctionCallRequest,
    AgentV1ConversationText,
    AgentV1UserStartedSpeaking,
    AgentV1AgentAudioDone,
    AgentV1Error,
    AgentV1Warning,
    AgentV1SendFunctionCallResponse,
)
from deepgram.agent.v1.socket_client import V1SocketClientResponse

from voice_agent.agent_config import get_agent_config

logger = logging.getLogger(__name__)


class VoiceAgentSession:
    """Manages one Deepgram Voice Agent session for the lifetime of a phone call."""

    def __init__(
        self,
        twilio_ws: WebSocket,
        call_sid: str,
        stream_sid: str,
        caller_phone: str = "unknown",
    ):
        self.twilio_ws   = twilio_ws
        self.call_sid    = call_sid
        self.stream_sid  = stream_sid
        self.caller_phone = caller_phone

        # Deepgram connection state
        self._client          = None
        self._connection      = None
        self._context_manager = None

        # Coordination
        self._settings_applied = asyncio.Event()
        self._cleanup_done     = False

        # Tasks
        self._listen_task = None
        self._audio_task  = None

        # Call tracking
        self._start_time: datetime = datetime.now()
        self._transcript: list[dict] = []          # accumulated ConversationText events

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self):
        """Connect to Deepgram, configure, and start the receive loop."""
        logger.info(f"[SESSION:{self.call_sid}] Connecting to Deepgram Voice Agent API")

        self._client          = AsyncDeepgramClient()
        self._context_manager = self._client.agent.v1.connect()
        self._connection      = await self._context_manager.__aenter__()

        # Use our own receive loop instead of the SDK's start_listening()
        # so that unknown message types are skipped gracefully.
        self._listen_task = asyncio.create_task(self._listen_loop())

        config = get_agent_config()
        await self._connection.send_settings(config)

        try:
            await asyncio.wait_for(self._settings_applied.wait(), timeout=5.0)
            logger.info(f"[SESSION:{self.call_sid}] Settings applied — ready for audio")
        except asyncio.TimeoutError:
            logger.error(f"[SESSION:{self.call_sid}] Timeout waiting for settings")
            raise

    async def run(self):
        """Forward audio from Twilio to Deepgram until the call ends."""
        self._audio_task = asyncio.create_task(self._forward_twilio_audio())

        done, pending = await asyncio.wait(
            [self._audio_task, self._listen_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        logger.info(f"[SESSION:{self.call_sid}] Call ended")

    async def cleanup(self):
        """Release resources and push the completed claim to the dashboard."""
        if self._cleanup_done:
            return
        self._cleanup_done = True

        logger.info(f"[SESSION:{self.call_sid}] Cleaning up")

        for task in [self._audio_task, self._listen_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        if self._context_manager:
            try:
                await self._context_manager.__aexit__(None, None, None)
            except Exception as e:
                logger.debug(f"[SESSION:{self.call_sid}] Deepgram cleanup error: {e}")

        self._connection = None
        self._client     = None

        # Finalise and broadcast to the dashboard
        duration_secs = int((datetime.now() - self._start_time).total_seconds())
        try:
            from backend.claims_service import finalize_call
            await finalize_call(
                call_sid=self.call_sid,
                caller_phone=self.caller_phone,
                transcript=self._transcript,
                duration_secs=duration_secs,
            )
        except Exception as e:
            logger.error(f"[SESSION:{self.call_sid}] Failed to finalise claim: {e}")

        logger.info(f"[SESSION:{self.call_sid}] Cleanup complete")

    # ------------------------------------------------------------------
    # Receive loop
    # ------------------------------------------------------------------

    async def _listen_loop(self):
        """Read messages from Deepgram, skipping unrecognised types."""
        try:
            async for raw_message in self._connection._websocket:
                try:
                    if isinstance(raw_message, bytes):
                        parsed = raw_message
                    else:
                        json_data = json.loads(raw_message)
                        parsed    = parse_obj_as(V1SocketClientResponse, json_data)
                except Exception:
                    msg_type = (
                        json_data.get("type", "unknown")
                        if isinstance(raw_message, str)
                        else "binary"
                    )
                    logger.debug(f"[SESSION:{self.call_sid}] Skipping: {msg_type}")
                    continue

                if isinstance(parsed, AgentV1SettingsApplied):
                    self._settings_applied.set()
                else:
                    await self._handle_message(parsed)
        except Exception as e:
            logger.info(f"[SESSION:{self.call_sid}] Deepgram listen loop ended: {e}")
        finally:
            logger.info(f"[SESSION:{self.call_sid}] Deepgram connection closed")

    async def _handle_message(self, message):
        """Process a single message from the Deepgram Voice Agent."""
        try:
            if isinstance(message, bytes):
                # Agent audio → forward to Twilio
                audio_b64 = base64.b64encode(message).decode("utf-8")
                await self.twilio_ws.send_json({
                    "event":     "media",
                    "streamSid": self.stream_sid,
                    "media":     {"payload": audio_b64},
                })

            elif isinstance(message, AgentV1FunctionCallRequest):
                await self._handle_function_call(message)

            elif isinstance(message, AgentV1ConversationText):
                logger.info(
                    f"[SESSION:{self.call_sid}] {message.role.upper()}: {message.content}"
                )
                # Accumulate for the dashboard transcript
                elapsed   = int((datetime.now() - self._start_time).total_seconds())
                mins, sec = divmod(elapsed, 60)
                self._transcript.append({
                    "role":      message.role,
                    "text":      message.content,
                    "timestamp": f"00:{mins:02d}:{sec:02d}",
                })

            elif isinstance(message, AgentV1UserStartedSpeaking):
                logger.info(f"[SESSION:{self.call_sid}] User started speaking")
                await self.twilio_ws.send_json({
                    "event":     "clear",
                    "streamSid": self.stream_sid,
                })

            elif isinstance(message, AgentV1AgentAudioDone):
                logger.debug(f"[SESSION:{self.call_sid}] Agent finished speaking")

            elif isinstance(message, AgentV1Error):
                logger.error(f"[SESSION:{self.call_sid}] Agent error: {message.description}")

            elif isinstance(message, AgentV1Warning):
                logger.warning(f"[SESSION:{self.call_sid}] Agent warning: {message.description}")

        except Exception as e:
            logger.error(f"[SESSION:{self.call_sid}] Error handling message: {e}")

    # ------------------------------------------------------------------
    # Function calls
    # ------------------------------------------------------------------

    async def _handle_function_call(self, event: AgentV1FunctionCallRequest):
        """Dispatch a function call from the agent to the backend."""
        if not event.functions:
            return

        func          = event.functions[0]
        function_name = func.name
        call_id       = func.id
        args          = json.loads(func.arguments) if func.arguments else {}

        logger.info(f"[SESSION:{self.call_sid}] Function call: {function_name}({args})")

        try:
            from voice_agent.function_handlers import dispatch_function
            result = await dispatch_function(function_name, args, call_sid=self.call_sid)
            logger.info(
                f"[SESSION:{self.call_sid}] Function result: {function_name} → {json.dumps(result)}"
            )
        except Exception as e:
            logger.error(f"[SESSION:{self.call_sid}] Function error: {function_name} → {e}")
            result = {"error": str(e)}

        response = AgentV1SendFunctionCallResponse(
            type="FunctionCallResponse",
            name=function_name,
            content=json.dumps(result),
            id=call_id,
        )
        await self._connection.send_function_call_response(response)

        if function_name == "end_call":
            asyncio.create_task(self._end_call_after_delay())

    # ------------------------------------------------------------------
    # Call termination
    # ------------------------------------------------------------------

    async def _end_call_after_delay(self):
        """Wait for the goodbye audio, then hang up via Twilio REST API."""
        await asyncio.sleep(3)
        logger.info(f"[SESSION:{self.call_sid}] Hanging up")

        from config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN
        if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
            try:
                from twilio.rest import Client
                client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
                await asyncio.to_thread(
                    client.calls(self.call_sid).update,
                    status="completed",
                )
                logger.info(f"[SESSION:{self.call_sid}] Twilio call completed")
            except Exception as e:
                logger.error(f"[SESSION:{self.call_sid}] Failed to complete Twilio call: {e}")

        try:
            await self.twilio_ws.close()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Audio forwarding
    # ------------------------------------------------------------------

    async def _forward_twilio_audio(self):
        """Read Twilio WebSocket messages and forward mulaw audio to Deepgram."""
        try:
            while True:
                message = await self.twilio_ws.receive_text()
                data    = json.loads(message)

                if data.get("event") == "media":
                    payload     = data["media"]["payload"]
                    audio_bytes = base64.b64decode(payload)
                    if self._connection:
                        await self._connection.send_media(audio_bytes)

                elif data.get("event") == "stop":
                    logger.info(f"[SESSION:{self.call_sid}] Twilio stream stopped")
                    break

        except Exception as e:
            logger.info(f"[SESSION:{self.call_sid}] Twilio WebSocket closed: {e}")
