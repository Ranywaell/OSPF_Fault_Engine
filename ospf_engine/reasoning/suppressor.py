"""Suppress alternatives that are fully explained by a CONFIG-level cause.

This step eliminates the noise the legacy engine produced (Scenario 1 / 2 / 3
all surfaced OSPF Area, Timer, and Hellos-Blocked-by-ACL even though only one
was real). Two kinds of suppression run here:

1. **Weak suppression (always safe).** If a fault Y has only WEAK evidence AND
   a CONFIG-level fault X explains Y's symptoms, drop Y.

2. **Ambiguous-tag suppression.** Some evidence tags - notably broad syslog
   messages like ``%OSPF-4-ERRRCV: Mismatched hello parameters`` - could
   indicate any of several faults (area / timer / MTU). When a CONFIG cause
   X is confirmed AND fault Y is in EXPLAINS[X] AND ALL of Y's supporting
   evidence comes from such ambiguous tags, drop Y.
"""

from __future__ import annotations

from ospf_engine.models import EvidenceLevel, ScoredFault
from ospf_engine.models.analysis import ConsideredFault
from ospf_engine.reasoning.side_effects import EXPLAINS
from ospf_engine.reasoning.tag_map import TAG_TO_FAULT


def _compute_ambiguous_tags() -> set[str]:
    """A tag is *ambiguous* when its mapping in TAG_TO_FAULT contributes
    STRONG-or-higher to two or more competing faults. Such evidence is
    informative ('something is wrong with OSPF parameters') but does not
    pinpoint *which* parameter."""
    out: set[str] = set()
    for tag, contributions in TAG_TO_FAULT.items():
        strong_or_above = sum(
            1 for _f, lvl in contributions if lvl.order >= EvidenceLevel.STRONG.order
        )
        if strong_or_above >= 2:
            out.add(tag)
    return out


_AMBIGUOUS_TAGS = _compute_ambiguous_tags()


def _tags_supporting_at_best_level(fault: ScoredFault) -> set[str]:
    """Return the evidence tags that lift this fault to its current best level.

    Lower-level supporting evidence (e.g. a generic 'OSPF adjacency went DOWN'
    syslog that contributes WEAK to many faults) does not count - only tags
    whose effective contribution to *this* fault matches its best level.
    """
    out: set[str] = set()
    best_order = fault.best_evidence_level.order
    for ev in fault.supporting_evidence:
        for fname, contribution_level in TAG_TO_FAULT.get(ev.tag, ()):
            if fname != fault.name:
                continue
            effective_order = min(ev.level.order, contribution_level.order)
            if effective_order >= best_order:
                out.add(ev.tag)
                break
    return out


def suppress_weak_alternatives(
    ranked: list[ScoredFault],
) -> tuple[list[ScoredFault], list[ConsideredFault]]:
    confirmed = [f for f in ranked if f.best_evidence_level == EvidenceLevel.CONFIG]
    if not confirmed:
        return ranked, []

    explained: dict[str, str] = {}
    for c in confirmed:
        for explained_name in EXPLAINS.get(c.name, set()):
            explained.setdefault(explained_name, c.name)

    kept: list[ScoredFault] = []
    ruled_out: list[ConsideredFault] = []

    for fault in ranked:
        if fault.best_evidence_level == EvidenceLevel.CONFIG:
            kept.append(fault)
            continue

        if fault.name not in explained:
            kept.append(fault)
            continue

        explainer = explained[fault.name]

        if fault.best_evidence_level == EvidenceLevel.WEAK:
            ruled_out.append(
                ConsideredFault(
                    name=fault.name,
                    reason=(
                        f"Suppressed: only weak symptom-level evidence, and the symptoms "
                        f"are fully explained by the confirmed cause '{explainer}'."
                    ),
                )
            )
            continue

        # STRONG and explained: only suppress if every tag that supports this
        # fault at its best level is an ambiguous shared-symptom tag.
        ev_tags = _tags_supporting_at_best_level(fault)
        if ev_tags and ev_tags.issubset(_AMBIGUOUS_TAGS):
            ruled_out.append(
                ConsideredFault(
                    name=fault.name,
                    reason=(
                        f"Suppressed: supporting evidence ({', '.join(sorted(ev_tags))}) is "
                        f"ambiguous and could indicate several faults. The confirmed cause "
                        f"'{explainer}' fully accounts for it."
                    ),
                )
            )
            continue

        kept.append(fault)

    return kept, ruled_out
