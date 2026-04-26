# Pioneer (Fastino) & Entire — hackathon integration guide

**Team noTime** · [Bigberlin-hackathon](https://github.com/0xk4g3/Bigberlin-hackathon)

This document is the **canonical write-up** for sponsor tracks. Live phone traffic is unchanged: see [README.md](../README.md). Product vision: [CLAIMAI.pdf](CLAIMAI.pdf).

---

## Fastino — Best use of [Pioneer](https://pioneer.ai/)

### Challenge (summary)

- Use **Pioneer** in the project and **confirm** in the submission.
- Judges look for: fine-tuning / replacing generic LLM usage where it makes sense, **synthetic data**, **evaluation**, **adaptive inference**, and **creative GLiNER2** use.

### How this repo uses Pioneer

| Item | Location |
|------|----------|
| HTTP client + local risk heuristic | [`integrations/pioneer_risk.py`](../integrations/pioneer_risk.py) |
| CLI demo | [`integrations/__main__.py`](../integrations/__main__.py) → `python3 -m integrations` |
| Short readme | [`integrations/README.md`](../integrations/README.md) |

- **API:** `POST https://api.pioneer.ai/inference` with header **`X-API-Key`** (keys often start with `pio_sk_`).
- **Task:** `extract_entities` — **GLiNER2-class** encoder; default **`PIONEER_MODEL_ID=fastino/gliner2-base-v1`** (override in `.env`).
- **Input:** A short **narrative** built from FNOL-shaped JSON (plates, location, injuries, weather, etc.).
- **Without `PIONEER_API_KEY`:** Pioneer is skipped; a **deterministic local risk heuristic** still runs (good for offline demos).

### Environment (`.env`)

```bash
PIONEER_API_KEY=          # optional — enables live Pioneer NER
PIONEER_MODEL_ID=fastino/gliner2-base-v1
```

### Commands

```bash
# Sample claim JSON built in code
python3 -m integrations

# Your own JSON
python3 -m integrations --file path/to/claim.json
echo '{"vehicle_plate":"B XY 1","location":"rain on A9"}' | python3 -m integrations --stdin
```

### Confirmation for judges

**Yes — Pioneer is integrated in this repository** via the code paths above. It does **not** replace ElevenLabs on the call; it adds an **optional second pass** (encoder NER + risk hints) for research, eval, and sponsor demos.

---

## Entire — Best use of [Entire](https://entire.io/?utm_source=luma)

### Challenge (summary)

- Use **Entire** in the project and link the **repositories overview** page in the submission.

### How this repo uses Entire

Entire captures **AI-assisted development** alongside Git (hooks, optional branch `entire/checkpoints/v1`). There is **no Entire Python SDK** inside this app; integration is **workflow + documentation**.

1. Install the [Entire CLI](https://github.com/entireio/cli) (see [docs.entire.io](https://docs.entire.io/)).
2. In this repo: run **`entire enable`** (and connect GitHub in the Entire web app as documented).
3. Use your real **overview** URL in [README.md](../README.md) if it differs from the template below.

### Submission link (template)

**[Entire — repository overview](https://entire.io/gh/0xk4g3/Bigberlin-hackathon/overview)**

Replace with the exact URL Entire shows after you connect **this** GitHub repository.

### Confirmation for judges

**Yes — we use Entire** for provenance / transparency of how the project was built, per Entire’s model. The link above (once verified) satisfies the “link to repositories overview” requirement.

---

## Files in this repo (quick map)

```
integrations/
  __init__.py
  __main__.py          # CLI entry
  pioneer_risk.py      # Pioneer API + local risk
  README.md
docs/
  CLAIMAI.pdf          # Product brief
  SPONSOR_PIONEER_ENTIRE.md   # this file
README.md              # Summary + sponsor section + link here
.env.example           # PIONEER_* optional vars
```

---

## References

- [Pioneer API docs](https://agent.pioneer.ai/docs) · [OpenAPI](https://agent.pioneer.ai/openapi.json)
- [Entire docs](https://docs.entire.io/) · [Entire CLI](https://github.com/entireio/cli)
