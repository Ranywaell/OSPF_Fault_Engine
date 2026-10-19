"""Tests for the tier-driven scorer and the suppressor."""

from __future__ import annotations

from ospf_engine.models import Evidence, EvidenceLevel
from ospf_engine.models.analysis import (
    CLASSIFICATION_ROOT_CAUSE,
    CLASSIFICATION_SIDE_EFFECT,
)
from ospf_engine.reasoning.classifier import classify
from ospf_engine.reasoning.knowledge_base import (
    F_AREA_MISMATCH,
    F_HELLOS_BLOCKED_ACL,
    F_TIMER_MISMATCH,
)
from ospf_engine.reasoning.scorer import score_faults
from ospf_engine.reasoning.suppressor import suppress_weak_alternatives


def test_config_evidence_yields_high_confidence():
    ev = [
        Evidence(
            tag="area_mismatch_link",
            level=EvidenceLevel.CONFIG,
            source="correlator",
            detail="Area 0 vs Area 1",
        )
    ]
    scored = score_faults(ev)
    assert scored
    top = scored[0]
    assert top.name == F_AREA_MISMATCH
    assert top.best_evidence_level == EvidenceLevel.CONFIG
    assert top.confidence >= 0.85


def test_only_weak_evidence_caps_confidence_low():
    ev = [
        Evidence(tag="ospf_no_neighbor", level=EvidenceLevel.WEAK, source="x", detail="-"),
        Evidence(tag="ospf_no_routes", level=EvidenceLevel.WEAK, source="x", detail="-"),
    ]
    scored = score_faults(ev)
    assert scored
    for f in scored:
        assert f.best_evidence_level == EvidenceLevel.WEAK
        assert f.confidence <= 0.40


def test_combination_upgrade_grants_config_for_acl_blocks_ospf():
    ev = [
        Evidence(
            tag="acl_blocks_ospf",
            level=EvidenceLevel.STRONG,
            source="x",
            detail="deny ospf multicast",
        ),
        Evidence(
            tag="acl_applied_inbound",
            level=EvidenceLevel.CONFIG,
            source="x",
            detail="ACL applied inbound",
        ),
    ]
    scored = score_faults(ev)
    top = next(f for f in scored if f.name == F_HELLOS_BLOCKED_ACL)
    assert top.best_evidence_level == EvidenceLevel.CONFIG
    assert top.confidence >= 0.85


def test_suppressor_drops_weak_alternatives_when_config_explains_them():
    """When 'Hellos Blocked by ACL' is CONFIG-confirmed, weak Area/Timer mismatch
    candidates that only have ospf_no_neighbor as their support must be suppressed."""
    ev = [
        Evidence(
            tag="acl_blocks_ospf_confirmed",
            level=EvidenceLevel.CONFIG,
            source="correlator",
            detail="ACL blocks OSPF",
        ),
        Evidence(
            tag="ospf_no_neighbor",
            level=EvidenceLevel.WEAK,
            source="x",
            detail="empty table",
        ),
    ]
    scored = score_faults(ev)
    classified = classify(scored)
    kept, ruled_out = suppress_weak_alternatives(classified)

    kept_names = {f.name for f in kept}
    ruled_names = {c.name for c in ruled_out}
    assert F_HELLOS_BLOCKED_ACL in kept_names
    # The WEAK-only competitors should be suppressed.
    assert F_AREA_MISMATCH in ruled_names
    assert F_TIMER_MISMATCH in ruled_names


def test_classifier_marks_top_config_as_root_cause():
    ev = [
        Evidence(
            tag="timer_mismatch_link",
            level=EvidenceLevel.CONFIG,
            source="correlator",
            detail="hello 10 vs 20",
        ),
    ]
    scored = score_faults(ev)
    classified = classify(scored)
    assert classified[0].classification == CLASSIFICATION_ROOT_CAUSE


def test_classifier_marks_explained_weak_as_side_effect():
    ev = [
        Evidence(
            tag="acl_blocks_ospf_confirmed",
            level=EvidenceLevel.CONFIG,
            source="correlator",
            detail="acl blocks ospf",
        ),
        Evidence(
            tag="ospf_no_neighbor",
            level=EvidenceLevel.WEAK,
            source="x",
            detail="empty",
        ),
    ]
    scored = score_faults(ev)
    classified = classify(scored)
    side_effect_names = [
        f.name for f in classified if f.classification == CLASSIFICATION_SIDE_EFFECT
    ]
    assert F_AREA_MISMATCH in side_effect_names
