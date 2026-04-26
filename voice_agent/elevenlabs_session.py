"""
ElevenLabsSession — connects to ElevenLabs Conversational AI for one phone call.

Bridges Twilio (mulaw 8 kHz) ↔ ElevenLabs ConvAI (PCM 16 kHz). On hangup, optional
GPT extraction fills dashboard fields when OPENAI_API_KEY is set.
"""
import asyncio
import audioop
import base64
import json
import logging
import re
from datetime import datetime

import websockets
from openai import AsyncOpenAI
from starlette.websockets import WebSocket

logger = logging.getLogger(__name__)

EL_WS_URL = "wss://api.elevenlabs.io/v1/convai/conversation"

_TAG_RE = re.compile(r"\[[^\]]{1,40}\]\s*", re.MULTILINE)


def _strip_eleven_tags(text: str) -> str:
    return _TAG_RE.sub("", text).strip()


def _lower_keys(d: dict) -> dict:
    out = {}
    for k, v in d.items():
        if not isinstance(k, str):
            continue
        out[k.strip().lower().replace(" ", "_")] = v
    return out


def _normalize_extracted(raw: dict) -> dict:
    if not isinstance(raw, dict):
        return {}
    d = _lower_keys(raw)
    if "claim" in d and isinstance(d["claim"], dict):
        inner = _lower_keys(d["claim"])
        d = {**d, **inner}
        d.pop("claim", None)

    def pick(*names: str):
        for n in names:
            if n not in d:
                continue
            val = d[n]
            if val is None:
                continue
            if isinstance(val, str):
                val = val.strip()
                if not val or val.lower() == "null":
                    continue
                return val
            if isinstance(val, bool):
                return "Yes" if val else "No"
            return str(val)
        return None

    return {
        "caller_name": pick(
            "caller_name", "caller", "name", "insured_name",
            "reporting_party", "claimant_name",
        ),
        "policy_number": pick("policy_number", "policy_no", "policy"),
        "date_of_loss": pick("date_of_loss", "loss_date", "date_of_accident", "incident_date"),
        "time_of_loss": pick("time_of_loss", "loss_time", "time_of_accident", "incident_time"),
        "location": pick("location", "accident_location", "place", "where", "incident_location"),
        "loss_type": pick("loss_type", "type_of_loss", "incident_type", "nature_of_loss"),
        "description": pick("description", "narrative", "what_happened", "incident_description"),
        "vehicle_plate": pick(
            "vehicle_plate", "license_plate", "plate", "registration",
            "caller_vehicle_plate", "insured_plate", "vehicle_registration",
        ),
        "third_party_plate": pick(
            "third_party_plate", "other_party_plate", "opponent_plate", "tp_plate",
        ),
        "police_report": pick(
            "police_report", "police_report_number", "police_reference", "police_ref",
        ),
        "injuries": pick("injuries", "injury", "any_injuries", "casualties"),
        "drivable": pick("drivable", "vehicle_drivable", "is_drivable", "car_drivable"),
        "repair_shop": pick("repair_shop", "garage", "body_shop"),
    }


async def _send_pong_if_ping(ws, call_sid: str, data: dict) -> bool:
    if data.get("type") != "ping":
        return False
    pe = data.get("ping_event") or {}
    eid = pe.get("event_id")
    if eid is not None:
        await ws.send(json.dumps({"type": "pong", "event_id": eid}))
        logger.debug(f"[EL:{call_sid}] pong → event_id={eid}")
    return True


class ElevenLabsSession:
    def __init__(
        self,
        twilio_ws: WebSocket,
        call_sid: str,
        stream_sid: str,
        caller_phone: str = "unknown",
    ):
        self.twilio_ws = twilio_ws
        self.call_sid = call_sid
        self.stream_sid = stream_sid
        self.caller_phone = caller_phone

        self._el_ws: websockets.WebSocketClientProtocol | None = None
        self._start_time = datetime.now()
        self._transcript: list[dict] = []
        self._cleanup_done = False
        self._audio_task: asyncio.Task | None = None
        self._receive_task: asyncio.Task | None = None

    async def _drain_init_until_ready(self):
        """Read ElevenLabs handshake until conversation/ASR metadata.

        Must run while `_forward_twilio_audio` is already feeding `user_audio_chunk`
        where possible: some agent pipelines only emit the first turn after they see
        inbound audio, which would otherwise sound like a silent answered call.
        """
        while True:
            raw = await self._el_ws.recv()
            if isinstance(raw, bytes):
                await self._send_audio_to_twilio(raw)
                continue
            init_data = json.loads(raw)
            if await _send_pong_if_ping(self._el_ws, self.call_sid, init_data):
                continue
            mt = init_data.get("type", "")
            if mt == "conversation_initiation_metadata":
                logger.info(
                    f"[EL:{self.call_sid}] Init: {mt} "
                    f"conv_id={init_data.get('conversation_initiation_metadata_event', {}).get('conversation_id', '?')}"
                )
                break
            if mt == "asr_initiation_metadata":
                logger.info(f"[EL:{self.call_sid}] Init: {mt}")
                break
            logger.info(f"[EL:{self.call_sid}] Init (pre-metadata): {mt}")
            await self._dispatch(init_data)

    async def run(self):
        from config import ELEVENLABS_API_KEY, ELEVENLABS_AGENT_ID, ELEVENLABS_COMPANY_NAME

        logger.info(f"[EL:{self.call_sid}] Connecting to ElevenLabs agent {ELEVENLABS_AGENT_ID}")

        url = f"{EL_WS_URL}?agent_id={ELEVENLABS_AGENT_ID}&inactivity_timeout=180"
        self._el_ws = await websockets.connect(
            url,
            additional_headers={"xi-api-key": ELEVENLABS_API_KEY},
        )

        await self._el_ws.send(
            json.dumps({
                "type": "conversation_initiation_client_data",
                "dynamic_variables": {"company_name": ELEVENLABS_COMPANY_NAME},
            })
        )

        # Caller → ElevenLabs during init so the model sees line audio while the
        # handshake runs (avoids silent answered calls when the agent waits for input).
        self._audio_task = asyncio.create_task(self._forward_twilio_audio())
        try:
            await self._drain_init_until_ready()
        except BaseException:
            if self._audio_task and not self._audio_task.done():
                self._audio_task.cancel()
                try:
                    await self._audio_task
                except asyncio.CancelledError:
                    pass
            raise

        logger.info(f"[EL:{self.call_sid}] Ready for audio")

        self._receive_task = asyncio.create_task(self._handle_elevenlabs())

        done, pending = await asyncio.wait(
            [self._audio_task, self._receive_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        logger.info(f"[EL:{self.call_sid}] Call ended")

    async def cleanup(self):
        if self._cleanup_done:
            return
        self._cleanup_done = True

        for task in [self._audio_task, self._receive_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        if self._el_ws:
            try:
                await self._el_ws.close()
            except Exception:
                pass

        duration_secs = int((datetime.now() - self._start_time).total_seconds())
        claim_data = await self._extract_claim_data()

        try:
            from backend.claims_service import submit_claim_draft, finalize_call

            if claim_data:
                await submit_claim_draft(self.call_sid, claim_data)
            await finalize_call(
                call_sid=self.call_sid,
                caller_phone=self.caller_phone,
                transcript=self._transcript,
                duration_secs=duration_secs,
            )
        except Exception as e:
            logger.error(f"[EL:{self.call_sid}] Failed to finalise claim: {e}")

        logger.info(f"[EL:{self.call_sid}] Cleanup complete")

    async def _forward_twilio_audio(self):
        try:
            while True:
                msg = await self.twilio_ws.receive_text()
                data = json.loads(msg)

                if data.get("event") == "media":
                    mulaw_bytes = base64.b64decode(data["media"]["payload"])
                    pcm8k = audioop.ulaw2lin(mulaw_bytes, 2)
                    pcm16k = audioop.ratecv(pcm8k, 2, 1, 8000, 16000, None)[0]
                    pcm_b64 = base64.b64encode(pcm16k).decode()
                    await self._el_ws.send(json.dumps({"user_audio_chunk": pcm_b64}))

                elif data.get("event") == "stop":
                    logger.info(f"[EL:{self.call_sid}] Twilio stream stopped")
                    break
        except Exception as e:
            logger.info(f"[EL:{self.call_sid}] Twilio WS closed: {e}")

    async def _handle_elevenlabs(self):
        try:
            async for msg in self._el_ws:
                try:
                    if isinstance(msg, bytes):
                        await self._send_audio_to_twilio(msg)
                    else:
                        await self._dispatch(json.loads(msg))
                except Exception as e:
                    logger.warning(f"[EL:{self.call_sid}] Message error: {e}")
        except Exception as e:
            logger.info(f"[EL:{self.call_sid}] ElevenLabs WS closed: {e}")

    async def _send_audio_to_twilio(self, pcm_bytes: bytes):
        pcm8k = audioop.ratecv(pcm_bytes, 2, 1, 16000, 8000, None)[0]
        mulaw_bytes = audioop.lin2ulaw(pcm8k, 2)
        audio_b64 = base64.b64encode(mulaw_bytes).decode()
        await self.twilio_ws.send_json({
            "event": "media",
            "streamSid": self.stream_sid,
            "media": {"payload": audio_b64},
        })

    async def _dispatch(self, data: dict):
        if await _send_pong_if_ping(self._el_ws, self.call_sid, data):
            return

        msg_type = data.get("type", "")

        if msg_type == "audio":
            audio_b64 = data.get("audio_event", {}).get("audio_base_64", "")
            if audio_b64:
                pcm_bytes = base64.b64decode(audio_b64)
                await self._send_audio_to_twilio(pcm_bytes)

        elif msg_type == "agent_response":
            text = data.get("agent_response_event", {}).get("agent_response", "")
            if text:
                logger.info(f"[EL:{self.call_sid}] KLAUS: {text}")
                self._append_transcript("agent", text)

        elif msg_type == "user_transcript":
            text = data.get("user_transcription_event", {}).get("user_transcript", "")
            if text:
                logger.info(f"[EL:{self.call_sid}] USER: {text}")
                self._append_transcript("caller", text)

        elif msg_type == "interruption":
            logger.info(f"[EL:{self.call_sid}] Interruption")
            try:
                await self.twilio_ws.send_json({"event": "clear", "streamSid": self.stream_sid})
            except Exception:
                pass

        elif msg_type == "client_tool_call":
            tool = data.get("client_tool_call", {})
            logger.info(f"[EL:{self.call_sid}] Tool: {tool.get('tool_name')}")

        elif msg_type in (
            "conversation_initiation_metadata", "pong",
            "internal_tentative_agent_response", "agent_response_correction",
        ):
            pass
        else:
            logger.debug(f"[EL:{self.call_sid}] Unhandled: {msg_type}")

    def _append_transcript(self, role: str, text: str):
        elapsed = int((datetime.now() - self._start_time).total_seconds())
        mins, sec = divmod(elapsed, 60)
        self._transcript.append({
            "role": role,
            "text": text,
            "timestamp": f"00:{mins:02d}:{sec:02d}",
        })

    async def _extract_claim_data(self) -> dict | None:
        if not self._transcript:
            return None

        from config import CLAIM_EXTRACTION_MODEL, OPENAI_API_KEY

        if not OPENAI_API_KEY:
            logger.error(
                f"[EL:{self.call_sid}] OPENAI_API_KEY missing — "
                "dashboard fields will stay empty until extraction is configured"
            )
            return None

        conversation = "\n".join(
            f"{'Klaus' if m['role'] == 'agent' else 'Caller'}: {_strip_eleven_tags(m['text'])}"
            for m in self._transcript
        )

        system = """You extract structured motor FNOL (first notice of loss) data from a phone transcript.
Return one JSON object only. Use null only when the fact was never stated.

Rules:
- caller_name: the FINAL corrected legal name of the person filing (if they correct themselves, use the correction).
- vehicle_plate: registration / license plate of the CALLER's vehicle involved (not the other party). NATO spellings like "Bravo Echo Golf 556" → compact plate "BEG556".
- third_party_plate: only if another vehicle's plate was given as the OTHER party; otherwise null.
- date_of_loss / time_of_loss: short strings as spoken (e.g. "26 April 2026", "10:00" or "10am").
- location: city + place in a single concise line.
- loss_type: short label (e.g. "Collision", "Stationary damage").
- injuries: "No" / "None" / brief note if stated.
- drivable: "Yes" / "No" / "Unknown" from transcript.
- police_report: reference exactly as confirmed (e.g. "AV6F"), not NATO words unless that is all that was confirmed."""

        user = f"""Keys (all top-level, same names):
caller_name, policy_number, date_of_loss, time_of_loss, location, loss_type, description,
vehicle_plate, third_party_plate, police_report, injuries, drivable, repair_shop

Transcript:
{conversation}"""

        try:
            client = AsyncOpenAI(api_key=OPENAI_API_KEY)
            response = await client.chat.completions.create(
                model=CLAIM_EXTRACTION_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
                temperature=0,
            )
            raw = json.loads(response.choices[0].message.content)
            claim_data = _normalize_extracted(raw)
            claim_data = {k: v for k, v in claim_data.items() if v is not None}
            logger.info(f"[EL:{self.call_sid}] Extracted claim: {claim_data}")
            return claim_data or None
        except Exception as e:
            logger.error(f"[EL:{self.call_sid}] Claim extraction failed: {e}")
            return None
