.PHONY: up down restart build logs shell ps clean dev test

# ── Docker operations ─────────────────────────────────────────────────────────

up:
	docker compose up -d

build:
	docker compose up -d --build

rebuild:
	docker compose build --no-cache claimcall
	docker compose up -d

down:
	docker compose down

stop:
	docker compose stop

restart:
	docker compose restart claimcall

restart-all:
	docker compose down && docker compose up -d

# Delete containers + volumes (fresh start)
clean:
	docker compose down -v --remove-orphans
	docker image rm -f claimcall-claimcall 2>/dev/null || true

# ── Logs ──────────────────────────────────────────────────────────────────────

logs:
	docker compose logs -f claimcall

logs-nginx:
	docker compose logs -f nginx

logs-all:
	docker compose logs -f

# ── Status ────────────────────────────────────────────────────────────────────

ps:
	docker compose ps

health:
	curl -s http://localhost:8000/health | python3 -m json.tool

# ── Shell access ──────────────────────────────────────────────────────────────

shell:
	docker compose exec claimcall bash

# ── Local dev (no Docker) ─────────────────────────────────────────────────────

dev:
	.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload --log-level info

# ── Tests ─────────────────────────────────────────────────────────────────────

test-audio:
	.venv/bin/python -c "\
import base64, numpy as np; \
from services.audio import mulaw_to_pcm16, pcm16_to_mulaw, apply_telephone_bandpass; \
m=bytes([0x7F]*160); p=mulaw_to_pcm16(m); assert len(p)==320; \
b=apply_telephone_bandpass(p); assert len(b)==len(p); \
print('audio OK')"

test-supabase:
	.venv/bin/python -c "\
import asyncio; \
from config import get_settings; \
from services.supabase_client import SupabaseService; \
async def t(): \
    svc = await SupabaseService.create(get_settings()); \
    assert await svc.ping(); \
    cid = await svc.create_call('CA_MKTEST','+4917612345','+49800123'); \
    call = await svc.get_call('CA_MKTEST'); \
    assert call['call_sid']=='CA_MKTEST'; \
    print('Supabase OK — id=' + cid); \
asyncio.run(t())"

test-relay:
	.venv/bin/python -c "\
import asyncio, json, base64; \
from unittest.mock import AsyncMock, patch; \
from websocket.relay import CallRelay; \
class EL: \
    async def connect(self): return self; \
    async def send_audio(self, p): pass; \
    async def send_pong(self, e): pass; \
    async def receive(self): \
        import asyncio; await asyncio.sleep(0); yield {'type':'agent_response','agent_response_event':{'agent_response':'Hi'}}; \
    async def close(self): pass; \
    connected=True; \
msgs=[json.dumps({'event':'connected'}),json.dumps({'event':'start','start':{'streamSid':'MZ1','callSid':'CA1','customParameters':{'from':'+491','to':'+492'}}}),json.dumps({'event':'stop'})]; \
class WS: \
    async def iter_text(self): \
        import asyncio; \
        for m in msgs: await asyncio.sleep(0); yield m; \
    async def send_text(self,d): pass; \
sb=AsyncMock(); sb.create_call=AsyncMock(return_value='uuid1'); sb.update_call_stream_sid=AsyncMock(); sb.update_call_el_conversation_id=AsyncMock(); sb.complete_call=AsyncMock(); sb.save_transcript_chunk=AsyncMock(); \
tw=AsyncMock(); tw.send_sms=AsyncMock(); \
async def run(): \
    r=CallRelay('CA1','ag','key',sb,tw,None); \
    with patch('websocket.relay.ElevenLabsClient',return_value=EL()): await r.run(WS()); \
    assert sb.create_call.called; assert sb.complete_call.called; print('relay OK'); \
asyncio.run(run())"

test-all: test-audio test-supabase test-relay
	@echo "All tests passed"
