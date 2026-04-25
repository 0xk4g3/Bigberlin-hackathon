"""
ElevenLabs Conversational AI WebSocket client.

Connects to: wss://api.elevenlabs.io/v1/convai/conversation?agent_id={AGENT_ID}
Handles: send_audio, receive events, ping/pong.

Ping/pong is handled in relay.py's EL receive loop — this module only
provides the connection and send primitives.
"""

import asyncio
import base64
import json
import logging
from typing import AsyncGenerator, Optional

import websockets
from websockets.asyncio.client import ClientConnection

logger = logging.getLogger(__name__)

EL_WS_URL = "wss://api.elevenlabs.io/v1/convai/conversation"


class ElevenLabsClient:
    def __init__(self, agent_id: str, api_key: str):
        self.agent_id = agent_id
        self.api_key = api_key
        self._ws: Optional[ClientConnection] = None

    async def connect(self) -> "ElevenLabsClient":
        url = f"{EL_WS_URL}?agent_id={self.agent_id}"
        self._ws = await websockets.connect(
            url,
            additional_headers={"xi-api-key": self.api_key},
            ping_interval=None,  # EL manages its own ping/pong protocol
        )
        logger.info("ElevenLabs WebSocket connected for agent %s", self.agent_id)
        return self

    async def send_audio(self, pcm16_bytes: bytes) -> None:
        """Send caller audio chunk to ElevenLabs."""
        if self._ws is None:
            raise RuntimeError("ElevenLabs WebSocket not connected")
        payload = json.dumps({"user_audio_chunk": base64.b64encode(pcm16_bytes).decode()})
        await self._ws.send(payload)

    async def send_pong(self, event_id: int) -> None:
        """Respond to EL ping — must be within 5 seconds or connection drops."""
        if self._ws is None:
            return
        await self._ws.send(json.dumps({"type": "pong", "event_id": event_id}))

    async def receive(self) -> AsyncGenerator[dict, None]:
        """Async generator yielding parsed EL messages."""
        if self._ws is None:
            raise RuntimeError("ElevenLabs WebSocket not connected")
        async for raw in self._ws:
            try:
                yield json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("EL sent non-JSON message: %s", raw[:200])

    async def close(self) -> None:
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
            logger.info("ElevenLabs WebSocket closed")

    @property
    def connected(self) -> bool:
        return self._ws is not None and not self._ws.closed
