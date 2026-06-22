"""
Runtime feature flags — all switches in one place.
Default values are production-safe (real paths, not mock).
"""
from __future__ import annotations

import os

# ── Detection ─────────────────────────────────────────────────────────────────
USE_MOCK_DETECTION: bool = os.getenv("FEH_MOCK", "0") == "1"
# True  → skip E1 LLM API; load JSON fixture + run E2 locally
# False → call real vision API (production default)

# ── Compliance Checker ────────────────────────────────────────────────────────
COMPLIANCE_MODE: str = os.getenv("FEH_COMPLIANCE", "mock")
# "off"    → D2 skipped entirely; ctx.compliance_result = None
# "mock"   → hardcoded rules, is_mock_rule=True, disclaimer shown (Phase 1 default)
# "config" → rules loaded from rules_compliance.json (Phase 2)
# "llm"    → LLM-assisted rule interpretation (Phase 3)
