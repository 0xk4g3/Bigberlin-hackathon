# ClaimCall — Testing Guide

## Prerequisites

```bash
# Create venv and install deps (first time only)
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install pytest pytest-asyncio

# .env must be populated with real credentials for integration tests
```

---

## 1. Unit Tests (no network, no DB)

Fastest. Run after every code change.

```bash
# All unit tests
.venv/bin/python -m pytest tests/test_audio.py tests/test_claim_processor.py tests/test_relay.py tests/test_routes.py -v

# Individual suites
.venv/bin/python -m pytest tests/test_audio.py -v          # G.711 codec, bandpass filter
.venv/bin/python -m pytest tests/test_claim_processor.py -v # FNOL extraction, urgency, fraud
.venv/bin/python -m pytest tests/test_relay.py -v          # WebSocket relay logic (mocked)
.venv/bin/python -m pytest tests/test_routes.py -v         # FastAPI routes (mocked services)
```

Expected: **95 passed**

---

## 2. Integration Tests (hits real Supabase)

Requires `.env` with valid `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` (service_role).
Creates rows with prefix `CA_PYTEST_*` and cleans up after each test.

```bash
.venv/bin/python -m pytest tests/test_supabase.py -v
```

Expected: **17 passed**

What it tests:
- `ping()` — DB connection alive
- `create_call` / `get_call` / `update_*` / `complete_call`
- `save_transcript_chunk` — transcript rows appear in `get_call` join
- `create_claim` / `get_claim_by_call_id` / `approve_claim`
- `get_claims` with urgency/status filters
- `check_prior_claims` — count by policy number
- `get_live_stats` — active calls, claims today, SIU flags

---

## 3. Makefile Smoke Tests

Quick sanity checks for audio pipeline, Supabase write, and relay logic:

```bash
make test-audio      # mulaw round-trip + bandpass filter
make test-supabase   # insert + query + delete one call row
make test-relay      # full relay run with fake Twilio WS events
make test-all        # all three above
```

---

## 4. Health Check (Docker running)

```bash
# Via Makefile
make health

# Raw
curl -s http://localhost:8000/health | python3 -m json.tool
```

Expected response:
```json
{
  "status": "ok",
  "supabase": true,
  "timestamp": "2026-...",
  "version": "1.0.0"
}
```

If `supabase: false` → check `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` in `.env`.

---

## 5. Manual API Tests (Docker running)

### List calls
```bash
curl -s http://localhost:8000/api/calls | python3 -m json.tool
curl -s "http://localhost:8000/api/calls?status=in_progress" | python3 -m json.tool
```

### List claims
```bash
curl -s http://localhost:8000/api/claims | python3 -m json.tool
curl -s "http://localhost:8000/api/claims?urgency=critical" | python3 -m json.tool
```

### Live stats (dashboard data)
```bash
curl -s http://localhost:8000/api/claims/stats | python3 -m json.tool
```

### Simulate incoming call (TwiML response)
```bash
curl -s -X POST http://localhost:8000/incoming-call \
  -d "CallSid=CA_TEST_001&From=%2B4917612345&To=%2B493042431626"
```
Expected: XML response containing `<Connect><Stream` and `wss://`

### Simulate ElevenLabs post-call webhook
```bash
curl -s -X POST http://localhost:8000/webhook/call-complete \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "EL-TEST-999",
    "transcript": [
      {"role": "agent", "message": "Hello, this is Sophie"},
      {"role": "user", "message": "I had a collision on the A6"}
    ],
    "data_collection_results": {
      "policyholder_name": {"value": "Hans Müller"},
      "loss_type": {"value": "moving_collision"}
    }
  }'
```
Expected (dev mode, no sig validation): `{"status": "call_not_found"}` if no matching conversation_id in DB, or claim created if it matches a real call.

---

## 6. WebSocket Test (local, no Twilio)

Tests the `/twilio-stream` WebSocket endpoint directly:

```bash
# Install wscat
npm install -g wscat

# Connect
wscat -c ws://localhost:8000/twilio-stream

# Paste these messages one by one:
{"event":"connected"}
{"event":"start","start":{"streamSid":"MZ_TEST","callSid":"CA_WS_TEST","customParameters":{"from":"+4917600000","to":"+493042431626"}}}
{"event":"stop"}
```

Watch logs: `make logs` — should see:
```
Twilio stream connected for CA_WS_TEST
Stream started: call_sid=CA_WS_TEST stream_sid=MZ_TEST db_id=<uuid>
Call CA_WS_TEST completed: duration=...
```

---

## 7. Real End-to-End Test (live call)

**Requires:** Docker running, Nginx + SSL up on Hetzner, Twilio webhook configured.

1. Call `+493042431626` from any phone
2. Sophie (ElevenLabs agent) answers and takes FNOL details
3. Hang up
4. Check DB:

```bash
curl -s "http://localhost:8000/api/calls?limit=1" | python3 -m json.tool
curl -s "http://localhost:8000/api/claims?limit=1" | python3 -m json.tool
```

5. Check SMS — caller receives claim reference SMS after hangup
6. Approve claim:

```bash
CLAIM_ID="<id from step 4>"
curl -s -X POST "http://localhost:8000/api/claims/$CLAIM_ID/approve" \
  -H "Content-Type: application/json" \
  -d '{"approved_by": "test_operator"}' | python3 -m json.tool
```

Expected: `{"status": "processing", "approved_by": "test_operator", ...}`

---

## 8. Twilio Webhook Validation Test

Verifies Twilio signature checking works in production mode:

```bash
# Without valid signature — should return 403
curl -s -X POST https://claimcall.eliteprojects.uk/incoming-call \
  -d "CallSid=CA_FAKE" \
  -w "\nHTTP %{http_code}\n"
```

Expected: `HTTP 403` (signature missing/invalid)

To test with a valid signature, use Twilio's [webhook tester](https://console.twilio.com/us1/develop/phone-numbers/manage/incoming) or call the real number.

---

## 9. Docker Container Checks

```bash
# Container status
make ps

# Follow live logs
make logs

# Check nginx
make logs-nginx

# Enter container shell
make shell
# Inside: python -c "from services.elevenlabs import ElevenLabsClient; print('OK')"
# Inside: python -c "from config import get_settings; s=get_settings(); print(s.twilio_phone_number)"

# Rebuild from scratch (after code changes)
make rebuild
```

---

## 10. Fraud + Urgency Scoring (unit, no network)

```bash
.venv/bin/python -c "
from services.claim_processor import ClaimProcessor
p = ClaimProcessor()

# Critical urgency — drunk driver hit and run
transcript = [{'speaker': 'caller', 'text': 'The drunk driver fled the scene'}]
fnol = p.extract_fnol(transcript, {}, {'from_number': '+491', 'call_id': 'x'})
urgency, reason = p.score_urgency(fnol)
print(f'Urgency: {urgency} ({reason})')  # → critical

# High fraud — late reporting + prior claims
fnol.report_delay_hours = 96
score, signals = p.score_fraud(fnol, prior_claims=2)
print(f'Fraud: {score} | Signals: {signals}')  # → high

# SLA
print(p.calculate_assessor_sla('critical'))   # → 4
print(p.calculate_assessor_sla('high'))       # → 24
print(p.calculate_assessor_sla('moderate'))   # → 48
print(p.calculate_assessor_sla('routine'))    # → 72
"
```

---

## Quick Reference

| Test | Command | Speed | Needs network |
|---|---|---|---|
| All unit tests | `pytest tests/ -v` (excl. supabase) | ~3s | No |
| Supabase integration | `pytest tests/test_supabase.py -v` | ~8s | Supabase only |
| Audio smoke | `make test-audio` | <1s | No |
| Relay smoke | `make test-relay` | <1s | No |
| Health check | `make health` | <1s | Supabase |
| API manual | `curl` commands above | instant | Docker |
| WebSocket | `wscat` above | manual | Docker + EL |
| Full E2E | Real phone call | ~2min | Everything |
