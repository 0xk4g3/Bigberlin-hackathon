# ClaimCall — System Architecture

## Overview

AI voice agent for insurance FNOL (First Notice of Loss) intake.
Inbound calls via Twilio → audio cleaned by AI-Coustics → ElevenLabs AI (Sophie) handles conversation → claim written to Supabase.

---

## Infrastructure

```
                        INTERNET
                           │
                    ┌──────▼──────┐
                    │   Twilio    │  (+493042431626)
                    └──────┬──────┘
                           │ HTTPS POST /incoming-call
                           │ WSS  /twilio-stream  (mulaw G.711 audio)
                           │
              ┌────────────▼────────────┐
              │   Nginx (Hetzner CX21)  │
              │ claimcall.eliteprojects.uk
              │   :80  → redirect HTTPS │
              │   :443 SSL (Let's Encrypt)
              │   proxy_buffering off   │
              │   proxy_read_timeout 1h │
              │   tcp_nodelay on        │
              └────────────┬────────────┘
                           │ http://claimcall:8000
                           │
              ┌────────────▼────────────┐
              │   FastAPI (Uvicorn)     │
              │   Docker container      │
              └────────────────────────┘
```

---

## Call Flow (end-to-end)

```
Caller dials +493042431626
       │
       ▼
Twilio POST /incoming-call
       │  Returns TwiML:
       │  <Connect><Stream url="wss://claimcall.eliteprojects.uk/twilio-stream"/></Connect>
       │
       ▼
Twilio opens WebSocket → /twilio-stream
       │
       ▼
CallRelay.run()
  asyncio.wait(FIRST_COMPLETED) on two tasks:
  ┌─────────────────────────────────────────────────────┐
  │ Task A: Twilio → ElevenLabs                         │
  │   mulaw bytes → PCM16 (numpy G.711 decode)          │
  │   PCM16 8kHz → upsample 16kHz                       │
  │   AI-Coustics enhance (executor + 200ms timeout)    │
  │   downsample back to 8kHz                           │
  │   → ElevenLabs WebSocket (send_audio)               │
  ├─────────────────────────────────────────────────────┤
  │ Task B: ElevenLabs → Twilio                         │
  │   EL audio event (base64 PCM16)                     │
  │   Butterworth bandpass 300-3400Hz                   │
  │   PCM16 → mulaw (numpy G.711 encode)                │
  │   base64 → Twilio media event                       │
  ├─────────────────────────────────────────────────────┤
  │ EL events handled in Task B:                        │
  │   ping → pong (within 5s, always first)             │
  │   conversation_initiation_metadata → store conv_id  │
  │   agent_response → append to transcript             │
  │   user_transcript → append to transcript            │
  │   audio → forward to Twilio                         │
  └─────────────────────────────────────────────────────┘
       │
       ▼
Call ends (Twilio stop event or EL disconnect)
       │
_on_call_complete()
  ├── supabase.complete_call(duration, transcript)
  └── twilio_sms.send_sms(caller, "Claim ref: XXXXXXXX")
       │
       ▼
ElevenLabs fires POST /webhook/call-complete
  ├── HMAC-SHA256 signature verified
  ├── idempotency check (claim already exists?)
  ├── ClaimProcessor.build_claim_payload()
  │     ├── extract_fnol(transcript, collected_data)
  │     ├── score_urgency() → critical/high/moderate/routine
  │     ├── score_fraud()   → high/medium/low + signals
  │     └── calculate_assessor_sla()
  ├── supabase.create_claim(payload)
  └── if critical or SIU → SMS to claims manager
```

---

## Services

| Service | Role |
|---|---|
| Twilio | Inbound PSTN calls, Media Streams WebSocket, outbound SMS |
| ElevenLabs | Conversational AI agent (Sophie), post-call webhook |
| AI-Coustics | Real-time voice enhancement (background noise removal) |
| Supabase | Postgres DB — calls, transcripts, claims |
| Nginx | SSL termination, WebSocket proxy, HTTP→HTTPS redirect |

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/incoming-call` | Twilio webhook → returns TwiML |
| WS | `/twilio-stream` | Twilio Media Stream → CallRelay |
| POST | `/webhook/call-complete` | ElevenLabs post-call → FNOL + claim |
| POST | `/webhook/transcript` | ElevenLabs real-time transcript |
| GET | `/api/calls` | List calls (paginated, status filter) |
| GET | `/api/calls/{call_sid}` | Call detail + transcript + claim |
| GET | `/api/claims` | List claims (urgency/fraud/status filters) |
| GET | `/api/claims/{id}` | Claim detail + linked call |
| POST | `/api/claims/{id}/approve` | Approve claim, update status |
| GET | `/api/claims/stats` | Live dashboard stats |
| GET | `/health` | Health check (Supabase ping) |

---

## Database Schema

```
calls
  id (UUID PK)
  call_sid (TEXT UNIQUE)          ← Twilio call SID
  stream_sid (TEXT)
  elevenlabs_conversation_id
  from_number / to_number
  status: in_progress | completed | failed
  started_at / ended_at
  duration_seconds
  transcript (JSONB)

transcripts
  id, call_id (FK → calls), speaker, text, timestamp_ms

claims
  id (UUID PK)
  call_id (FK → calls)
  policyholder_name, phone, policy_number
  loss_type, incident_date, incident_location
  injuries_reported, hit_and_run, alcohol_drugs_involved
  police_on_scene, license_plate, other_party_*
  urgency: critical | high | moderate | routine
  fraud_score: high | medium | low
  fraud_signals (JSONB)
  siu_referral (BOOL)
  assessor_sla_hours
  status: opened | processing | closed
  approved_by / approved_at
  full_fnol_payload (JSONB)
```

---

## Dependency Injection

```
app.state.supabase      ← all routers via Depends(get_supabase)
app.state.twilio        ← all routers via Depends(get_twilio)
app.state.aic_processor ← initialized once at startup (model load is expensive)
relay.py                ← receives supabase + twilio via WS route
claim_processor         ← pure functions, no state
```

---

## Key Implementation Notes

- `audioop` removed in Python 3.13 — G.711 u-law codec implemented with numpy
- AI-Coustics model `quail-vf-2.1-l-16khz` requires 16kHz — upsample from 8kHz before enhancing
- ElevenLabs ping must be ponged within 5s — handled **before** stop_event check
- `asyncio.create_task()` for all DB writes in the audio path — never block with `await`
- `asyncio.wait(FIRST_COMPLETED)` not `gather` — clean shutdown when either side disconnects
- Supabase `SUPABASE_SERVICE_KEY` must be `service_role` JWT (not anon) — startup assertion checks this
