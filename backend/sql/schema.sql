-- =============================================================================
-- ClaimCall — Supabase Schema
-- Run in: Supabase Dashboard → SQL Editor
-- =============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- CALLS
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_sid TEXT UNIQUE NOT NULL,
    stream_sid TEXT,
    elevenlabs_conversation_id TEXT,
    from_number TEXT,
    to_number TEXT,
    status TEXT DEFAULT 'in_progress'
        CHECK (status IN ('in_progress', 'completed', 'failed')),
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    duration_seconds INTEGER,
    transcript JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- TRANSCRIPTS (real-time, per utterance)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS transcripts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id UUID REFERENCES calls(id) ON DELETE CASCADE,
    speaker TEXT NOT NULL CHECK (speaker IN ('agent', 'caller')),
    text TEXT NOT NULL,
    timestamp_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- CLAIMS (one per completed FNOL call)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS claims (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id UUID REFERENCES calls(id),

    -- Reporter
    reporter_type TEXT CHECK (reporter_type IN (
        'policyholder', 'driver', 'claimant', 'repair_shop', 'lawyer', 'broker'
    )),

    -- Policy
    policy_number TEXT,
    product_name TEXT,
    coverage_type TEXT CHECK (coverage_type IN (
        'Vollkasko', 'Teilkasko', 'liability_only'
    )),
    sf_klasse_liability TEXT,
    sf_klasse_vollkasko TEXT,
    rabattschutz BOOLEAN,
    werkstattbindung BOOLEAN,
    premium_in_arrears BOOLEAN DEFAULT FALSE,
    sf_downgrade_risk BOOLEAN DEFAULT FALSE,
    geographic_scope_valid BOOLEAN DEFAULT TRUE,
    seasonal_plate_in_season BOOLEAN DEFAULT TRUE,

    -- Policyholder
    policyholder_name TEXT,
    policyholder_dob DATE,
    policyholder_phone TEXT,
    policyholder_email TEXT,
    preferred_channel TEXT DEFAULT 'sms',

    -- Driver
    driver_is_policyholder BOOLEAN DEFAULT TRUE,
    driver_name TEXT,
    driver_dob DATE,
    driver_license_valid BOOLEAN,
    driver_license_class TEXT,
    driver_license_held_since DATE,
    driver_in_policy_scope BOOLEAN,
    alcohol_drugs_involved BOOLEAN DEFAULT FALSE,
    breathalyzer_conducted BOOLEAN DEFAULT FALSE,
    hit_and_run BOOLEAN DEFAULT FALSE,

    -- Vehicle
    license_plate TEXT,
    vin TEXT,
    vehicle_make TEXT,
    vehicle_model TEXT,
    vehicle_first_registration DATE,
    vehicle_use_type TEXT,
    vehicle_drivable BOOLEAN,
    vehicle_location TEXT,
    vehicle_towed_to TEXT,
    hu_au_current BOOLEAN,
    preexisting_damage BOOLEAN DEFAULT FALSE,
    preexisting_damage_detail TEXT,
    modifications_undeclared BOOLEAN DEFAULT FALSE,

    -- Incident
    incident_date DATE,
    incident_time TIME,
    incident_location_address TEXT,
    incident_location_city TEXT,
    incident_location_country TEXT DEFAULT 'DE',
    incident_road_type TEXT,
    incident_weather TEXT,
    incident_visibility TEXT,
    loss_type TEXT CHECK (loss_type IN (
        'moving_collision', 'stationary_hit', 'parking_damage',
        'wildlife', 'property_only', 'personal_injury', 'other'
    )),
    incident_description TEXT,
    direction_own TEXT,
    direction_other TEXT,
    speed_own_kmh INTEGER,
    right_of_way TEXT,
    traffic_light_state TEXT,
    european_accident_statement BOOLEAN DEFAULT FALSE,
    photos_taken BOOLEAN DEFAULT FALSE,

    -- Other party
    other_party_name TEXT,
    other_party_address TEXT,
    other_party_phone TEXT,
    other_party_plate TEXT,
    other_party_vehicle TEXT,
    other_party_insurer TEXT,
    other_party_policy_number TEXT,
    other_party_owner_differs BOOLEAN DEFAULT FALSE,
    fault_admitted BOOLEAN,
    fault_denied BOOLEAN,
    fault_written BOOLEAN DEFAULT FALSE,
    other_party_claim_raised BOOLEAN DEFAULT FALSE,
    other_party_lawyer BOOLEAN DEFAULT FALSE,

    -- Police
    police_on_scene BOOLEAN DEFAULT FALSE,
    police_station TEXT,
    police_case_number TEXT,
    criminal_proceedings BOOLEAN DEFAULT FALSE,
    offense_type TEXT CHECK (offense_type IN (
        'none', 'administrative', 'criminal_dui',
        'criminal_hit_and_run', 'dangerous_driving'
    )) DEFAULT 'none',

    -- Witnesses
    witnesses JSONB DEFAULT '[]',

    -- Injuries
    injuries_reported BOOLEAN DEFAULT FALSE,
    injuries_detail JSONB DEFAULT '[]',

    -- Damage
    damage_own_vehicle TEXT,
    damage_own_areas JSONB DEFAULT '[]',
    damage_other_vehicle TEXT,
    damage_third_party JSONB DEFAULT '[]',

    -- Coverage checks
    use_within_scope BOOLEAN DEFAULT TRUE,
    paid_transport BOOLEAN DEFAULT FALSE,
    racing_event BOOLEAN DEFAULT FALSE,
    late_reporting BOOLEAN DEFAULT FALSE,
    late_reporting_reason TEXT,
    report_delay_hours INTEGER,

    -- Liability
    prima_facie_type TEXT,
    prima_facie_party TEXT CHECK (prima_facie_party IN (
        'own', 'other', 'shared', 'unclear'
    )),

    -- Recourse
    recourse_other_insurer BOOLEAN DEFAULT FALSE,
    recourse_third_party BOOLEAN DEFAULT FALSE,
    recourse_road_authority BOOLEAN DEFAULT FALSE,

    -- Settlement
    rental_car_requested BOOLEAN DEFAULT FALSE,
    loss_of_use_requested BOOLEAN DEFAULT FALSE,
    preferred_repair_shop TEXT,
    lawyer_own_side BOOLEAN DEFAULT FALSE,
    lawyer_name TEXT,
    lawyer_firm TEXT,

    -- Urgency & routing
    urgency TEXT DEFAULT 'moderate' CHECK (urgency IN (
        'routine', 'moderate', 'high', 'critical'
    )),
    urgency_reason TEXT,
    assessor_sla_hours INTEGER DEFAULT 48,

    -- Fraud
    fraud_score TEXT DEFAULT 'low' CHECK (fraud_score IN ('low', 'medium', 'high')),
    fraud_signals JSONB DEFAULT '{}',
    siu_referral BOOLEAN DEFAULT FALSE,

    -- Full FNOL payload (complete structured JSON for audit trail)
    full_fnol_payload JSONB,

    -- Status & approval
    status TEXT DEFAULT 'opened' CHECK (status IN (
        'opened', 'processing', 'closed', 'denied'
    )),
    coverage_confirmed_to_caller BOOLEAN DEFAULT FALSE,
    approved_by TEXT,
    approved_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- AUTO-UPDATE updated_at ON CLAIMS
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS claims_updated_at ON claims;
CREATE TRIGGER claims_updated_at
    BEFORE UPDATE ON claims
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ─────────────────────────────────────────────────────────────────────────────
-- INDEXES
-- ─────────────────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_calls_call_sid       ON calls(call_sid);
CREATE INDEX IF NOT EXISTS idx_calls_status         ON calls(status);
CREATE INDEX IF NOT EXISTS idx_calls_started_at     ON calls(started_at DESC);

CREATE INDEX IF NOT EXISTS idx_transcripts_call_id  ON transcripts(call_id);

CREATE INDEX IF NOT EXISTS idx_claims_call_id       ON claims(call_id);
CREATE INDEX IF NOT EXISTS idx_claims_status        ON claims(status);
CREATE INDEX IF NOT EXISTS idx_claims_urgency       ON claims(urgency);
CREATE INDEX IF NOT EXISTS idx_claims_fraud_score   ON claims(fraud_score);
CREATE INDEX IF NOT EXISTS idx_claims_siu           ON claims(siu_referral) WHERE siu_referral = TRUE;
CREATE INDEX IF NOT EXISTS idx_claims_created_at    ON claims(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_claims_policy_number ON claims(policy_number);
CREATE INDEX IF NOT EXISTS idx_claims_license_plate ON claims(license_plate);

-- ─────────────────────────────────────────────────────────────────────────────
-- ROW LEVEL SECURITY
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE calls      ENABLE ROW LEVEL SECURITY;
ALTER TABLE transcripts ENABLE ROW LEVEL SECURITY;
ALTER TABLE claims     ENABLE ROW LEVEL SECURITY;

-- Service role bypasses RLS automatically.
-- Add policies here if you need anon/authenticated read access from the dashboard.
-- Example (read-only for authenticated users):
-- CREATE POLICY "authenticated read calls"
--     ON calls FOR SELECT TO authenticated USING (true);
