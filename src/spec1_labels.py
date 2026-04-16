"""Canonical label constants for SPEC-1.

All enum-like string values used across packages are defined here.
Every module should import from this file rather than hard-coding strings.
"""

# ── Source types ──────────────────────────────────────────────────────────────
SOURCE_RSS           = "RSS"
SOURCE_FARA          = "FARA"
SOURCE_CONGRESSIONAL = "CONGRESSIONAL"
SOURCE_NARRATIVE     = "NARRATIVE"

# ── Congressional record types ────────────────────────────────────────────────
RECORD_BILL       = "BILL"
RECORD_RESOLUTION = "RESOLUTION"
RECORD_HEARING    = "HEARING"
RECORD_AMENDMENT  = "AMENDMENT"

# ── Chamber ───────────────────────────────────────────────────────────────────
CHAMBER_HOUSE   = "HOUSE"
CHAMBER_SENATE  = "SENATE"
CHAMBER_UNKNOWN = "UNKNOWN"

# ── FARA registration status ──────────────────────────────────────────────────
FARA_STATUS_ACTIVE     = "ACTIVE"
FARA_STATUS_TERMINATED = "TERMINATED"

# ── Congressional bill status ─────────────────────────────────────────────────
CONGRESS_STATUS_INTRODUCED    = "INTRODUCED"
CONGRESS_STATUS_PASSED_HOUSE  = "PASSED_HOUSE"
CONGRESS_STATUS_PASSED_SENATE = "PASSED_SENATE"
CONGRESS_STATUS_ENACTED       = "ENACTED"
CONGRESS_STATUS_FAILED        = "FAILED"

# ── Narrative sentiment ───────────────────────────────────────────────────────
SENTIMENT_POSITIVE = "POSITIVE"
SENTIMENT_NEGATIVE = "NEGATIVE"
SENTIMENT_NEUTRAL  = "NEUTRAL"
SENTIMENT_MIXED    = "MIXED"

# ── Investigation outcome classification ──────────────────────────────────────
OUTCOME_CORROBORATED = "CORROBORATED"
OUTCOME_ESCALATE     = "ESCALATE"
OUTCOME_INVESTIGATE  = "INVESTIGATE"
OUTCOME_MONITOR      = "MONITOR"
OUTCOME_CONFLICTED   = "CONFLICTED"
OUTCOME_ARCHIVE      = "ARCHIVE"

# ── Cross-source verification classification ──────────────────────────────────
VERIF_CORROBORATED = "CORROBORATED"
VERIF_PARTIAL      = "PARTIAL"
VERIF_UNVERIFIED   = "UNVERIFIED"
VERIF_CONFLICTED   = "CONFLICTED"

# ── Psyop risk classification ─────────────────────────────────────────────────
PSYOP_HIGH_RISK   = "HIGH_RISK"
PSYOP_MEDIUM_RISK = "MEDIUM_RISK"
PSYOP_LOW_RISK    = "LOW_RISK"
PSYOP_CLEAN       = "CLEAN"

# ── Psyop pattern threat level ────────────────────────────────────────────────
THREAT_HIGH   = "HIGH"
THREAT_MEDIUM = "MEDIUM"
THREAT_LOW    = "LOW"

# ── Lead priority ─────────────────────────────────────────────────────────────
PRIORITY_CRITICAL = "CRITICAL"
PRIORITY_HIGH     = "HIGH"
PRIORITY_MEDIUM   = "MEDIUM"
PRIORITY_LOW      = "LOW"

# ── Lead category ─────────────────────────────────────────────────────────────
CATEGORY_MILITARY     = "MILITARY"
CATEGORY_CYBER        = "CYBER"
CATEGORY_GEOPOLITICAL = "GEOPOLITICAL"
CATEGORY_FARA         = "FARA"
CATEGORY_PSYOP        = "PSYOP"
CATEGORY_QUANT        = "QUANT"
