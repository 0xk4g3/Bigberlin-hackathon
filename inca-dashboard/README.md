# INCA operator dashboard — Team **noTime**

Next.js UI for the **Big Berlin Hackathon** submission: live view of completed FNOL calls (transcript + extracted claim fields) pushed from the Python voice server over WebSocket.

Parent project (Twilio · ElevenLabs · setup): see **[../README.md](../README.md)**.

## Run locally

From this directory:

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Connect to the voice backend

The Python app exposes **`WebSocket /ws`** (see `backend/claims_service.py`). Point the dashboard at the same host as your API server.

1. Start **`python3 main.py`** from the repo root (with `.env` configured).
2. Optional **`.env.local`** — the app uses **`NEXT_PUBLIC_WS_URL`** (see `app/claims/page.tsx`). Default if unset: `ws://localhost:8080/ws`. Match your **`SERVER_PORT`** (e.g. `ws://localhost:8989/ws`). Behind **ngrok**, use **`wss://<your-host>/ws`**.

```bash
# Example when voice server runs on 8989 locally
echo 'NEXT_PUBLIC_WS_URL=ws://localhost:8989/ws' > .env.local
```

## Stack

- **Next.js 16**, **React 19**, **TypeScript**, **Tailwind CSS 4**

## Team

**noTime** — [Bigberlin-hackathon](https://github.com/0xk4g3/Bigberlin-hackathon)
