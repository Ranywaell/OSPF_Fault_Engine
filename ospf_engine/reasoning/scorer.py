"""Tier-driven fault scorer.

Replaces the old `total_weight / 10.0` formula with a small, explainable table
keyed by the *highest* evidence level that supports a fault and the *count* of
that level's evidence.

Confidence ladder (per fault):
  CONFIG x 1   -> 0.85
  CONFIG x 2+  -> 0.92
  STRONG x 1   -> 0.55
  STRONG x 2   -> 0.68
  STRONG x 3+  -> 0.72
  WEAK   x any -> 0.30

A combination upgrade adds +0.05 (capped at 0.95).
"""

from __future__ import annotations

from collections import defaultdict

from ospf_engine.models import Evidence, EvidenceLevel, ScoredFault
from ospf_engine.models.analysis import (
    CLASSIFICATION_CONTRIBUTING,
    CLASSIFICATION_LIKELY_ROOT,
    CLASSIFICATION_POSSIBLE,
    CLASSIFICATION_ROOT_CAUSE,
)
from ospf_engine.models.evidence import best_level
from ospf_engine.reasoning.combinations import COMBINATION_UPGRADES
from ospf_engine.reasoning.knowledge_base import FAULT_CATALOG
from ospf_engine.reasoning.tag_map import TAG_TO_FAULT


def _level_min(a: EvidenceLevel, b: EvidenceLevel) -> EvidenceLevel:
    """Return the *lower* level. The contribution-level in TAG_TO_FAULT acts as a CAP -
    a piece of CONFIG-level evidence can only contribute STRONG to a fault if its
    tag's contribution to that fault is STRONG, etc. This matches engineering reality:
    knowing 'an ACL is applied inbound' is a CONFIG-level fact, but it only WEAKLY
    suggests 'OSPF blocked by ACL' until we also know what's in the ACL."""
    return a if a.order <= b.order else b


_CONFIDENCE_LADDER: dict[tuple[EvidenceLevel, int], float] = {
    (EvidenceLevel.CONFIG, 1): 0.85,
    (EvidenceLevel.CONFIG, 2): 0.92,
    (EvidenceLevel.STRONG, 1): 0.55,
    (EvidenceLevel.STRONG, 2): 0.68,
    (EvidenceLevel.STRONG, 3): 0.72,
}
_WEAK_BASE = 0.30
_COMBINATION_BONUS = 0.05
_CONFIDENCE_CEIL = 0.95


def _confidence_for(level: EvidenceLevel, count: int, *, combo_bonus: bool) -> float:
    if level == EvidenceLevel.WEAK:
        base = _WEAK_BASE
    elif level == EvidenceLevel.CONFIG:
        base = _CONFIDENCE_LADDER[(level, 1)] if count <= 1 else _CONFIDENCE_LADDER[(level, 2)]
    else:  # STRONG
        if count <= 1:
            base = _CONFIDENCE_LADDER[(level, 1)]
        elif count == 2:
            base = _CONFIDENCE_LADDER[(level, 2)]
        else:
            base = _CONFIDENCE_LADDER[(level, 3)]

    if combo_bonus:
        base += _COMBINATION_BONUS
    return min(base, _CONFIDENCE_CEIL)


def _label(level: EvidenceLevel, confidence: float) -> str:
    if level == EvidenceLevel.CONFIG:
        return "Confirmed Cause"
    if level == EvidenceLevel.STRONG and confidence >= 0.50:
        return "Likely Cause"
    return "Possible Cause"


def _initial_classification(level: EvidenceLevel, confidence: float) -> str:
    if level == EvidenceLevel.CONFIG:
        return CLASSIFICATION_ROOT_CAUSE
    if level == EvidenceLevel.STRONG and confidence >= 0.55:
        return CLASSIFICATION_LIKELY_ROOT
    if level == EvidenceLevel.STRONG:
        return CLASSIFICATION_CONTRIBUTING
    return CLASSIFICATION_POSSIBLE


def score_faults(evidence: list[Evidence]) -> list[ScoredFault]:
    """Score every candidate fault from a flat evidence list."""
    # fault_name -> level -> [Evidence]
    bucket: dict[str, dict[EvidenceLevel, list[Evidence]]] = defaultdict(
        lambda: defaultdict(list)
    )
    present_tags = {ev.tag for ev in evidence}

    for ev in evidence:
        if ev.tag not in TAG_TO_FAULT:
            continue
        for fault_name, contribution_level in TAG_TO_FAULT[ev.tag]:
            effective = _level_min(ev.level, contribution_level)
            bucket[fault_name][effective].append(ev)

    # Apply combination upgrades.
    combo_bonused: set[str] = set()
    for tag_a, tag_b, fault_name, upgrade_to in COMBINATION_UPGRADES:
        if tag_a in present_tags and tag_b in present_tags and fault_name in bucket:
            # Synthesize a combination upgrade by adding evidence at upgrade level.
            # Use both originating evidence pieces as supporting evidence.
            uplift_evidence = [ev for ev in evidence if ev.tag in (tag_a, tag_b)][:2]
            for ev in uplift_evidence:
                if ev not in bucket[fault_name][upgrade_to]:
                    bucket[fault_name][upgrade_to].append(ev)
            combo_bonused.add(fault_name)

    results: list[ScoredFault] = []
    for fault_name, levels in bucket.items():
        fault = FAULT_CATALOG.get(fault_name)
        if fault is None:
            continue

        best = best_level(list(levels.keys()))
        count_at_best = len(levels[best])
        combo = fault_name in combo_bonused
        confidence = _confidence_for(best, count_at_best, combo_bonus=combo)
        all_evidence = [ev for lvl_list in levels.values() for ev in lvl_list]
        # Dedup while preserving order.
        seen_id: set[int] = set()
        unique_evidence: list[Evidence] = []
        for ev in all_evidence:
            if id(ev) in seen_id:
                continue
            seen_id.add(id(ev))
            unique_evidence.append(ev)

        evidence_summary = {lvl.value: len(items) for lvl, items in levels.items()}
        classification = _initial_classification(best, confidence)
        label = _label(best, confidence)

        results.append(
            ScoredFault(
                name=fault_name,
                category=fault.category.value,
                cause=fault.cause,
                verify=fault.verify,
                fix=fault.fix,
                confidence=confidence,
                best_evidence_level=best,
                classification=classification,
                label=label,
                supporting_evidence=unique_evidence,
                evidence_summary=evidence_summary,
            )
        )

    results.sort(
        key=lambda f: (f.best_evidence_level.order, f.confidence),
        reverse=True,
    )
    return results
