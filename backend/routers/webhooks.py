"""
ElevenLabs post-call webhooks:
  POST /webhook/call-complete  — FNOL extraction + claim insert
  POST /webhook/transcript     — real-time transcript chunks from EL
"""

import hashlib
import hmac
import json
import logging
import time
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from config import get_settings
from services.claim_processor import ClaimProcessor
from services.supabase_client import SupabaseService

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/webhook", tags=["webhooks"])

_claim_processor = ClaimProcessor()


def _verify_el_signature(body: bytes, signature_header: str, secret: str) -> bool:
    """
    ElevenLabs sends: X-ElevenLabs-Signature: t=<timestamp>,v0=<hmac>
    Validate HMAC-SHA256 and timestamp within 300 seconds (replay protection).
    """
    if not signature_header or not secret:
        return False
    try:
        parts = dict(item.split("=", 1) for item in signature_header.split(","))
        timestamp = parts.get("t", "")
        v0 = parts.get("v0", "")
        if not timestamp or not v0:
            return False
        age = abs(time.time() - int(timestamp))
        if age > 300:
            logger.warning("EL webhook timestamp too old: %ds", age)
            return False
        signed = f"{timestamp}.{body.decode('utf-8', errors='replace')}"
        expected = hmac.new(secret.encode(), signed.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, v0)
    except Exception as exc:
        logger.error("EL signature verification error: %s", exc)
        return False


@router.post("/call-complete")
async def call_complete(request: Request):
    """
    Called by ElevenLabs when a conversation ends.
    Extracts FNOL, scores urgency + fraud, writes claim to Supabase.
    ElevenLabs retries on non-2xx — be idempotent.
    """
    body = await request.body()
    sig = request.headers.get("X-ElevenLabs-Signature", "")

    if settings.environment == "production" and not _verify_el_signature(
        body, sig, settings.elevenlabs_webhook_secret
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    conversation_id = payload.get("conversation_id", "")
    transcript_raw = payload.get("transcript", [])  # EL sends [{role, message}]
    collected_data = payload.get("data_collection_results", {})
    metadata = payload.get("metadata", {})

    supabase: SupabaseService = request.app.state.supabase

    # Find the call by EL conversation_id
    call = await supabase.get_call_by_el_conversation_id(conversation_id)
    if not call:
        logger.warning("No call found for EL conversation_id=%s", conversation_id)
        return JSONResponse({"status": "call_not_found"}, status_code=200)

    call_id = call["id"]

    # Idempotency — don't double-process
    existing_claim = await supabase.get_claim_by_call_id(call_id)
    if existing_claim:
        logger.info("Claim already exists for call_id=%s, skipping", call_id)
        return JSONResponse({"status": "already_processed", "claim_id": existing_claim["id"]})

    # Normalise EL transcript format → our format
    transcript = [
        {
            "speaker": "agent" if t.get("role") == "agent" else "caller",
            "text": t.get("message", ""),
        }
        for t in transcript_raw
    ]

    call_metadata = {
        "from_number": call.get("from_number"),
        "call_id": call_id,
    }

    prior_claims = await supabase.check_prior_claims(
        policy_number=collected_data.get("policy_number"),
        license_plate=collected_data.get("license_plate"),
    )

    claim_data = _claim_processor.build_claim_payload(
        call_id=call_id,
        transcript=transcript,
        collected_data=collected_data,
        call_metadata=call_metadata,
        prior_claims=prior_claims,
    )

    claim_payload = claim_data.model_dump(mode="json", exclude_none=True)
    claim_id = await supabase.create_claim(claim_payload)
    logger.info(
        "Claim created: claim_id=%s urgency=%s fraud=%s siu=%s",
        claim_id, claim_data.urgency, claim_data.fraud_score, claim_data.siu_referral,
    )

    # Alert manager for critical/SIU
    if claim_data.urgency == "critical" or claim_data.siu_referral:
        twilio = request.app.state.twilio
        manager_phone = settings.claims_manager_phone
        if manager_phone:
            label = "CRITICAL" if claim_data.urgency == "critical" else "SIU FLAG"
            await twilio.send_sms(
                to=manager_phone,
                body=(
                    f"[ClaimCall {label}] Claim {claim_id[:8].upper()} "
                    f"— {claim_data.urgency_reason or 'See dashboard'}. "
                    f"Policy: {claim_data.policy_number or 'unknown'}"
                ),
            )

    return JSONResponse({"status": "ok", "claim_id": claim_id})


@router.post("/transcript")
async def transcript_chunk(request: Request):
    """
    Real-time transcript chunks from ElevenLabs during an active call.
    Must respond in <500ms or EL drops the event.
    """
    body = await request.body()
    sig = request.headers.get("X-ElevenLabs-Signature", "")

    if settings.environment == "production" and not _verify_el_signature(
        body, sig, settings.elevenlabs_webhook_secret
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    conversation_id = payload.get("conversation_id", "")
    role = payload.get("role", "")
    text = payload.get("message", "")
    timestamp_ms = payload.get("timestamp_ms")

    if not conversation_id or not text:
        return JSONResponse({"status": "ignored"})

    supabase: SupabaseService = request.app.state.supabase
    call = await supabase.get_call_by_el_conversation_id(conversation_id)
    if not call:
        return JSONResponse({"status": "call_not_found"})

    speaker = "agent" if role == "agent" else "caller"
    await supabase.save_transcript_chunk(call["id"], speaker, text, timestamp_ms)
    return JSONResponse({"status": "ok"})
