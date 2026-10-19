"""End-to-end analysis pipeline: parsed evidence + facts -> AnalysisResult.

This is the SINGLE code path used by both the Streamlit UI and the CLI
benchmark. It is deliberately a pure function: feed it parser output, get
back a typed AnalysisResult.
"""

from __future__ import annotations

from ospf_engine.models import AnalysisResult, Evidence, EvidenceLevel
from ospf_engine.parsers.dispatcher import ParseResult
from ospf_engine.reasoning.classifier import classify
from ospf_engine.reasoning.correlator import correlate
from ospf_engine.reasoning.fix_planner import build_fix_path
from ospf_engine.reasoning.scorer import score_faults
from ospf_engine.reasoning.suppressor import suppress_weak_alternatives


_VERIFICATION_NOTE = (
    "WARNING: only symptom-level evidence is available - the root cause cannot be confirmed. "
    "Collect 'show ip ospf interface', 'show access-lists', 'show ip interface', and "
    "'show interfaces trunk' on every device on the affected path before drawing conclusions."
)


def _build_diagnosis_chain(
    correlator_evidence: list[Evidence],
    parser_evidence: list[Evidence],
    ranked: list,
) -> list[str]:
    """Produce a short narrative explaining how the engine reached its conclusion."""
    chain: list[str] = []

    correlator_config = [e for e in correlator_evidence if e.level == EvidenceLevel.CONFIG]
    if correlator_config:
        chain.append(
            f"Cross-device correlation produced {len(correlator_config)} CONFIG-level "
            "finding(s) - these are concrete configuration conflicts, not just symptoms."
        )
        for ev in correlator_config[:3]:
            chain.append(f"  - {ev.detail}")

    parser_config = [
        e for e in parser_evidence if e.level == EvidenceLevel.CONFIG and e.source != "correlator"
    ]
    if parser_config:
        chain.append(
            f"Parsers extracted {len(parser_config)} CONFIG-level finding(s) directly from "
            "device output."
        )

    if ranked:
        top = ranked[0]
        chain.append(
            f"Top fault selected: '{top.name}' (level={top.best_evidence_level.value}, "
            f"confidence={int(top.confidence * 100)}%)."
        )
    else:
        chain.append("No fault candidates matched the available evidence.")

    return chain


def analyze(parse_result: ParseResult) -> AnalysisResult:
    """Single entry point.

    Parameters
    ----------
    parse_result:
        The output of :func:`ospf_engine.parsers.parse_files`.
    """
    correlator_evidence = correlate(parse_result.facts)

    # Combine parser evidence with correlator evidence, deduplicating by tag+detail.
    seen: set[tuple[str, str]] = set()
    combined: list[Evidence] = []
    for ev in list(parse_result.evidence) + list(correlator_evidence):
        key = (ev.tag, ev.detail[:80])
        if key in seen:
            continue
        seen.add(key)
        combined.append(ev)

    ranked = score_faults(combined)
    classified = classify(ranked)
    kept, ruled_out = suppress_weak_alternatives(classified)
    fix_path = build_fix_path(kept)

    uncertain = bool(kept) and kept[0].best_evidence_level == EvidenceLevel.WEAK

    return AnalysisResult(
        evidence=combined,
        ranked_faults=kept,
        fix_path=fix_path,
        considered_and_ruled_out=ruled_out,
        uncertain=uncertain,
        verification_note=_VERIFICATION_NOTE if uncertain else None,
        diagnosis_chain=_build_diagnosis_chain(correlator_evidence, parse_result.evidence, kept),
    )
