"""Promote/demote classification labels after scoring."""

from __future__ import annotations

from ospf_engine.models import EvidenceLevel, ScoredFault
from ospf_engine.models.analysis import (
    CLASSIFICATION_CONTRIBUTING,
    CLASSIFICATION_LIKELY_ROOT,
    CLASSIFICATION_POSSIBLE,
    CLASSIFICATION_ROOT_CAUSE,
    CLASSIFICATION_SIDE_EFFECT,
)
from ospf_engine.reasoning.side_effects import EXPLAINS


def classify(ranked: list[ScoredFault]) -> list[ScoredFault]:
    """Apply ROOT_CAUSE / SIDE_EFFECT / CONTRIBUTING / POSSIBLE labels in context."""
    if not ranked:
        return ranked

    top = ranked[0]
    if top.best_evidence_level == EvidenceLevel.CONFIG:
        top.classification = CLASSIFICATION_ROOT_CAUSE
    elif top.best_evidence_level == EvidenceLevel.STRONG:
        top.classification = CLASSIFICATION_LIKELY_ROOT
    else:
        top.classification = CLASSIFICATION_POSSIBLE

    # Identify all CONFIG / LIKELY-ROOT confirmed causes (more than one is allowed,
    # e.g. Native VLAN + DHCP Helper Missing happen simultaneously).
    confirmed_causes = [
        f for f in ranked if f.best_evidence_level == EvidenceLevel.CONFIG
    ]

    explained_by_confirmed: set[str] = set()
    for cause in confirmed_causes:
        explained_by_confirmed.update(EXPLAINS.get(cause.name, set()))

    for fault in ranked[1:]:
        if fault.best_evidence_level == EvidenceLevel.CONFIG:
            # Two confirmed causes: both are ROOT_CAUSEs.
            fault.classification = CLASSIFICATION_ROOT_CAUSE
            continue

        if fault.name in explained_by_confirmed and fault.best_evidence_level == EvidenceLevel.WEAK:
            fault.classification = CLASSIFICATION_SIDE_EFFECT
        elif fault.best_evidence_level == EvidenceLevel.STRONG:
            fault.classification = CLASSIFICATION_CONTRIBUTING
        else:
            fault.classification = CLASSIFICATION_POSSIBLE

    return ranked
