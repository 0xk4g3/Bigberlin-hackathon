from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from services.supabase_client import SupabaseService

router = APIRouter(prefix="/claims", tags=["claims"])


def _get_supabase(request: Request) -> SupabaseService:
    return request.app.state.supabase


def _get_twilio(request: Request):
    return request.app.state.twilio


class ApproveRequest(BaseModel):
    approved_by: str = "operator"


@router.get("")
async def list_claims(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    urgency: Optional[str] = Query(None),
    fraud_score: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD"),
    supabase: SupabaseService = Depends(_get_supabase),
):
    return await supabase.get_claims(
        limit=limit,
        offset=offset,
        status=status,
        urgency=urgency,
        fraud_score=fraud_score,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/stats")
async def live_stats(supabase: SupabaseService = Depends(_get_supabase)):
    return await supabase.get_live_stats()


@router.get("/{claim_id}")
async def get_claim(
    claim_id: str,
    supabase: SupabaseService = Depends(_get_supabase),
):
    claim = await supabase.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim


@router.post("/{claim_id}/approve")
async def approve_claim(
    claim_id: str,
    body: ApproveRequest,
    request: Request,
    supabase: SupabaseService = Depends(_get_supabase),
):
    claim = await supabase.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    if claim["status"] not in ("opened", "processing"):
        raise HTTPException(status_code=400, detail=f"Cannot approve claim with status '{claim['status']}'")

    updated = await supabase.approve_claim(claim_id, body.approved_by)

    # Send confirmation SMS to policyholder
    phone = claim.get("policyholder_phone")
    if phone:
        twilio = _get_twilio(request)
        sla = claim.get("assessor_sla_hours", 48)
        werkstatt = claim.get("werkstattbindung", False)
        msg = (
            f"Your Allianz claim {claim_id[:8].upper()} has been approved. "
            f"An assessor will contact you within {sla} hours."
        )
        if werkstatt:
            msg += " Please use a network garage for repairs."
        await twilio.send_sms(to=phone, body=msg)

    return updated or claim
