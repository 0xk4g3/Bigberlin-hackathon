# ClaimCall Backend

AI voice agent for insurance FNOL (First Notice of Loss) intake. Inbound calls via Twilio are cleaned by AI-Coustics, handled by ElevenLabs conversational AI (Sophie), and written directly to Supabase. No middleware, no n8n. One FastAPI process on Hetzner CX21 behind Nginx.

## Tech Stack

- Python 3.11+, FastAPI (async throughout)
- WebSockets: websockets + FastAPI WebSocket
- Phone: Twilio inbound TwiML + Media Streams
- Audio cleaning: AI-Coustics SDK (`aic-sdk`, import as `aic_sdk`)
- AI Voice: ElevenLabs Conversational AI WebSocket (manual mode)
- Database: Supabase (supabase-py async, service key, direct writes)
- Audio DSP: numpy (G.711 u-law codec) + scipy (Butterworth bandpass)
- HTTP client: httpx (async)
- Config: pydantic-settings
- Server: Uvicorn behind Nginx (SSL + WebSocket proxy)
- Containers: Docker + Docker Compose

## Build Order

1. config.py + .env.example
2. sql/schema.sql
3. models/call.py + models/claim.py
4. services/audio.py — TEST: mulaw round trip
5. services/supabase_client.py — TEST: insert + query
6. services/elevenlabs.py
7. services/twilio_client.py
8. services/claim_processor.py
9. websocket/relay.py — TEST: fake Twilio WS message
10. routers/twilio.py
11. routers/webhooks.py
12. routers/calls.py + routers/claims.py
13. routers/health.py
14. main.py
15. static/index.html
16. Dockerfile + docker-compose.yml + nginx.conf
17. requirements.txt
18. README.md

## Environment Variables

```
HOST, PORT, APP_HOST, ENVIRONMENT, LOG_LEVEL
TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER, TWILIO_VALIDATE_REQUESTS
ELEVENLABS_API_KEY, ELEVENLABS_AGENT_ID, ELEVENLABS_WEBHOOK_SECRET
AICOUSTICS_API_KEY (aliased as AIC_SDK_LICENSE in aic-sdk), AICOUSTICS_ENABLED
SUPABASE_URL, SUPABASE_SERVICE_KEY (must be service_role JWT, NOT anon)
APPLY_TELEPHONE_FILTER, TELEPHONE_FILTER_ORDER
CLAIMS_MANAGER_PHONE, CLAIMS_MANAGER_EMAIL
```

## Critical Notes

- `audioop` removed in Python 3.13 — use numpy G.711 implementation in audio.py
- AI-Coustics model `quail-vf-2.1-l-16khz` requires 16kHz input — upsample from 8kHz before enhancing
- AI-Coustics processor must be initialized once at startup (`app.state.aic_processor`)
- ElevenLabs ping must be ponged within 5 seconds or connection drops
- Supabase SUPABASE_SERVICE_KEY must be service_role (not anon) — startup assertion checks this
- Never `await` in the EL receive loop except for the pong — use `create_task` for DB writes
- relay.py uses `asyncio.wait(FIRST_COMPLETED)` not `gather` for cleaner shutdown

## Session Goal

Build the complete production-ready backend from scratch following the build order above, with a passing test after each file before moving to the next.
