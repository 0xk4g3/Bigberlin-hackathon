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
- [ ] 6.6 TEST: insert → query → assert → delete (BLOCKED — schema.sql not yet run in Supabase)

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

## Step 20 — Full E2E Test (BLOCKED until schema.sql is run)
- [ ] 20.1 Inbound call → calls row exists
- [ ] 20.2 Transcript webhook → transcripts rows exist
- [ ] 20.3 Post-call webhook → claims row with FNOL data
- [ ] 20.4 Approve → status=processing, SMS sent

---

## ⚠️ Action Required

1. **Run schema.sql in Supabase:**
   - Supabase Dashboard → SQL Editor
   - Paste contents of `sql/schema.sql`
   - Click Run

2. **Verify SUPABASE_SERVICE_KEY** is the `service_role` key (not anon)
   - Supabase Dashboard → Project Settings → API → `service_role` key

3. **Rotate ELEVENLABS_WEBHOOK_SECRET** before production

After schema is applied, run:
```bash
.venv/bin/python -c "
import asyncio
from config import get_settings
from services.supabase_client import SupabaseService

async def test():
    svc = await SupabaseService.create(get_settings())
    assert await svc.ping(), 'ping failed'
    id = await svc.create_call('CA_TEST', '+49123', '+49456')
    call = await svc.get_call('CA_TEST')
    assert call['call_sid'] == 'CA_TEST'
    print('Supabase OK, id=' + id)

asyncio.run(test())
"
```
