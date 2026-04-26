"""
Claims service — stores per-call claim drafts and broadcasts completed
claims to all connected dashboard WebSocket clients.

Flow:
  1. telephony/routes.py accepts a call  → VoiceAgentSession starts
  2. Agent calls submit_claim()          → draft stored by call_sid
  3. Call ends / cleanup()              → finalize_call() merges transcript
                                           and broadcasts to dashboard /ws clients
"""
import json
import logging
import random
from datetime import datetime

from starlette.websockets import WebSocket

logger = logging.getLogger(__name__)

# --- connected dashboard clients -------------------------------------------
_ws_clients: set[WebSocket] = set()

# --- per-call state ---------------------------------------------------------
# call_sid -> claim fields submitted by the agent via submit_claim()
_drafts: dict[str, dict] = {}

# --- completed tickets (in-memory store) ------------------------------------
# Sent to any new dashboard client that connects after a call has already ended
_completed_tickets: list[dict] = []


# ---------------------------------------------------------------------------
# Dashboard WebSocket management
# ---------------------------------------------------------------------------

async def register_ws_client(websocket: WebSocket) -> None:
    """Accept a dashboard WebSocket, replay past tickets, then keep it alive."""
    await websocket.accept()
    _ws_clients.add(websocket)
    logger.info(f"[DASHBOARD] Client connected ({len(_ws_clients)} total)")

    # Replay any tickets that completed before this client connected
    for ticket in _completed_tickets:
        try:
            await websocket.send_text(json.dumps({"type": "call_ended", "data": ticket}))
        except Exception:
            break

    try:
        while True:
            await websocket.receive_text()          # keep-alive / ignore messages
    except Exception:
        pass
    finally:
        _ws_clients.discard(websocket)
        logger.info(f"[DASHBOARD] Client disconnected ({len(_ws_clients)} remaining)")


async def _broadcast(data: dict) -> None:
    """Send a JSON payload to every connected dashboard client."""
    if not _ws_clients:
        logger.info("[DASHBOARD] No clients connected — skipping broadcast")
        return
    payload = json.dumps(data)
    dead: set[WebSocket] = set()
    for ws in list(_ws_clients):
        try:
            await ws.send_text(payload)
        except Exception:
            dead.add(ws)
    for ws in dead:
        _ws_clients.discard(ws)
    logger.info(f"[DASHBOARD] Broadcast sent to {len(_ws_clients)} client(s)")


# ---------------------------------------------------------------------------
# Claim lifecycle
# ---------------------------------------------------------------------------

def _gen_claim_ref() -> str:
    year = datetime.now().year
    num = random.randint(1000, 9999)
    return f"INCA-{year}-{num}"


async def submit_claim_draft(call_sid: str, args: dict) -> str:
    """Store the agent-submitted claim fields and return a claim reference."""
    claim_ref = _gen_claim_ref()
    _drafts[call_sid] = {**args, "claimRef": claim_ref}
    logger.info(f"[CLAIMS] Draft stored for {call_sid}: {claim_ref}")
    return claim_ref


async def finalize_call(
    call_sid: str,
    caller_phone: str,
    transcript: list[dict],
    duration_secs: int,
) -> None:
    """
    Merge the claim draft with the full transcript and broadcast to the dashboard.
    Called from VoiceAgentSession.cleanup() after every call.
    """
    draft = _drafts.pop(call_sid, {})

    claim_ref   = draft.get("claimRef") or _gen_claim_ref()
    caller_name = draft.get("caller_name") or "Unknown caller"
    loss_type   = draft.get("loss_type")   or "Not specified"
    location    = draft.get("location")    or "Unknown"

    now       = datetime.now()
    date_str  = now.strftime("%b %d, %Y")
    mins, sec = divmod(duration_secs, 60)
    duration_str = f"{mins:02d}:{sec:02d}"

    vehicle_plate = (
        draft.get("vehicle_plate")
        or draft.get("caller_vehicle_plate")
        or draft.get("license_plate")
    )

    fields = [
        {"key": "Date of loss",    "value": draft.get("date_of_loss")},
        {"key": "Time of loss",    "value": draft.get("time_of_loss")},
        {"key": "Location",        "value": location},
        {"key": "Loss type",       "value": loss_type},
        {"key": "Vehicle plate",   "value": vehicle_plate},
        {"key": "3rd party plate", "value": draft.get("third_party_plate")},
        {"key": "Police report",   "value": draft.get("police_report")},
        {"key": "Injuries",        "value": draft.get("injuries")},
        {"key": "Drivable",        "value": draft.get("drivable")},
        {"key": "Policy no.",      "value": draft.get("policy_number")},
        {"key": "Repair shop",     "value": draft.get("repair_shop")},
    ]

    messages = [
        {
            "id":        str(i + 1),
            "role":      msg["role"],
            "text":      msg["text"],
            "timestamp": msg["timestamp"],
        }
        for i, msg in enumerate(transcript)
    ]

    ticket = {
        "id":          call_sid,
        "claimRef":    claim_ref,
        "callerName":  caller_name,
        "callerPhone": caller_phone,
        "date":        date_str,
        "duration":    duration_str,
        "lossType":    loss_type,
        "location":    location,
        "fields":      fields,
        "messages":    messages,
    }

    logger.info(f"[CLAIMS] Finalizing {claim_ref} — {len(messages)} transcript lines")
    _completed_tickets.append(ticket)
    await _broadcast({"type": "call_ended", "data": ticket})
