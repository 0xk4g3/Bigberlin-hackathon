"""
All Supabase operations for ClaimCall.
Uses the async supabase-py client. Service key bypasses RLS.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from supabase._async.client import AsyncClient, create_client
from config import Settings

logger = logging.getLogger(__name__)


class SupabaseService:
    def __init__(self, client: AsyncClient):
        self._db = client

    @classmethod
    async def create(cls, settings: Settings) -> "SupabaseService":
        client = await create_client(settings.supabase_url, settings.supabase_service_key)
        return cls(client)

    async def ping(self) -> bool:
        """Verify connection — lightweight select."""
        try:
            await self._db.table("calls").select("id").limit(1).execute()
            return True
        except Exception as exc:
            logger.error("Supabase ping failed: %s", exc)
            return False

    # ──────────────────────────────────────────────────────────────────────────
    # CALLS
    # ──────────────────────────────────────────────────────────────────────────

    async def create_call(
        self, call_sid: str, from_number: Optional[str], to_number: Optional[str]
    ) -> str:
        """Insert new call row. Returns the UUID."""
        res = await (
            self._db.table("calls")
            .insert({"call_sid": call_sid, "from_number": from_number, "to_number": to_number})
            .execute()
        )
        return res.data[0]["id"]

    async def update_call_stream_sid(self, call_sid: str, stream_sid: str) -> None:
        await (
            self._db.table("calls")
            .update({"stream_sid": stream_sid})
            .eq("call_sid", call_sid)
            .execute()
        )

    async def update_call_el_conversation_id(
        self, call_sid: str, conversation_id: str
    ) -> None:
        await (
            self._db.table("calls")
            .update({"elevenlabs_conversation_id": conversation_id})
            .eq("call_sid", call_sid)
            .execute()
        )

    async def complete_call(
        self,
        call_sid: str,
        duration_seconds: int,
        transcript: list[dict],
        elevenlabs_conversation_id: Optional[str] = None,
    ) -> None:
        update: dict = {
            "status": "completed",
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "duration_seconds": duration_seconds,
            "transcript": transcript,
        }
        if elevenlabs_conversation_id:
            update["elevenlabs_conversation_id"] = elevenlabs_conversation_id
        await (
            self._db.table("calls")
            .update(update)
            .eq("call_sid", call_sid)
            .execute()
        )

    async def fail_call(self, call_sid: str) -> None:
        await (
            self._db.table("calls")
            .update({"status": "failed", "ended_at": datetime.now(timezone.utc).isoformat()})
            .eq("call_sid", call_sid)
            .execute()
        )

    async def save_transcript_chunk(
        self, call_id: str, speaker: str, text: str, timestamp_ms: Optional[int]
    ) -> None:
        await (
            self._db.table("transcripts")
            .insert(
                {
                    "call_id": call_id,
                    "speaker": speaker,
                    "text": text,
                    "timestamp_ms": timestamp_ms,
                }
            )
            .execute()
        )

    async def get_calls(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> list[dict]:
        q = self._db.table("calls").select("*").order("started_at", desc=True)
        if status:
            q = q.eq("status", status)
        res = await q.range(offset, offset + limit - 1).execute()
        return res.data

    async def get_call(self, call_sid: str) -> Optional[dict]:
        try:
            res = await (
                self._db.table("calls")
                .select("*, transcripts(*), claims(*)")
                .eq("call_sid", call_sid)
                .single()
                .execute()
            )
            return res.data
        except Exception:
            return None

    async def get_call_by_el_conversation_id(self, conversation_id: str) -> Optional[dict]:
        res = await (
            self._db.table("calls")
            .select("*")
            .eq("elevenlabs_conversation_id", conversation_id)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    # ──────────────────────────────────────────────────────────────────────────
    # CLAIMS
    # ──────────────────────────────────────────────────────────────────────────

    async def create_claim(self, payload: dict) -> str:
        """Insert FNOL claim. Returns the UUID."""
        res = await self._db.table("claims").insert(payload).execute()
        return res.data[0]["id"]

    async def get_claim_by_call_id(self, call_id: str) -> Optional[dict]:
        res = await (
            self._db.table("claims")
            .select("*")
            .eq("call_id", call_id)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    async def update_claim_status(self, claim_id: str, status: str) -> None:
        await (
            self._db.table("claims")
            .update({"status": status})
            .eq("id", claim_id)
            .execute()
        )

    async def approve_claim(self, claim_id: str, approved_by: str) -> Optional[dict]:
        res = await (
            self._db.table("claims")
            .update(
                {
                    "status": "processing",
                    "approved_by": approved_by,
                    "approved_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            .eq("id", claim_id)
            .execute()
        )
        return res.data[0] if res.data else None

    async def get_claims(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
        urgency: Optional[str] = None,
        fraud_score: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> list[dict]:
        q = self._db.table("claims").select("*").order("created_at", desc=True)
        if status:
            q = q.eq("status", status)
        if urgency:
            q = q.eq("urgency", urgency)
        if fraud_score:
            q = q.eq("fraud_score", fraud_score)
        if date_from:
            q = q.gte("created_at", date_from)
        if date_to:
            q = q.lte("created_at", date_to)
        res = await q.range(offset, offset + limit - 1).execute()
        return res.data

    async def get_claim(self, claim_id: str) -> Optional[dict]:
        try:
            res = await (
                self._db.table("claims")
                .select("*, calls(*)")
                .eq("id", claim_id)
                .single()
                .execute()
            )
            return res.data
        except Exception:
            return None

    async def check_prior_claims(
        self,
        policy_number: Optional[str] = None,
        license_plate: Optional[str] = None,
        months: int = 24,
    ) -> int:
        from datetime import timedelta

        cutoff = (datetime.now(timezone.utc) - timedelta(days=months * 30)).isoformat()
        q = self._db.table("claims").select("id", count="exact").gte("created_at", cutoff)
        if policy_number:
            q = q.eq("policy_number", policy_number)
        if license_plate:
            q = q.eq("license_plate", license_plate)
        res = await q.execute()
        return res.count or 0

    async def get_live_stats(self) -> dict:
        from datetime import date

        today = date.today().isoformat()
        active_res = await (
            self._db.table("calls").select("id", count="exact").eq("status", "in_progress").execute()
        )
        claims_today_res = await (
            self._db.table("claims").select("id", count="exact").gte("created_at", today).execute()
        )
        siu_res = await (
            self._db.table("claims")
            .select("id", count="exact")
            .eq("siu_referral", True)
            .eq("status", "opened")
            .execute()
        )
        critical_res = await (
            self._db.table("claims")
            .select("id", count="exact")
            .eq("urgency", "critical")
            .eq("status", "opened")
            .execute()
        )
        dur_res = await (
            self._db.table("calls")
            .select("duration_seconds")
            .eq("status", "completed")
            .limit(100)
            .execute()
        )
        durations = [r["duration_seconds"] for r in dur_res.data if r.get("duration_seconds")]
        avg_duration = int(sum(durations) / len(durations)) if durations else 0

        return {
            "active_calls": active_res.count or 0,
            "claims_today": claims_today_res.count or 0,
            "siu_flags_open": siu_res.count or 0,
            "critical_open": critical_res.count or 0,
            "avg_call_duration_seconds": avg_duration,
        }
