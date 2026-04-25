# ClaimCall — Build Plan

Status key: `[ ]` todo | `[x]` done | `[~]` in progress

---

## Step 1 — Project Docs
- [x] 1.1 CLAUDE.md
- [x] 1.2 PLAN.md

## Step 2 — config.py + .env.example
- [x] 2.1 pydantic-settings BaseSettings with all env groups
- [x] 2.2 get_settings() with @lru_cache
- [x] 2.3 .env.example with all keys + descriptions
- [x] 2.4 Test: import and assert supabase_url ✅

## Step 3 — sql/schema.sql
- [x] 3.1 calls table
- [x] 3.2 transcripts table
- [x] 3.3 claims table (80+ FNOL fields)
- [x] 3.4 Indexes
- [x] 3.5 updated_at trigger
- [x] 3.6 RLS enabled
- [ ] ⚠️  RUN IN SUPABASE: Supabase Dashboard → SQL Editor → paste sql/schema.sql → Run

## Step 4 — models/
- [x] 4.1 models/call.py — CallCreate, CallUpdate, CallResponse
- [x] 4.2 models/claim.py — ClaimCreate, ClaimResponse, FNOLExtraction, enums
- [x] 4.3 Test: validate enum rejection ✅

## Step 5 — services/audio.py
- [x] 5.1 numpy G.711 u-law codec
- [x] 5.2 base64 helpers
- [x] 5.3 mulaw_base64_to_pcm16_base64 (Twilio→EL pipeline)
- [x] 5.4 enhance_with_aicoustics (executor + timeout + fallback)
- [x] 5.5 apply_telephone_bandpass (Butterworth 300-3400Hz, cached)
- [x] 5.6 elevenlabs_audio_to_twilio_payload (EL→Twilio pipeline)
- [x] 5.7 TEST: mulaw round trip ✅
- [x] 5.8 TEST: bandpass filter output shape ✅

## Step 6 — services/supabase_client.py
- [x] 6.1 AsyncClient init
- [x] 6.2 create_call, update_call_stream_sid, complete_call, save_transcript_chunk
- [x] 6.3 create_claim, update_claim_status, approve_claim
- [x] 6.4 get_calls, get_call, get_claims, get_claim, check_prior_claims, get_live_stats
- [x] 6.5 ping()
- [x] 6.6 TEST: 17/17 integration tests passed ✅

## Step 7 — services/elevenlabs.py ✅
## Step 8 — services/twilio_client.py ✅
## Step 9 — services/claim_processor.py ✅ (all tests passed)
## Step 10 — websocket/relay.py ✅ (all tests passed)

## Step 11 — routers/twilio.py ✅
## Step 12 — routers/webhooks.py ✅
## Step 13 — routers/calls.py + routers/claims.py ✅
## Step 14 — routers/health.py ✅
## Step 15 — main.py ✅ (imports OK, TwiML route tested)

## Step 16 — static/index.html ✅
## Step 17 — Docker + Nginx ✅
## Step 18 — requirements.txt ✅

## Step 19 — README.md
- [ ] 19.1 Hetzner deploy + Twilio/EL config + schema setup + E2E test

## Step 20 — Full E2E Test (BLOCKED — app not deployed to Hetzner yet)

### What's done ✅
- Schema applied in Supabase (17/17 integration tests pass)
- All 95 unit tests pass
- Twilio webhook configured → +493042431626 → https://claimcall.eliteprojects.uk/incoming-call
- Hetzner server online (default nginx responding at claimcall.eliteprojects.uk)

### What's blocking ❌
Hetzner still serves default nginx page — our Docker Compose stack not deployed yet.

### Deploy steps (run on Hetzner via SSH)
```bash
# 1. SSH into Hetzner
ssh root@<HETZNER_IP>

# 2. Install Docker + Docker Compose
apt update && apt install -y docker.io docker-compose-plugin
systemctl enable --now docker

# 3. Clone repo
git clone https://github.com/0xk4g3/Bigberlin-hackathon.git /app/claimcall
cd /app/claimcall/backend

# 4. Copy .env (or create it with the same values as local)
nano .env   # paste contents

# 5. Get SSL cert (before starting nginx)
apt install -y certbot
certbot certonly --standalone -d claimcall.eliteprojects.uk
# → certs at /etc/letsencrypt/live/claimcall.eliteprojects.uk/

# 6. Start stack
docker compose up -d --build

# 7. Verify
curl -s https://claimcall.eliteprojects.uk/health
# Expected: {"status": "ok", "supabase": true, ...}
```

### E2E checklist (once deployed)
- [ ] 20.1 `curl https://claimcall.eliteprojects.uk/health` → `{"status":"ok","supabase":true}`
- [ ] 20.2 Call +493042431626 → Sophie answers → call row appears in Supabase `calls` table
- [ ] 20.3 Hang up → ElevenLabs fires webhook → `claims` row created with FNOL data
- [ ] 20.4 `POST /api/claims/{id}/approve` → status=processing, caller receives SMS

---

## ⚠️ Pre-production Checklist
- [x] schema.sql applied in Supabase
- [x] SUPABASE_SERVICE_KEY is service_role JWT ✅
- [x] Twilio webhook set to https://claimcall.eliteprojects.uk/incoming-call ✅
- [ ] Docker stack deployed on Hetzner
- [ ] Let's Encrypt SSL cert obtained on Hetzner
- [ ] ElevenLabs webhook URL set to https://claimcall.eliteprojects.uk/webhook/call-complete
- [ ] TWILIO_VALIDATE_REQUESTS=true in production .env
