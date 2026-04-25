from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from services.supabase_client import SupabaseService

router = APIRouter(prefix="/calls", tags=["calls"])


def _get_supabase(request: Request) -> SupabaseService:
    return request.app.state.supabase


@router.get("")
async def list_calls(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    supabase: SupabaseService = Depends(_get_supabase),
):
    calls = await supabase.get_calls(limit=limit, offset=offset, status=status)
    # Add transcript preview (first 3 lines)
    for call in calls:
        transcript = call.get("transcript") or []
        call["transcript_preview"] = transcript[:3]
    return calls


@router.get("/{call_sid}")
async def get_call(
    call_sid: str,
    supabase: SupabaseService = Depends(_get_supabase),
):
    call = await supabase.get_call(call_sid)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    return call
