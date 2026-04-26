"""
CLI: python3 -m integrations [--stdin] [--file path.json]

Default: built-in sample claim (no stdin read — avoids blocking in CI / pipes).
"""
from __future__ import annotations

import argparse
import json
import sys

from dotenv import load_dotenv

load_dotenv()

SAMPLE_CLAIM = {
    "caller_name": "Alex Müller",
    "location": "A100 near Tempelhof, Berlin, heavy rain at night",
    "loss_type": "rear-end collision",
    "injuries": "Minor neck pain, no ambulance",
    "police_report": "Ref 2026-AV-12",
    "vehicle_plate": "B AB 1234",
    "description": "Low visibility, sudden braking, two vehicles involved.",
}


def main() -> int:
    p = argparse.ArgumentParser(description="Pioneer + local FNOL risk demo (offline from telephony).")
    p.add_argument(
        "--stdin",
        action="store_true",
        help="Read one JSON object from stdin (claim fields).",
    )
    p.add_argument(
        "--file",
        metavar="PATH",
        help="Load claim JSON from a file.",
    )
    args = p.parse_args()

    if args.stdin and args.file:
        print("Use only one of --stdin or --file", file=sys.stderr)
        return 2
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            claim = json.load(f)
    elif args.stdin:
        raw = sys.stdin.read().strip()
        claim = json.loads(raw) if raw else SAMPLE_CLAIM
    else:
        claim = SAMPLE_CLAIM

    from integrations.pioneer_risk import run_fnol_enrichment

    out = run_fnol_enrichment(claim)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
