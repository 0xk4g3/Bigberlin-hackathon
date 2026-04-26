"""
Pioneer (Fastino) — optional NER / risk enrichment for FNOL-shaped JSON.

Uses Pioneer HTTP API when PIONEER_API_KEY is set; otherwise exposes a
deterministic local heuristic for demos (no network, no effect on calls).
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

PIONEER_INFERENCE_URL = "https://api.pioneer.ai/inference"

# Public encoder model from Pioneer docs (GLiNER2 family) — override via env.
DEFAULT_PIONEER_MODEL_ID = "fastino/gliner2-base-v1"

# Labels we care about for motor FNOL narratives (creative GLiNER2 use case).
DEFAULT_ENTITY_SCHEMA = [
    "vehicle_plate",
    "location",
    "date",
    "injury",
    "police",
    "weather",
]


def claim_dict_to_narrative(claim: dict) -> str:
    """Flatten structured claim fields into one paragraph for NER / risk."""
    parts: list[str] = []
    for key in sorted(claim.keys()):
        val = claim.get(key)
        if val is None or val == "":
            continue
        parts.append(f"{key.replace('_', ' ')}: {val}")
    return ". ".join(parts) if parts else "No structured details provided."


def pioneer_extract_entities(text: str, schema: list[str] | None = None) -> dict:
    """Call Pioneer /inference with task extract_entities (GLiNER2 path).

    Returns {"ok": bool, ...} — never raises for missing key (caller handles).
    """
    api_key = (os.getenv("PIONEER_API_KEY") or "").strip()
    model_id = (os.getenv("PIONEER_MODEL_ID") or DEFAULT_PIONEER_MODEL_ID).strip()
    if not api_key:
        return {"ok": False, "skipped": True, "reason": "PIONEER_API_KEY not set"}

    schema = schema or list(DEFAULT_ENTITY_SCHEMA)
    payload = {
        "task": "extract_entities",
        "model_id": model_id,
        "text": text,
        "schema": schema,
        "include_confidence": True,
        "threshold": 0.35,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        PIONEER_INFERENCE_URL,
        data=body,
        headers={
            "X-API-Key": api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return {"ok": True, "model_id": model_id, "pioneer": data}
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")[:800]
        return {"ok": False, "http_status": e.code, "error": err}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def local_risk_assessment(claim: dict) -> dict:
    """Lightweight, explainable risk hints from text — no external APIs.

    Aligns with ClaimAI.pdf vision (preventive intelligence) without coupling
    to the live OpenAI extraction path.
    """
    blob = claim_dict_to_narrative(claim).lower()
    score = 18
    factors: list[str] = []

    weather_kw = ("rain", "snow", "ice", "fog", "storm", "wet", "night", "dark")
    if any(k in blob for k in weather_kw):
        score += 22
        factors.append("weather or low-visibility context mentioned")

    injury_kw = ("injur", "hurt", "ambulance", "hospital", "pain", "blood")
    if any(k in blob for k in injury_kw):
        score += 25
        factors.append("injury or medical escalation mentioned")

    highway_kw = ("motorway", "highway", "autobahn", "a100", "a1", "junction")
    if any(k in blob for k in highway_kw):
        score += 12
        factors.append("high-speed road context")

    police_kw = ("police", "report", "fine", "ticket")
    if any(k in blob for k in police_kw):
        score += 8
        factors.append("police involvement")

    if not factors:
        factors.append("no elevated automated signals from text")

    score = max(0, min(100, score))
    actions: list[str] = []
    if score >= 55:
        actions.append("Prioritise human review and outbound welfare check if injuries implied.")
    if any("weather" in f for f in factors):
        actions.append("Flag for FNOL analytics: environmental correlation bucket.")

    return {
        "risk_score": score,
        "factors": factors,
        "recommended_actions": actions,
        "source": "local_heuristic",
    }


def run_fnol_enrichment(claim: dict) -> dict:
    """Run Pioneer NER (if configured) + always attach local risk assessment."""
    narrative = claim_dict_to_narrative(claim)
    pioneer = pioneer_extract_entities(narrative)
    risk = local_risk_assessment(claim)
    return {
        "narrative": narrative,
        "pioneer_entities": pioneer,
        "risk": risk,
    }
