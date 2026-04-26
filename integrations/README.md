# Integrations (hackathon tracks) — **not** on the live call path

This folder is **isolated** from `telephony/`, `main.py`, and `voice_agent/elevenlabs_session.py`. Inbound audio and Twilio behaviour are unchanged.

**Full sponsor guide:** [docs/SPONSOR_PIONEER_ENTIRE.md](../docs/SPONSOR_PIONEER_ENTIRE.md) · Root [README.md](../README.md)

## Pioneer (Fastino)

1. Get an API key from [Pioneer / Fastino](https://pioneer.ai/) (`pio_sk_…`).
2. Set in `.env` (optional):

   - `PIONEER_API_KEY`
   - `PIONEER_MODEL_ID` (default: `fastino/gliner2-base-v1`)

3. Run the offline demo (built-in sample claim — does not read stdin):

   ```bash
   python3 -m integrations
   ```

   Custom JSON from stdin or file:

   ```bash
   echo '{"vehicle_plate":"B XY 9","location":"rain on A9"}' | python3 -m integrations --stdin
   python3 -m integrations --file path/to/claim.json
   ```

With a key, the demo calls **`POST https://api.pioneer.ai/inference`** with **`extract_entities`** (GLiNER2-style encoder) on a short narrative built from claim fields — a **creative NER layer** beside the existing OpenAI post-call extraction.

Without a key, Pioneer is skipped and only the **local risk heuristic** runs (still useful for storytelling and tests).

## Entire

No code here — connect this repository in the [Entire](https://entire.io/) dashboard after `entire enable` (see main README). Submission uses your **Entire repositories overview** URL.
