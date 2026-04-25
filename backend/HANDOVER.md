# ClaimCall — Project Handover

## What This Is

AI voice agent for insurance FNOL (First Notice of Loss) intake.
Caller dials a German number → ElevenLabs AI agent (Sophie) handles the conversation → structured claim written to Supabase → SMS sent to caller with claim reference.

**Stack:** Python 3.11, FastAPI, Uvicorn, Twilio Media Streams (WebSocket), ElevenLabs Conversational AI, AI-Coustics audio enhancement, Supabase (Postgres), Nginx, Docker Compose on Hetzner.

**Repo:** https://github.com/0xk4g3/Bigberlin-hackathon  
**Backend folder:** `/backend`  
**Live domain:** https://claimcall.eliteprojects.uk  
**Phone number:** +493042431626 (German, Twilio)

---

## Credentials (in backend/.env on Hetzner at /root/Bigberlin-hackathon/backend/.env)

```
TWILIO_ACCOUNT_SID=AC0048a0d1121a939bbdc653916846aa87
TWILIO_API_KEY_SID=SK60ded18c3b03900c75ca98603be9003c
TWILIO_API_KEY_SECRET=brFLwRznJsi288QUZ3AgD4sDkQj4P0nX
TWILIO_PHONE_NUMBER=+493042431626

ELEVENLABS_API_KEY=sk_3a18c4e7f9694143ad17f6b770ede65795285a4756e2f11e
ELEVENLABS_AGENT_ID=agent_6701kq26aj5ef44sh459a7szjgy9
ELEVENLABS_WEBHOOK_SECRET=wsec_cad425d0c10c993159e5f040b38e1b9425620a2f4d7fe0013cb55cdfd4c03efa

SUPABASE_URL=https://gntptlsgtfepkxrchowr.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...  (service_role JWT)

AICOUSTICS_API_KEY=eyJ1c2VyIjoidXNlcl8z...  (base64 encoded)
AICOUSTICS_ENABLED=true

ENVIRONMENT=production
APP_HOST=https://claimcall.eliteprojects.uk
TWILIO_VALIDATE_REQUESTS=false   ← change to true before final production
```

---

## What Is 100% Done ✅

| Component | Status |
|---|---|
| `config.py` | Done — pydantic-settings, all env vars typed |
| `sql/schema.sql` | Done — **applied in Supabase**, 3 tables: calls, transcripts, claims |
| `models/call.py` + `models/claim.py` | Done — Pydantic v2 models, enums |
| `services/audio.py` | Done — G.711 mulaw codec (numpy), bandpass filter (scipy), AI-Coustics pipeline |
| `services/supabase_client.py` | Done — 17/17 integration tests pass against real DB |
| `services/elevenlabs.py` | Done — WebSocket client, send_audio, receive, pong |
| `services/twilio_client.py` | Done — API Key auth (not Auth Token), async SMS |
| `services/claim_processor.py` | Done — FNOL extraction, urgency scoring, fraud scoring, SLA |
| `websocket/relay.py` | Done — dual-task relay (Twilio↔EL), ping/pong, transcript, call complete |
| `routers/twilio.py` | Done — TwiML `/incoming-call`, WebSocket `/twilio-stream` |
| `routers/webhooks.py` | Done — `/webhook/call-complete`, `/webhook/transcript`, HMAC sig check |
| `routers/calls.py` | Done — `GET /api/calls`, `GET /api/calls/{sid}` |
| `routers/claims.py` | Done — `GET /api/claims`, `POST /api/claims/{id}/approve`, `GET /api/claims/stats` |
| `routers/health.py` | Done — `GET /health` with Supabase ping |
| `main.py` | Done — lifespan, service_role JWT check, all routers mounted |
| `static/index.html` | Done — operations dashboard, Tailwind CDN |
| `Dockerfile` | Done — python:3.11-slim, gcc/g++, uvicorn |
| `docker-compose.yml` | Done — claimcall + nginx services, healthcheck |
| `nginx.conf` | Done — SSL, WebSocket upgrade, proxy_read_timeout 3600s |
| `requirements.txt` | Done — all deps pinned |
| `Makefile` | Done — up, build, rebuild, logs, health, shell, test-* |
| Twilio webhook | Done — +493042431626 → https://claimcall.eliteprojects.uk/incoming-call |
| Tests | Done — 95 unit tests + 17 integration tests, all passing |

---

## Current Problem ❌ (Only Remaining Blocker)

**Nginx Docker container fails to start** with:
```
[emerg] host not found in upstream "claimcall:8000" in /etc/nginx/nginx.conf:7
```

**Root cause:** Nginx resolves the `claimcall` upstream hostname at startup before Docker's internal DNS is ready.

**Fix already applied in code** (not yet pulled on Hetzner):
- Removed `upstream` block from `nginx.conf`
- Added `resolver 127.0.0.11 valid=30s ipv6=off;` (Docker's internal DNS)
- Changed `proxy_pass http://claimcall;` to use a variable: `set $upstream http://claimcall:8000;` — forces runtime DNS resolution

**To apply fix on Hetzner:**
```bash
cd /root/Bigberlin-hackathon/backend
git pull
docker compose restart nginx
docker compose logs nginx | tail -5
# Should show NO [emerg] errors
docker compose ps
# backend-nginx-1 should show 0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
```

**Then verify:**
```bash
curl -s https://claimcall.eliteprojects.uk/health
# Expected: {"status":"ok","version":"1.0.0","supabase":"connected"}
```

---

## Current State on Hetzner Server

- `backend-claimcall-1` → **Up + Healthy** ✅ (app running, Supabase connected)
- `backend-nginx-1` → **Crash-looping** ❌ (DNS fix not pulled yet)
- SSL cert → **Exists** at `/etc/letsencrypt/live/claimcall.eliteprojects.uk/`
- Firewall (ufw) → **Inactive** (no blocking issue)
- System nginx → **Stopped + disabled** (was conflicting on port 80)

---

## After Nginx Is Fixed — Remaining Tasks

1. **Test the live endpoint:**
   ```bash
   curl -s https://claimcall.eliteprojects.uk/health
   curl -s https://claimcall.eliteprojects.uk/api/claims/stats
   ```

2. **Set ElevenLabs webhook URL** in ElevenLabs dashboard:
   - Post-call webhook: `https://claimcall.eliteprojects.uk/webhook/call-complete`
   - Transcript webhook: `https://claimcall.eliteprojects.uk/webhook/transcript`
   - Use secret: `wsec_cad425d0c10c993159e5f040b38e1b9425620a2f4d7fe0013cb55cdfd4c03efa`

3. **Enable Twilio request validation** (security):
   - Set `TWILIO_VALIDATE_REQUESTS=true` in `.env` on Hetzner
   - `docker compose restart claimcall`

4. **Call the number** (+493042431626) and verify:
   - Sophie answers
   - Call row appears in Supabase `calls` table
   - After hang up → `claims` row created
   - Caller receives SMS

---

## File Structure

```
backend/
├── main.py                      # FastAPI app, lifespan, startup checks
├── config.py                    # pydantic-settings, all env vars
├── requirements.txt
├── .env                         # NOT in git (gitignored)
├── .env.example                 # Template with all keys
├── Dockerfile
├── docker-compose.yml
├── nginx.conf                   # ← fix applied here (resolver + $upstream var)
├── Makefile
├── sql/schema.sql               # Applied in Supabase already
├── routers/
│   ├── twilio.py                # POST /incoming-call, WS /twilio-stream
│   ├── webhooks.py              # POST /webhook/call-complete, /webhook/transcript
│   ├── calls.py                 # GET /api/calls, /api/calls/{sid}
│   ├── claims.py                # GET /api/claims, POST /api/claims/{id}/approve
│   └── health.py                # GET /health
├── services/
│   ├── audio.py                 # G.711 mulaw codec, bandpass filter, AI-Coustics
│   ├── elevenlabs.py            # ElevenLabs WebSocket client
│   ├── supabase_client.py       # All DB operations
│   ├── twilio_client.py         # SMS via API Key auth
│   └── claim_processor.py       # FNOL extraction, urgency, fraud scoring
├── websocket/
│   └── relay.py                 # Core: Twilio ↔ AI-Coustics ↔ ElevenLabs
├── models/
│   ├── call.py
│   └── claim.py
├── static/index.html            # Operations dashboard
├── tests/
│   ├── test_audio.py            # 18 tests ✅
│   ├── test_claim_processor.py  # 26 tests ✅
│   ├── test_relay.py            # 17 tests ✅
│   ├── test_routes.py           # 17 tests ✅ (mocked)
│   └── test_supabase.py         # 17 tests ✅ (real DB)
├── scripts/
│   └── configure_twilio_webhook.py  # One-time: sets Twilio webhook URL
├── ARCHITECTURE.md              # Full system diagram
├── TESTING.md                   # All testing methods
└── PLAN.md                      # Build progress tracker
```

---

## Key Implementation Notes (for next AI)

- **Twilio auth**: Uses API Key SID + Secret (not Auth Token). `TwilioSDKClient(api_key_sid, api_key_secret, account_sid=account_sid)`
- **G.711**: `audioop` removed in Python 3.13 — codec implemented with numpy in `services/audio.py`
- **ElevenLabs ping**: Must pong within 5s. Handled BEFORE `stop_event` check in `relay.py`
- **DB writes in relay**: Always `asyncio.create_task()` — never `await` in audio path
- **Relay shutdown**: `asyncio.wait(FIRST_COMPLETED)` not `gather`
- **Supabase key**: Must be `service_role` JWT (not anon) — startup check in `main.py` warns if wrong
- **AI-Coustics**: Optional, graceful fallback. Currently commented out in `requirements.txt` due to Linux install issues. Enable by uncommenting `aic-sdk` and rebuilding.
- **nginx DNS fix**: `resolver 127.0.0.11` + `set $upstream` variable — required for Docker service name resolution at runtime
