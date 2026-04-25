from datetime import date, datetime, time
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, ConfigDict


class UrgencyLevel(str, Enum):
    routine = "routine"
    moderate = "moderate"
    high = "high"
    critical = "critical"


class FraudScore(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class ClaimStatus(str, Enum):
    opened = "opened"
    processing = "processing"
    closed = "closed"
    denied = "denied"


class ReporterType(str, Enum):
    policyholder = "policyholder"
    driver = "driver"
    claimant = "claimant"
    repair_shop = "repair_shop"
    lawyer = "lawyer"
    broker = "broker"


class LossType(str, Enum):
    moving_collision = "moving_collision"
    stationary_hit = "stationary_hit"
    parking_damage = "parking_damage"
    wildlife = "wildlife"
    property_only = "property_only"
    personal_injury = "personal_injury"
    other = "other"


class OffenseType(str, Enum):
    none = "none"
    administrative = "administrative"
    criminal_dui = "criminal_dui"
    criminal_hit_and_run = "criminal_hit_and_run"
    dangerous_driving = "dangerous_driving"


class PrimaFacieParty(str, Enum):
    own = "own"
    other = "other"
    shared = "shared"
    unclear = "unclear"


class FNOLExtraction(BaseModel):
    """Intermediate model produced by claim_processor before DB insert."""
    reporter_type: Optional[ReporterType] = None
    policy_number: Optional[str] = None
    policyholder_name: Optional[str] = None
    policyholder_phone: Optional[str] = None
    policyholder_email: Optional[str] = None
    driver_is_policyholder: bool = True
    driver_name: Optional[str] = None
    license_plate: Optional[str] = None
    vehicle_make: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_drivable: Optional[bool] = None
    incident_date: Optional[date] = None
    incident_time: Optional[time] = None
    incident_location_address: Optional[str] = None
    incident_location_city: Optional[str] = None
    incident_location_country: str = "DE"
    loss_type: Optional[LossType] = None
    incident_description: Optional[str] = None
    other_party_name: Optional[str] = None
    other_party_plate: Optional[str] = None
    other_party_insurer: Optional[str] = None
    police_on_scene: bool = False
    injuries_reported: bool = False
    alcohol_drugs_involved: bool = False
    hit_and_run: bool = False
    photos_taken: bool = False
    rental_car_requested: bool = False
    lawyer_own_side: bool = False
    report_delay_hours: Optional[int] = None


class ClaimCreate(BaseModel):
    call_id: str
    reporter_type: Optional[ReporterType] = None
    policy_number: Optional[str] = None
    product_name: Optional[str] = None
    coverage_type: Optional[str] = None
    policyholder_name: Optional[str] = None
    policyholder_phone: Optional[str] = None
    policyholder_email: Optional[str] = None
    driver_is_policyholder: bool = True
    driver_name: Optional[str] = None
    license_plate: Optional[str] = None
    vehicle_make: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_drivable: Optional[bool] = None
    incident_date: Optional[date] = None
    incident_time: Optional[time] = None
    incident_location_address: Optional[str] = None
    incident_location_city: Optional[str] = None
    incident_location_country: str = "DE"
    loss_type: Optional[LossType] = None
    incident_description: Optional[str] = None
    other_party_name: Optional[str] = None
    other_party_plate: Optional[str] = None
    other_party_insurer: Optional[str] = None
    police_on_scene: bool = False
    injuries_reported: bool = False
    injuries_detail: list[dict] = []
    alcohol_drugs_involved: bool = False
    hit_and_run: bool = False
    photos_taken: bool = False
    rental_car_requested: bool = False
    lawyer_own_side: bool = False
    report_delay_hours: Optional[int] = None
    urgency: UrgencyLevel = UrgencyLevel.moderate
    urgency_reason: Optional[str] = None
    assessor_sla_hours: int = 48
    fraud_score: FraudScore = FraudScore.low
    fraud_signals: dict = {}
    siu_referral: bool = False
    full_fnol_payload: Optional[dict] = None


class ClaimResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    call_id: Optional[str] = None
    policy_number: Optional[str] = None
    policyholder_name: Optional[str] = None
    policyholder_phone: Optional[str] = None
    loss_type: Optional[LossType] = None
    incident_description: Optional[str] = None
    urgency: UrgencyLevel
    urgency_reason: Optional[str] = None
    assessor_sla_hours: int
    fraud_score: FraudScore
    siu_referral: bool
    status: ClaimStatus
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    full_fnol_payload: Optional[Any] = None
