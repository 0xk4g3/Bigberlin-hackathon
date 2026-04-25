"""
Twilio routes:
  POST /incoming-call  — return TwiML to start Media Stream
  WS   /twilio-stream  — Media Stream WebSocket → CallRelay
"""

import logging
from fastapi import APIRouter, Request, WebSocket
from fastapi.responses import Response

from config import get_settings
from websocket.relay import CallRelay

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(tags=["twilio"])

_TWIML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="wss://{host}/twilio-stream">
            <Parameter name="agent_id" value="{agent_id}"/>
        </Stream>
    </Connect>
</Response>"""


@router.post("/incoming-call")
async def incoming_call(request: Request):
    """
    Twilio calls this when someone dials our number.
    Responds with TwiML that opens a Media Stream WebSocket.
    No <Say> before <Connect> — any TTS adds 1-2s silence at call start.
    """
    if settings.twilio_validate_requests and settings.environment == "production":
        try:
            from twilio.request_validator import RequestValidator
            validator = RequestValidator(settings.twilio_auth_token)
            form = await request.form()
            url = str(request.url)
            signature = request.headers.get("X-Twilio-Signature", "")
            if not validator.validate(url, dict(form), signature):
                logger.warning("Invalid Twilio signature from %s", request.client)
                return Response(content="Forbidden", status_code=403)
        except Exception as exc:
            logger.error("Twilio signature validation error: %s", exc)

    host = settings.app_host.replace("https://", "").replace("http://", "")
    twiml = _TWIML_TEMPLATE.format(
        host=host,
        agent_id=settings.elevenlabs_agent_id,
    )
    return Response(content=twiml, media_type="application/xml")


@router.websocket("/twilio-stream")
async def twilio_stream(websocket: WebSocket):
    """Twilio Media Stream connects here. Relay manages the full call lifecycle."""
    await websocket.accept()
    state = websocket.app.state
    relay = CallRelay(
        call_sid="pending",  # Real call_sid extracted from Twilio start event
        agent_id=settings.elevenlabs_agent_id,
        api_key=settings.elevenlabs_api_key,
        supabase=state.supabase,
        twilio_sms=state.twilio,
        aic_processor=getattr(state, "aic_processor", None),
    )
    await relay.run(websocket)
