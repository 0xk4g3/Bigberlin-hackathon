"""
FNOL extraction, urgency scoring, and fraud detection.

Rule-based — no ML required. ElevenLabs agent (Sophie) collects structured
data during the call; this service validates, enriches, and scores it.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Optional

from models.claim import (
    ClaimCreate,
    FNOLExtraction,
    FraudScore,
    LossType,
    ReporterType,
    UrgencyLevel,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Keyword sets for text scanning
# ─────────────────────────────────────────────────────────────────────────────

_CRITICAL_KEYWORDS = {
    "hospitaliz", "hospital", "ambulance", "intensive care", "icu",
    "life-threatening", "unconscious", "fatality", "killed", "dead",
    "drunk driving", "dui", "alcohol", "drug", "hit and run", "fled",
    "criminal", "arrested", "manslaughter",
}
_HIGH_KEYWORDS = {
    "injury", "injured", "hurt", "broken", "fracture", "whiplash",
    "lawyer", "attorney", "solicitor", "lawsuit", "sue",
    "multi-vehicle", "multiple cars", "pile-up", "pileup",
    "total loss", "write-off",
}
_WILDLIFE_KEYWORDS = {"deer", "animal", "wildlife", "fox", "boar", "wild pig"}
_THEFT_KEYWORDS = {"stolen", "theft", "break-in", "burglary", "vandal"}
_FIRE_KEYWORDS = {"fire", "burn", "arson", "flame", "explosion"}
_FLOOD_KEYWORDS = {"flood", "water damage", "hail", "storm", "tornado", "hurricane"}
_PARKING_KEYWORDS = {"parking", "parked", "scratch", "dent", "hit while parked"}


def _text_matches(text_lower: str, keywords: set) -> bool:
    return any(kw in text_lower for kw in keywords)


def _transcript_text(transcript: list[dict]) -> str:
    parts = [t.get("text", "") for t in transcript if t.get("speaker") == "caller"]
    return " ".join(parts).lower()


# ─────────────────────────────────────────────────────────────────────────────
# FNOL extraction
# ─────────────────────────────────────────────────────────────────────────────

class ClaimProcessor:

    def extract_fnol(
        self,
        transcript: list[dict],
        collected_data: dict,
        call_metadata: dict,
    ) -> FNOLExtraction:
        """
        Build FNOLExtraction from ElevenLabs collected_data (priority)
        with transcript keyword fallback for gaps.
        """
        t = _transcript_text(transcript)
        cd = collected_data or {}

        def get(key: str, fallback=None):
            return cd.get(key) or fallback

        # Detect loss_type from text if not in collected_data
        loss_type_raw = get("loss_type")
        if not loss_type_raw:
            if _text_matches(t, _WILDLIFE_KEYWORDS):
                loss_type_raw = "wildlife"
            elif _text_matches(t, _PARKING_KEYWORDS):
                loss_type_raw = "parking_damage"
            elif "personal injury" in t or _text_matches(t, {"ambulance", "hospitaliz", "fracture"}):
                loss_type_raw = "personal_injury"
            elif _text_matches(t, {"collision", "crash", "accident", "hit"}):
                loss_type_raw = "moving_collision"

        try:
            loss_type = LossType(loss_type_raw) if loss_type_raw else None
        except ValueError:
            loss_type = None

        try:
            reporter_type = ReporterType(get("reporter_type")) if get("reporter_type") else None
        except ValueError:
            reporter_type = None

        return FNOLExtraction(
            reporter_type=reporter_type,
            policy_number=get("policy_number") or self._extract_policy_number(t),
            policyholder_name=get("policyholder_name") or call_metadata.get("caller_name"),
            policyholder_phone=call_metadata.get("from_number"),
            policyholder_email=get("policyholder_email"),
            driver_is_policyholder=get("driver_is_policyholder", True),
            driver_name=get("driver_name"),
            license_plate=get("license_plate") or self._extract_plate(t),
            vehicle_make=get("vehicle_make"),
            vehicle_model=get("vehicle_model"),
            vehicle_drivable=get("vehicle_drivable"),
            incident_date=self._parse_date(get("incident_date")),
            incident_time=None,
            incident_location_address=get("incident_location") or get("incident_address"),
            incident_location_city=get("incident_city"),
            loss_type=loss_type,
            incident_description=get("incident_description"),
            other_party_name=get("other_party_name"),
            other_party_plate=get("other_party_plate"),
            other_party_insurer=get("other_party_insurer"),
            police_on_scene=bool(get("police_on_scene")) or "police" in t,
            injuries_reported=bool(get("injuries")) or _text_matches(t, {"injured", "injury", "hurt"}),
            alcohol_drugs_involved=bool(get("alcohol")) or _text_matches(t, {"drunk", "alcohol", "drug"}),
            hit_and_run=bool(get("hit_and_run")) or "hit and run" in t or "fled" in t,
            photos_taken=bool(get("photos")) or "photo" in t or "picture" in t,
            rental_car_requested=bool(get("rental")) or "rental" in t or "replacement car" in t,
            lawyer_own_side=bool(get("lawyer")) or _text_matches(t, {"lawyer", "attorney", "solicitor"}),
            report_delay_hours=get("report_delay_hours"),
        )

    def _extract_policy_number(self, text: str) -> Optional[str]:
        m = re.search(r"\b([A-Z]{2,4}[-\s]?\d{4,10})\b", text.upper())
        return m.group(1).replace(" ", "-") if m else None

    def _extract_plate(self, text: str) -> Optional[str]:
        m = re.search(r"\b([A-ZÄÖÜ]{1,3}[-\s]?[A-Z]{1,2}[-\s]?\d{1,4})\b", text.upper())
        return m.group(1) if m else None

    def _parse_date(self, raw) -> Optional[object]:
        if not raw:
            return None
        if hasattr(raw, "date"):
            return raw.date()
        try:
            from datetime import date
            return datetime.fromisoformat(str(raw)).date()
        except (ValueError, TypeError):
            return None

    # ──────────────────────────────────────────────────────────────────────────
    # Urgency scoring
    # ──────────────────────────────────────────────────────────────────────────

    def score_urgency(self, fnol: FNOLExtraction) -> tuple[str, str]:
        """Returns (urgency_level, urgency_reason)."""
        desc = (fnol.incident_description or "").lower()
        full = desc

        if (
            fnol.alcohol_drugs_involved
            or fnol.hit_and_run
            or fnol.injuries_reported and _text_matches(full, {"hospital", "icu", "ambulance", "death", "fatal"})
        ):
            return UrgencyLevel.critical.value, self._urgency_reason(fnol, "critical")

        if (
            fnol.injuries_reported
            or fnol.lawyer_own_side
            or _text_matches(full, _HIGH_KEYWORDS)
        ):
            return UrgencyLevel.high.value, self._urgency_reason(fnol, "high")

        if fnol.loss_type in (LossType.moving_collision, LossType.stationary_hit):
            return UrgencyLevel.moderate.value, self._urgency_reason(fnol, "moderate")

        return UrgencyLevel.routine.value, self._urgency_reason(fnol, "routine")

    def _urgency_reason(self, fnol: FNOLExtraction, level: str) -> str:
        reasons = {
            "critical": [],
            "high": [],
            "moderate": [],
            "routine": [],
        }
        if fnol.alcohol_drugs_involved:
            reasons["critical"].append("alcohol/drugs involved")
        if fnol.hit_and_run:
            reasons["critical"].append("hit and run")
        if fnol.injuries_reported:
            reasons["high"].append("personal injuries reported")
        if fnol.lawyer_own_side:
            reasons["high"].append("lawyer instructed")
        if fnol.loss_type == LossType.moving_collision:
            reasons["moderate"].append("vehicle collision")
        parts = reasons.get(level, [])
        return "; ".join(parts) if parts else level.capitalize() + " incident"

    # ──────────────────────────────────────────────────────────────────────────
    # Fraud scoring
    # ──────────────────────────────────────────────────────────────────────────

    def score_fraud(
        self, fnol: FNOLExtraction, prior_claims: int = 0
    ) -> tuple[str, dict]:
        """Returns (fraud_score, signals_dict). Weighted heuristic."""
        signals: dict[str, int] = {}
        score = 0

        if fnol.report_delay_hours and fnol.report_delay_hours > 72:
            signals["late_reporting"] = 2
            score += 2

        if prior_claims >= 1:
            weight = min(prior_claims, 2) + 1
            signals["prior_claims_24mo"] = weight
            score += weight

        desc = (fnol.incident_description or "").lower()
        if _text_matches(desc, {"for sale", "selling", "listed"}):
            signals["vehicle_for_sale"] = 2
            score += 2

        if fnol.other_party_name and fnol.policyholder_name:
            if self._names_similar(fnol.other_party_name, fnol.policyholder_name):
                signals["parties_related"] = 2
                score += 2

        if score <= 2:
            return FraudScore.low.value, signals
        elif score <= 4:
            return FraudScore.medium.value, signals
        else:
            return FraudScore.high.value, signals

    def _names_similar(self, a: str, b: str) -> bool:
        a_parts = set(a.lower().split())
        b_parts = set(b.lower().split())
        return bool(a_parts & b_parts)

    # ──────────────────────────────────────────────────────────────────────────
    # SLA + SF-Klasse
    # ──────────────────────────────────────────────────────────────────────────

    def calculate_assessor_sla(self, urgency: str) -> int:
        """Returns SLA in hours."""
        return {"critical": 4, "high": 24, "moderate": 48, "routine": 72}.get(urgency, 48)

    def determine_sf_impact(self, fnol: FNOLExtraction, policy: dict) -> dict:
        """Assess no-claims bonus (SF-Klasse) impact."""
        rabattschutz = policy.get("rabattschutz", False)
        at_fault = fnol.loss_type in (LossType.moving_collision, LossType.stationary_hit)

        downgrade_likely = at_fault and not rabattschutz
        msg = (
            "Rabattschutz applies — SF class protected"
            if rabattschutz and at_fault
            else "SF downgrade likely — at-fault collision without Rabattschutz"
            if downgrade_likely
            else "SF impact minimal"
        )
        return {
            "downgrade_likely": downgrade_likely,
            "rabattschutz_applies": rabattschutz,
            "message": msg,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Full orchestration
    # ──────────────────────────────────────────────────────────────────────────

    def build_claim_payload(
        self,
        call_id: str,
        transcript: list[dict],
        collected_data: dict,
        call_metadata: dict,
        prior_claims: int = 0,
    ) -> ClaimCreate:
        fnol = self.extract_fnol(transcript, collected_data, call_metadata)
        urgency, urgency_reason = self.score_urgency(fnol)
        fraud_score, fraud_signals = self.score_fraud(fnol, prior_claims=prior_claims)
        sla = self.calculate_assessor_sla(urgency)
        siu = fraud_score == FraudScore.high.value or urgency == UrgencyLevel.critical.value

        return ClaimCreate(
            call_id=call_id,
            reporter_type=fnol.reporter_type,
            policy_number=fnol.policy_number,
            policyholder_name=fnol.policyholder_name,
            policyholder_phone=fnol.policyholder_phone,
            policyholder_email=fnol.policyholder_email,
            driver_is_policyholder=fnol.driver_is_policyholder,
            driver_name=fnol.driver_name,
            license_plate=fnol.license_plate,
            vehicle_make=fnol.vehicle_make,
            vehicle_model=fnol.vehicle_model,
            vehicle_drivable=fnol.vehicle_drivable,
            incident_date=fnol.incident_date,
            incident_time=fnol.incident_time,
            incident_location_address=fnol.incident_location_address,
            incident_location_city=fnol.incident_location_city,
            loss_type=fnol.loss_type,
            incident_description=fnol.incident_description,
            other_party_name=fnol.other_party_name,
            other_party_plate=fnol.other_party_plate,
            other_party_insurer=fnol.other_party_insurer,
            police_on_scene=fnol.police_on_scene,
            injuries_reported=fnol.injuries_reported,
            alcohol_drugs_involved=fnol.alcohol_drugs_involved,
            hit_and_run=fnol.hit_and_run,
            photos_taken=fnol.photos_taken,
            rental_car_requested=fnol.rental_car_requested,
            lawyer_own_side=fnol.lawyer_own_side,
            report_delay_hours=fnol.report_delay_hours,
            urgency=urgency,
            urgency_reason=urgency_reason,
            assessor_sla_hours=sla,
            fraud_score=fraud_score,
            fraud_signals=fraud_signals,
            siu_referral=siu,
            full_fnol_payload=fnol.model_dump(mode="json"),
        )
