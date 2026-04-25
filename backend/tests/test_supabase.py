"""
Integration tests for services/supabase_client.py.
Hits the real Supabase database — requires schema.sql to be applied.
Uses CA_PYTEST_* call_sid prefix and cleans up after each test.
"""

import pytest
import pytest_asyncio

from config import get_settings
from services.supabase_client import SupabaseService


@pytest_asyncio.fixture
async def svc():
    return await SupabaseService.create(get_settings())


async def _wipe_pytest_rows(svc):
    calls_res = await svc._db.table("calls").select("id").like("call_sid", "CA_PYTEST_%").execute()
    ids = [r["id"] for r in calls_res.data]
    if ids:
        for cid in ids:
            await svc._db.table("claims").delete().eq("call_id", cid).execute()
    await svc._db.table("calls").delete().like("call_sid", "CA_PYTEST_%").execute()


@pytest_asyncio.fixture(autouse=True)
async def cleanup(svc):
    await _wipe_pytest_rows(svc)
    yield
    await _wipe_pytest_rows(svc)


class TestPing:
    @pytest.mark.asyncio
    async def test_ping_returns_true(self, svc):
        ok = await svc.ping()
        assert ok is True


class TestCalls:
    @pytest.mark.asyncio
    async def test_create_call_returns_uuid(self, svc):
        cid = await svc.create_call("CA_PYTEST_001", "+4917612345", "+49800123")
        assert cid and len(cid) == 36  # UUID format

    @pytest.mark.asyncio
    async def test_get_call_by_sid(self, svc):
        await svc.create_call("CA_PYTEST_002", "+4917699999", "+49800456")
        call = await svc.get_call("CA_PYTEST_002")
        assert call is not None
        assert call["call_sid"] == "CA_PYTEST_002"
        assert call["from_number"] == "+4917699999"
        assert call["status"] == "in_progress"

    @pytest.mark.asyncio
    async def test_update_stream_sid(self, svc):
        await svc.create_call("CA_PYTEST_003", "+491761", "+49800")
        await svc.update_call_stream_sid("CA_PYTEST_003", "MZ_TEST_STREAM")
        call = await svc.get_call("CA_PYTEST_003")
        assert call["stream_sid"] == "MZ_TEST_STREAM"

    @pytest.mark.asyncio
    async def test_complete_call(self, svc):
        await svc.create_call("CA_PYTEST_004", "+491762", "+49800")
        transcript = [
            {"speaker": "agent", "text": "Hello"},
            {"speaker": "caller", "text": "I had an accident"},
        ]
        await svc.complete_call(
            call_sid="CA_PYTEST_004",
            duration_seconds=120,
            transcript=transcript,
            elevenlabs_conversation_id="EL-CONV-TEST",
        )
        call = await svc.get_call("CA_PYTEST_004")
        assert call["status"] == "completed"
        assert call["duration_seconds"] == 120
        assert call["elevenlabs_conversation_id"] == "EL-CONV-TEST"
        assert len(call["transcript"]) == 2

    @pytest.mark.asyncio
    async def test_save_transcript_chunk(self, svc):
        call_id = await svc.create_call("CA_PYTEST_005", "+491763", "+49800")
        await svc.save_transcript_chunk(call_id, "caller", "My car was hit", 1500)
        await svc.save_transcript_chunk(call_id, "agent", "Are you safe?", 2000)
        # Retrieve via get_call (includes transcripts via join)
        call = await svc.get_call("CA_PYTEST_005")
        chunks = call.get("transcripts", [])
        assert len(chunks) == 2
        speakers = {c["speaker"] for c in chunks}
        assert "caller" in speakers
        assert "agent" in speakers

    @pytest.mark.asyncio
    async def test_get_calls_list(self, svc):
        await svc.create_call("CA_PYTEST_006", "+491764", "+49800")
        calls = await svc.get_calls(limit=10)
        assert isinstance(calls, list)
        sids = [c["call_sid"] for c in calls]
        assert "CA_PYTEST_006" in sids

    @pytest.mark.asyncio
    async def test_get_calls_status_filter(self, svc):
        await svc.create_call("CA_PYTEST_007", "+491765", "+49800")
        active = await svc.get_calls(status="in_progress")
        assert all(c["status"] == "in_progress" for c in active)

    @pytest.mark.asyncio
    async def test_get_nonexistent_call_returns_none(self, svc):
        result = await svc.get_call("CA_DOES_NOT_EXIST_XYZ")
        assert result is None


class TestClaims:
    @pytest_asyncio.fixture
    async def call_id(self, svc, request):
        # Use test name to get unique call_sid per test
        sid = f"CA_PYTEST_{request.node.name[:20].upper().replace(' ', '_')}"
        cid = await svc.create_call(sid, "+491766", "+49800")
        return cid

    @pytest.mark.asyncio
    async def test_create_claim_returns_uuid(self, svc, call_id):
        claim_id = await svc.create_claim({
            "call_id": call_id,
            "urgency": "moderate",
            "fraud_score": "low",
            "assessor_sla_hours": 48,
        })
        assert claim_id and len(claim_id) == 36

    @pytest.mark.asyncio
    async def test_get_claim_by_call_id(self, svc, call_id):
        await svc.create_claim({
            "call_id": call_id,
            "urgency": "high",
            "fraud_score": "medium",
            "assessor_sla_hours": 24,
            "policyholder_name": "Hans Müller",
        })
        claim = await svc.get_claim_by_call_id(call_id)
        assert claim is not None
        assert claim["policyholder_name"] == "Hans Müller"
        assert claim["urgency"] == "high"

    @pytest.mark.asyncio
    async def test_approve_claim(self, svc, call_id):
        claim_id = await svc.create_claim({
            "call_id": call_id,
            "urgency": "moderate",
            "fraud_score": "low",
            "assessor_sla_hours": 48,
        })
        updated = await svc.approve_claim(claim_id, "test_operator")
        assert updated["status"] == "processing"
        assert updated["approved_by"] == "test_operator"
        assert updated["approved_at"] is not None

    @pytest.mark.asyncio
    async def test_get_claims_list(self, svc, call_id):
        await svc.create_claim({
            "call_id": call_id,
            "urgency": "routine",
            "fraud_score": "low",
            "assessor_sla_hours": 72,
        })
        claims = await svc.get_claims(limit=10)
        assert isinstance(claims, list)
        assert len(claims) >= 1

    @pytest.mark.asyncio
    async def test_get_claims_urgency_filter(self, svc, call_id):
        await svc.create_claim({
            "call_id": call_id,
            "urgency": "critical",
            "fraud_score": "high",
            "siu_referral": True,
            "assessor_sla_hours": 4,
        })
        critical = await svc.get_claims(urgency="critical")
        assert all(c["urgency"] == "critical" for c in critical)

    @pytest.mark.asyncio
    async def test_check_prior_claims_count(self, svc, call_id):
        await svc.create_claim({
            "call_id": call_id,
            "urgency": "moderate",
            "fraud_score": "low",
            "assessor_sla_hours": 48,
            "policy_number": "TEST-POLICY-9999",
        })
        count = await svc.check_prior_claims(policy_number="TEST-POLICY-9999")
        assert count >= 1

    @pytest.mark.asyncio
    async def test_get_nonexistent_claim_returns_none(self, svc):
        result = await svc.get_claim("00000000-0000-0000-0000-000000000000")
        assert result is None


class TestLiveStats:
    @pytest.mark.asyncio
    async def test_live_stats_structure(self, svc):
        stats = await svc.get_live_stats()
        assert "active_calls" in stats
        assert "claims_today" in stats
        assert "siu_flags_open" in stats
        assert "critical_open" in stats
        assert "avg_call_duration_seconds" in stats
        assert all(isinstance(v, int) for v in stats.values())
