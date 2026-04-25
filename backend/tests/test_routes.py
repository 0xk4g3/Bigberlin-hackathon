"""Tests for FastAPI routes — TwiML, webhooks, REST API."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient


# ─────────────────────────────────────────────────────────────────────────────
# App fixture with mocked services
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def app_client():
    mock_sb = AsyncMock()
    mock_sb.ping = AsyncMock(return_value=True)
    mock_sb.get_calls = AsyncMock(return_value=[])
    mock_sb.get_call = AsyncMock(return_value=None)
    mock_sb.get_claims = AsyncMock(return_value=[])
    mock_sb.get_claim = AsyncMock(return_value=None)
    mock_sb.get_live_stats = AsyncMock(return_value={
        "active_calls": 2, "claims_today": 5,
        "siu_flags_open": 1, "critical_open": 0,
        "avg_call_duration_seconds": 240,
    })
    mock_sb.get_call_by_el_conversation_id = AsyncMock(return_value=None)
    mock_sb.get_claim_by_call_id = AsyncMock(return_value=None)
    mock_sb.save_transcript_chunk = AsyncMock()

    mock_tw = AsyncMock()
    mock_tw.send_sms = AsyncMock()

    # Patch environment=development to skip EL webhook signature validation
    from config import get_settings
    settings = get_settings()
    original_env = settings.environment
    settings.__dict__["environment"] = "development"

    with patch("services.supabase_client.create_client", new_callable=AsyncMock) as mock_create, \
         patch("services.twilio_client.TwilioSDKClient"):
        mock_create.return_value = MagicMock()

        import main
        # Override app.state directly
        main.app.state.supabase = mock_sb
        main.app.state.twilio = mock_tw
        main.app.state.aic_processor = None

        client = TestClient(main.app, raise_server_exceptions=False)
        client._mock_sb = mock_sb
        client._mock_tw = mock_tw
        yield client

    settings.__dict__["environment"] = original_env


# ─────────────────────────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────────────────────────

class TestHealthRoute:
    def test_health_returns_200(self, app_client):
        r = app_client.get("/health")
        assert r.status_code == 200

    def test_health_contains_status(self, app_client):
        data = app_client.get("/health").json()
        assert "status" in data
        assert "supabase" in data
        assert "timestamp" in data
        assert "version" in data


# ─────────────────────────────────────────────────────────────────────────────
# Twilio TwiML
# ─────────────────────────────────────────────────────────────────────────────

class TestTwilioRoute:
    def test_incoming_call_returns_xml(self, app_client):
        r = app_client.post("/incoming-call", data={"CallSid": "CA123", "From": "+4917612345"})
        assert r.status_code == 200
        assert "application/xml" in r.headers["content-type"]

    def test_twiml_contains_stream(self, app_client):
        r = app_client.post("/incoming-call", data={"CallSid": "CA123"})
        assert b"<Stream" in r.content

    def test_twiml_no_say_before_connect(self, app_client):
        r = app_client.post("/incoming-call", data={"CallSid": "CA123"})
        # <Say> before <Connect> adds silence — must not be present
        assert b"<Say>" not in r.content

    def test_twiml_has_connect(self, app_client):
        r = app_client.post("/incoming-call", data={"CallSid": "CA123"})
        assert b"<Connect>" in r.content

    def test_stream_url_uses_wss(self, app_client):
        r = app_client.post("/incoming-call", data={"CallSid": "CA123"})
        assert b"wss://" in r.content


# ─────────────────────────────────────────────────────────────────────────────
# Webhooks
# ─────────────────────────────────────────────────────────────────────────────

class TestWebhookRoutes:
    def test_call_complete_unknown_conversation_returns_200(self, app_client):
        payload = json.dumps({
            "conversation_id": "EL-UNKNOWN",
            "transcript": [],
            "data_collection_results": {},
        })
        r = app_client.post(
            "/webhook/call-complete",
            content=payload,
            headers={"content-type": "application/json"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "call_not_found"

    def test_transcript_webhook_unknown_conversation(self, app_client):
        payload = json.dumps({
            "conversation_id": "EL-UNKNOWN",
            "role": "caller",
            "message": "Hello",
        })
        r = app_client.post(
            "/webhook/transcript",
            content=payload,
            headers={"content-type": "application/json"},
        )
        assert r.status_code == 200

    def test_call_complete_bad_json_returns_400(self, app_client):
        r = app_client.post(
            "/webhook/call-complete",
            content="not json",
            headers={"content-type": "application/json"},
        )
        assert r.status_code == 400

    def test_transcript_bad_json_returns_400(self, app_client):
        r = app_client.post(
            "/webhook/transcript",
            content="not json",
            headers={"content-type": "application/json"},
        )
        assert r.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# Calls API
# ─────────────────────────────────────────────────────────────────────────────

class TestCallsAPI:
    def test_list_calls_returns_200(self, app_client):
        r = app_client.get("/api/calls")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_list_calls_accepts_status_filter(self, app_client):
        r = app_client.get("/api/calls?status=in_progress")
        assert r.status_code == 200

    def test_get_call_not_found_returns_404(self, app_client):
        r = app_client.get("/api/calls/CA_DOES_NOT_EXIST")
        assert r.status_code == 404

    def test_list_calls_limit_param(self, app_client):
        r = app_client.get("/api/calls?limit=10&offset=0")
        assert r.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# Claims API
# ─────────────────────────────────────────────────────────────────────────────

class TestClaimsAPI:
    def test_list_claims_returns_200(self, app_client):
        r = app_client.get("/api/claims")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_list_claims_accepts_filters(self, app_client):
        r = app_client.get("/api/claims?urgency=high&fraud_score=low&status=opened")
        assert r.status_code == 200

    def test_get_claim_not_found_returns_404(self, app_client):
        r = app_client.get("/api/claims/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404

    def test_stats_endpoint_returns_expected_keys(self, app_client):
        r = app_client.get("/api/claims/stats")
        assert r.status_code == 200
        data = r.json()
        assert "active_calls" in data
        assert "claims_today" in data
        assert "siu_flags_open" in data

    def test_approve_nonexistent_claim_returns_404(self, app_client):
        r = app_client.post(
            "/api/claims/00000000-0000-0000-0000-000000000000/approve",
            json={"approved_by": "operator"},
        )
        assert r.status_code == 404
