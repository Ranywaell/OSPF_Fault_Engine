"""Plain-text operator report."""

from __future__ import annotations

from datetime import datetime

from ospf_engine.models import AnalysisResult, EvidenceLevel
from ospf_engine.reporting.accuracy import AccuracyMetrics


_DIVIDER_HEAVY = "=" * 70
_DIVIDER_LIGHT = "-" * 70


def _section(title: str) -> list[str]:
    return ["", _DIVIDER_HEAVY, f"  {title}", _DIVIDER_HEAVY]


def _subsection(title: str) -> list[str]:
    return ["", f"  --- {title} ---"]


def generate_text_report(
    analysis: AnalysisResult,
    scenario_name: str = "Unnamed",
    accuracy: AccuracyMetrics | None = None,
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    out: list[str] = []
    out.append(_DIVIDER_HEAVY)
    out.append("   OSPF FAULT ENGINE  -  OPERATOR REPORT  (CET361)")
    out.append(_DIVIDER_HEAVY)
    out.append(f"  Scenario : {scenario_name}")
    out.append(f"  Generated: {now}")
    out.append(
        "  Note     : This report is generated from text input only. "
        "No configuration is applied to any device."
    )

    # ---- Diagnosis chain ------------------------------------------------------
    out.extend(_section("DIAGNOSIS CHAIN"))
    if analysis.diagnosis_chain:
        for line in analysis.diagnosis_chain:
            out.append(f"  {line}")
    else:
        out.append("  (no diagnosis steps recorded)")

    # ---- Evidence ------------------------------------------------------------
    out.extend(_section("EVIDENCE COLLECTED"))
    by_level: dict[str, list] = {"CONFIG": [], "STRONG": [], "WEAK": []}
    for ev in analysis.evidence:
        by_level[ev.level.value].append(ev)
    for label, items in (
        ("CONFIG  - confirms a cause", by_level["CONFIG"]),
        ("STRONG  - strong indicator", by_level["STRONG"]),
        ("WEAK    - symptom only", by_level["WEAK"]),
    ):
        out.extend(_subsection(f"{label}  ({len(items)} items)"))
        if not items:
            out.append("    (none)")
            continue
        for ev in items:
            out.append(f"    [{ev.tag}] from {ev.source}")
            out.append(f"        {ev.detail}")

    # ---- Ranked faults --------------------------------------------------------
    out.extend(_section("ROOT CAUSE ANALYSIS"))
    if not analysis.ranked_faults:
        out.append("  No fault candidates matched the available evidence.")
    else:
        for i, fault in enumerate(analysis.ranked_faults, start=1):
            conf = int(fault.confidence * 100)
            out.extend(
                _subsection(
                    f"#{i}  [{fault.classification}]  {fault.name}  "
                    f"-  {conf}% confidence  ({fault.best_evidence_level.value})"
                )
            )
            out.append(f"    Category : {fault.category}")
            out.append(f"    Label    : {fault.label}")
            out.append(f"    Cause    : {fault.cause}")
            if fault.supporting_evidence:
                out.append("    Evidence :")
                for ev in fault.supporting_evidence[:5]:
                    out.append(f"      - [{ev.level.value}] {ev.detail}")

    # ---- Considered and ruled out --------------------------------------------
    if analysis.considered_and_ruled_out:
        out.extend(_section("CONSIDERED AND RULED OUT"))
        for c in analysis.considered_and_ruled_out:
            out.append(f"  - {c.name}")
            out.append(f"      reason: {c.reason}")

    # ---- Fix path ------------------------------------------------------------
    out.extend(_section("RECOMMENDED FIX PATH (verify before applying)"))
    if not analysis.fix_path:
        out.append("  (no fix steps - no faults detected with sufficient confidence)")
    for step in analysis.fix_path:
        out.append("")
        out.append(
            f"  Step {step.step}  [{step.classification}]  {step.fault}  "
            f"-  {int(step.confidence * 100)}%"
        )
        out.append("    Verification commands:")
        for cmd in step.verify:
            out.append(f"      > {cmd}")
        out.append("    Safe fix template:")
        for line in step.fix.splitlines():
            out.append(f"      {line}")

    # ---- Accuracy ------------------------------------------------------------
    if accuracy is not None:
        out.extend(_section("ACCURACY VS. GROUND TRUTH"))
        out.append(f"  Precision : {int(accuracy.precision * 100)}%")
        out.append(f"  Recall    : {int(accuracy.recall * 100)}%")
        out.append(f"  F1 score  : {accuracy.f1:.2f}")
        if accuracy.true_positives:
            out.append(f"  Correct   : {', '.join(accuracy.true_positives)}")
        if accuracy.false_positives:
            out.append(f"  False+    : {', '.join(accuracy.false_positives)}")
        if accuracy.false_negatives:
            out.append(f"  Missed    : {', '.join(accuracy.false_negatives)}")

    # ---- Summary -------------------------------------------------------------
    out.extend(_section("SUMMARY"))
    out.append(f"  Faults detected (after suppression): {len(analysis.ranked_faults)}")
    if analysis.top_fault is not None:
        out.append(f"  Top fault   : {analysis.top_fault.name}")
        out.append(f"  Confidence  : {int(analysis.top_fault.confidence * 100)}%")
        out.append(f"  Evidence    : {analysis.top_fault.best_evidence_level.value}")
    if analysis.uncertain:
        out.append("  Status      : UNCERTAIN  -  collect more evidence before acting.")
    else:
        out.append(
            "  Status      : Top fault is supported by a CONFIG-tier configuration "
            "conflict. Verify with the listed commands before applying any fix."
        )

    out.append("")
    out.append(_DIVIDER_HEAVY)
    out.append("  END OF REPORT")
    out.append(_DIVIDER_HEAVY)

    return "\n".join(out)
