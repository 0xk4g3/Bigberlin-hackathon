# Big Berlin Hackathon — Team **noTime**

**INCA motor FNOL voice agent** — callers reach a natural-sounding phone assistant (**Klaus**) that takes a **first notice of loss (FNOL)** for traffic and vehicle damage. Audio is streamed in real time; after the call, structured claim fields are extracted for a live **operator dashboard**.

| | |
|--|--|
| **Repository** | [github.com/0xk4g3/Bigberlin-hackathon](https://github.com/0xk4g3/Bigberlin-hackathon) |
| **Team** | **noTime** |
| **Stack (production path)** | Python · Starlette · Uvicorn · Twilio Media Streams · ElevenLabs Conversational AI · OpenAI · Next.js |

---

## Table of contents

1. [What we built](#what-we-built)
2. [Why it matters](#why-it-matters)
3. [Architecture](#architecture)
4. [Tech stack](#tech-stack)
5. [Prerequisites](#prerequisites)
6. [Environment variables](#environment-variables)
7. [Local setup (hackathon demo)](#local-setup-hackathon-demo)
8. [Twilio configuration](#twilio-configuration)
9. [ElevenLabs agent](#elevenlabs-agent)
10. [Operator dashboard](#operator-dashboard)
11. [Optional paths](#optional-paths)
12. [Project structure](#project-structure)
13. [Troubleshooting](#troubleshooting)
14. [Sponsor tracks: Pioneer & Entire](#sponsor-tracks-pioneer--entire)

---

## What we built

- **Inbound voice**: A caller dials a **Twilio** German number; Twilio opens a **bidirectional media stream** (WebSocket) to our server.
- **AI conversation**: Our server bridges **μ-law 8 kHz** (Twilio) ↔ **PCM 16 kHz** (ElevenLabs) and talks to **ElevenLabs Conversational AI** over a secure WebSocket. The agent (**Klaus**) follows a strict **FNOL** script: safety, identity, policy/plate, incident facts, third parties, police, injuries, read-back, closure.
- **Human-like delivery**: System prompt and TTS tuning (ElevenLabs **v3 conversational**, expressive tags where supported) keep turns short and natural.
- **Post-call extraction**: When the call ends, **OpenAI** turns the transcript into structured JSON (names, plates, loss details, etc.) for downstream systems.
- **Live dashboard**: A **Next.js** app connects to the Python server over **`/ws`** and receives **`call_ended`** payloads with transcript + extracted fields for demo operators.

---

## Why it matters

Insurance FNOL by phone is high-stakes: callers may be stressed, on a motorway, or speaking **English or German**. This demo shows **low-latency streaming voice**, **guardrailed** intake (no “I’m a bot”), and **structured handoff** to humans or core systems — without replacing the claims handler, only front-loading consistent data capture.

---

## Architecture

```
                    ┌──────────────┐
                    │  Phone call  │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │    Twilio    │
                    │ Voice + <Connect><Stream> │
                    └──────┬───────┘
                           │  HTTPS POST /incoming-call  (TwiML)
                           │  WSS  /twilio  (mulaw JSON frames)
                           │
              ┌────────────▼────────────────┐
              │   Application server         │
              │   Starlette + Uvicorn        │
              │                              │
              │   ElevenLabsSession          │
              │   Twilio WS  ↔  ElevenLabs   │
              │   (resample + encode)       │
              └────────────┬────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
         ▼                 ▼                 ▼
  ┌──────────────┐ ┌──────────────┐ ┌─────────────────┐
  │ ElevenLabs   │ │ OpenAI       │ │ Next.js         │
  │ ConvAI       │ │ (post-call)  │ │ dashboard /ws   │
  │ STT+LLM+TTS  │ │ extraction   │ │ live tickets    │
  └──────────────┘ └──────────────┘ └─────────────────┘
```

### Audio flow (live call)

1. Caller speaks → Twilio encodes **8 kHz μ-law**, sends **base64** inside JSON `media` events on **`/twilio`**.
2. Server decodes μ-law → linear PCM, **resamples 8 kHz → 16 kHz**, base64-wraps as **`user_audio_chunk`** to ElevenLabs.
3. ElevenLabs returns agent audio as **binary PCM** and/or JSON **`audio`** events; server **resamples 16 kHz → 8 kHz**, **μ-law** encodes, sends Twilio **`media`** outbound frames.
4. On barge-in / interruption, server can send Twilio **`clear`** to flush queued outbound audio.

Caller uplink is started **in parallel** with the ElevenLabs handshake so the pipeline sees line audio early (avoids “answered but silent” during init).

---

## Tech stack

| Layer | Technology |
|--------|------------|
| HTTP / WebSocket server | **Python 3.12+**, **Starlette**, **Uvicorn** |
| Telephony | **Twilio** Programmable Voice, **Media Streams**, TwiML `<Connect><Stream>` |
| Voice AI | **ElevenLabs** Conversational AI WebSocket API (`wss://api.elevenlabs.io/v1/convai/...`) |
| Agent LLM (hosted in ElevenLabs) | **Google Gemini** (e.g. `gemini-2.5-flash` — set in agent sync) |
| Audio transcoding | **`audioop`** (stdlib): μ-law ↔ PCM, sample-rate conversion |
| WebSocket client to ElevenLabs | **`websockets`** |
| Structured extraction | **OpenAI** API (`openai` SDK), JSON mode |
| Dashboard | **Next.js 16**, **React 19**, **TypeScript**, **Tailwind CSS 4** |
| Config | **`python-dotenv`**, `.env` (never commit secrets) |

**Legacy / alternate path in repo:** `voice_agent/session.py` + **Deepgram Voice Agent** — useful reference; **`main.py` inbound telephony uses ElevenLabs** via `telephony/routes.py` → `voice_agent/elevenlabs_session.py`.

---

## Prerequisites

- **Python 3.12+**
- **Twilio** account + **phone number** + Account SID + (**Auth Token** *or* **API Key** + secret)
- **HTTPS public URL** for webhooks (e.g. **ngrok**) when running locally
- **ElevenLabs** API key + **ConvAI agent ID**
- **OpenAI** API key (for post-call extraction; dashboard fields stay sparse without it)
- **Node.js** (for `inca-dashboard` only)

`DEEPGRAM_API_KEY` is still **required** by `config.py` at import time (project constraint); use a valid Deepgram key even if the live call path is ElevenLabs-only, or relax that check in a fork.

---

## Environment variables

Copy **`.env.example`** → **`.env`** and fill in values.

| Variable | Required for | Description |
|----------|----------------|-------------|
| `DEEPGRAM_API_KEY` | App boot | Required by `config.py` today (Deepgram console). |
| `SERVER_HOST` / `SERVER_PORT` | Server bind | Default `0.0.0.0` / `8080` — match your ngrok target port. |
| `SERVER_EXTERNAL_URL` | Real Twilio calls | **HTTPS origin only** (no path), e.g. `https://xxxx.ngrok-free.app`. Used in TwiML for `wss://` stream host. |
| `WEBHOOK_SECRET` | Recommended | Long random token; webhook becomes `/incoming-call/<token>` and stream `/twilio/<token>`. |
| `TWILIO_ACCOUNT_SID` | Twilio API / validation | Account SID. |
| `TWILIO_AUTH_TOKEN` | Optional | If set, Twilio **signature validation** runs on `/incoming-call` (URL must match Twilio’s configured URL exactly). |
| `TWILIO_API_KEY_SID` / `TWILIO_API_KEY_SECRET` | Optional | Alternative to auth token for REST scripts. |
| `TWILIO_PHONE_NUMBER` | Docs / scripts | E.164, e.g. `+493075420726`. |
| `ELEVENLABS_API_KEY` | Live voice | ElevenLabs API key. |
| `ELEVENLABS_AGENT_ID` | Live voice | ConvAI agent ID. |
| `ELEVENLABS_VOICE_ID` | TTS voice | Default in sync: **Klaus** `Jvf6TAXwMUVTSR20U0f9` (override if needed). |
| `ELEVENLABS_TTS_MODEL` | TTS | e.g. `eleven_v3_conversational` (tags) or `eleven_flash_v2` (faster, no v3 tags). |
| `ELEVENLABS_COMPANY_NAME` | Prompt | Replaces `{{company_name}}` in first message and prompt. |
| `OPENAI_API_KEY` | Extraction | Post-call structured FNOL JSON. |
| `CLAIM_EXTRACTION_MODEL` | Extraction | Default `gpt-4o-mini`. |

---

## Local setup (hackathon demo)

```bash
git clone https://github.com/0xk4g3/Bigberlin-hackathon.git
cd Bigberlin-hackathon

python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env — all keys above

# Terminal A — tunnel (example: app on port 8989)
ngrok http 8989

# Put the https URL in SERVER_EXTERNAL_URL (no trailing path)

# Terminal B — voice server
python3 main.py

# Terminal C (optional) — dashboard
cd inca-dashboard
npm install && npm run dev
```

---

## Twilio configuration

1. **Voice & Fax → A call comes in**  
   - **Webhook** to:  
     `https://<YOUR_HOST>/incoming-call/<WEBHOOK_SECRET>`  
     if `WEBHOOK_SECRET` is set, else  
     `https://<YOUR_HOST>/incoming-call`  
   - Method: **HTTP POST**.

2. **Do not** leave a **TwiML App** on the number if it points elsewhere — either clear the app binding or set the app’s Voice URL to the same webhook. Otherwise Twilio will hit the wrong server.

3. **`SERVER_EXTERNAL_URL`** in `.env` must use the **same host** as the webhook (ngrok URLs change each session on free tier — update Twilio every time).

4. If **`TWILIO_AUTH_TOKEN`** is set, signature validation uses the **exact URL** Twilio requested; mismatches return **404**.

The repo includes **`setup.py`** for Fly.io + Twilio wizard flows; for a quick hackathon tunnel, manual Console + `.env` is enough.

---

## ElevenLabs agent

Agent prompt, voice, TTS sliders, and LLM binding are pushed from code:

```bash
python3 -m voice_agent.elevenlabs_fnol_sync
```

Verify a voice ID works with your key:

```bash
python3 -m voice_agent.elevenlabs_voice_check
```

After PATCH, **publish** the agent in the **ElevenLabs** UI if **Published** still differs from **Main** — otherwise live calls may use an old revision.

---

## Operator dashboard

- **Path:** `inca-dashboard/`  
- **Dev:** `npm run dev` (default Next.js port, often `3000`).  
- **Backend feed:** Python app exposes **`WebSocket /ws`**. Configure the dashboard’s env (e.g. `NEXT_PUBLIC_WS_URL` in `inca-dashboard/.env.local`) to point at your running server (through ngrok if the dashboard runs on another machine).

On each completed call, the server broadcasts a **`call_ended`** message with transcript and merged claim fields for UI cards.

---

## Optional paths

| Path | Purpose |
|------|--------|
| `python setup.py` | Interactive Twilio + optional Fly.io deploy. |
| `python setup.py --twilio-only` / `--update-url URL` | Refresh webhooks. |
| `python dev_client.py` | Mic/speaker test against local server **without** Twilio (needs `requirements-dev.txt`). |
| `voice_agent/session.py` + Deepgram | Alternate stack; not wired in `main.py` for inbound. |
| `docs/*.md` | Deepgram-era architecture and prompt guides — still useful reading. |

---

## Project structure

```
├── main.py                     # Starlette app, routes, uvicorn entry
├── config.py                   # Env loading + validation
├── setup.py                    # Setup wizard (Twilio / Fly.io)
├── requirements.txt
├── .env.example
├── telephony/
│   └── routes.py               # POST /incoming-call, WS /twilio
├── voice_agent/
│   ├── elevenlabs_session.py # Twilio ↔ ElevenLabs bridge
│   ├── elevenlabs_fnol_sync.py   # PATCH agent (Klaus FNOL)
│   ├── elevenlabs_voice_check.py # List usable voice IDs
│   ├── session.py              # Deepgram session (legacy path)
│   ├── agent_config.py         # Deepgram agent config (legacy / consistency)
│   └── function_handlers.py
├── backend/
│   ├── claims_service.py       # Drafts, finalize_call, /ws broadcast
│   ├── scheduling_service.py # Mock scheduling (reference)
│   └── models.py
├── integrations/               # Pioneer + offline risk demo (not imported by main.py)
├── inca-dashboard/             # Next.js operator UI
└── docs/                       # Architecture & prompt guides
```

---

## Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| Call connects, **no audio** | `SERVER_EXTERNAL_URL` ≠ Twilio stream host; or ElevenLabs agent not **published**; or voice ID invalid — run `elevenlabs_voice_check` + `fnol_sync`. |
| **404** on `/incoming-call` | Wrong **`WEBHOOK_SECRET`** path; or Twilio signature URL mismatch. |
| **405** on `GET /incoming-call` | Browser hit; Twilio uses **POST** only — ignore. |
| **502** via ngrok | Python server down, wrong port, or crash — check server logs. |
| Dashboard empty | No client on **`/ws`**; or `OPENAI_API_KEY` missing so extraction skips fields. |

---

## Sponsor tracks: Pioneer & Entire

These integrations are **submission and research layers only**. They do **not** import into `main.py`, `telephony/`, or `voice_agent/elevenlabs_session.py` — inbound calls, Twilio, and ElevenLabs behaviour are unchanged.

### [Fastino](https://fastino.ai/) — Best use of [Pioneer](https://pioneer.ai/)

**We use Pioneer in this repository** as follows:

| Requirement (challenge) | How we satisfy it |
|---------------------------|-------------------|
| Use Pioneer in the project | Optional **`POST https://api.pioneer.ai/inference`** from `integrations/pioneer_risk.py` with **`task: "extract_entities"`** and a **GLiNER2-class encoder** (`fastino/gliner2-base-v1` by default, overridable via `PIONEER_MODEL_ID`). |
| Fine-tune / replace general LLM calls | Live calls still use **ElevenLabs + Gemini** for conversation; **OpenAI** remains the primary **post-call JSON extraction**. Pioneer adds a **second, specialised encoder pass** on the same structured FNOL narrative — complementary, not a swap of the voice pipeline. |
| Synthetic data, evaluation, adaptive inference | Narrative for Pioneer is built from **synthetic or real claim dicts**; scores and factors can be compared to frontier extraction offline. `python3 -m integrations` supports stdin JSON for repeatable eval runs. |
| Creative **GLiNER2** use | Entity schema tuned for **motor FNOL** (`vehicle_plate`, `location`, `injury`, `weather`, etc.) on free-text summaries — not generic NER demos. |

**Confirm for judges:** Pioneer is invoked only when **`PIONEER_API_KEY`** is set; without it, the same module still runs a **transparent local risk heuristic** (no network) so demos work offline. See **`integrations/README.md`** and run:

```bash
python3 -m integrations
```

Design intent matches the broader **ClaimAI** brief (predictive / preventive intelligence on top of intake) without coupling that experiment to production telephony.

### [Entire](https://entire.io/?utm_source=luma) — Best use of Entire

**We use Entire** for **provenance and session transparency**: connect this GitHub repository in the Entire dashboard (install the [Entire CLI](https://github.com/entireio/cli), run `entire enable` in the repo per [Entire docs](https://docs.entire.io/)).

**Repositories overview (submission link — replace after you connect your fork/org):**

**[Entire overview → `0xk4g3/Bigberlin-hackathon`](https://entire.io/gh/0xk4g3/Bigberlin-hackathon/overview)**  

If your Entire URL differs after linking GitHub, update this README in your fork to the exact **overview** page Entire shows for *this* repo.

---

## Credits & license

- **Team noTime** — Big Berlin Hackathon submission.  
- Project evolved from Deepgram’s inbound telephony reference; **production voice path** documented here is **Twilio + ElevenLabs + OpenAI**.  
- See repository **LICENSE** for original license terms.
