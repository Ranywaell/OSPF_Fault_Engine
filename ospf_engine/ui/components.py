"""Reusable Streamlit component renderers.

Every component takes ``st`` as the first argument so that
``ospf_engine.ui`` itself remains import-safe even if streamlit is not
installed (unit tests, CLI benchmark).
"""

from __future__ import annotations

import html

from ospf_engine.models import AnalysisResult, EvidenceLevel
from ospf_engine.models.analysis import (
    CLASSIFICATION_CONTRIBUTING,
    CLASSIFICATION_LIKELY_ROOT,
    CLASSIFICATION_POSSIBLE,
    CLASSIFICATION_ROOT_CAUSE,
    CLASSIFICATION_SIDE_EFFECT,
)


# Styling lookup tables ------------------------------------------------------

_LEVEL_PILL = {
    EvidenceLevel.CONFIG: ("CONFIG", "ev-pill ev-pill-config"),
    EvidenceLevel.STRONG: ("STRONG", "ev-pill ev-pill-strong"),
    EvidenceLevel.WEAK: ("WEAK", "ev-pill ev-pill-weak"),
}

_CLASS_PILL = {
    CLASSIFICATION_ROOT_CAUSE: ("ROOT CAUSE", "ev-pill ev-pill-root"),
    CLASSIFICATION_LIKELY_ROOT: ("LIKELY ROOT", "ev-pill ev-pill-likely"),
    CLASSIFICATION_CONTRIBUTING: ("CONTRIBUTING", "ev-pill ev-pill-likely"),
    CLASSIFICATION_SIDE_EFFECT: ("SIDE EFFECT", "ev-pill ev-pill-side"),
    CLASSIFICATION_POSSIBLE: ("POSSIBLE", "ev-pill ev-pill-poss"),
}

_FAULT_BORDER = {
    CLASSIFICATION_ROOT_CAUSE: "fe-fault-root",
    CLASSIFICATION_LIKELY_ROOT: "fe-fault-likely",
    CLASSIFICATION_CONTRIBUTING: "fe-fault-contrib",
    CLASSIFICATION_SIDE_EFFECT: "fe-fault-side",
    CLASSIFICATION_POSSIBLE: "fe-fault-possible",
}

_CONF_BAR_FILL = {
    EvidenceLevel.CONFIG: "conf-bar-fill conf-bar-fill-config",
    EvidenceLevel.STRONG: "conf-bar-fill conf-bar-fill-strong",
    EvidenceLevel.WEAK: "conf-bar-fill conf-bar-fill-weak",
}


def _pill(label: str, css_class: str) -> str:
    return f'<span class="{css_class}">{label}</span>'


def _esc(text: str) -> str:
    return html.escape(text or "")


# ---------------------------------------------------------------------------
# Top metrics
# ---------------------------------------------------------------------------


def render_top_metrics(st, analysis: AnalysisResult) -> None:
    top = analysis.top_fault
    config_count = sum(1 for e in analysis.evidence if e.level == EvidenceLevel.CONFIG)
    strong_count = sum(1 for e in analysis.evidence if e.level == EvidenceLevel.STRONG)
    weak_count = sum(1 for e in analysis.evidence if e.level == EvidenceLevel.WEAK)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Top fault", top.name if top else "-")
    c2.metric(
        "Confidence",
        f"{int(top.confidence * 100)}%" if top else "-",
        help="0-95% scale. CONFIG-tier evidence caps at 95%.",
    )
    c3.metric(
        "Evidence  C / S / W",
        f"{config_count} / {strong_count} / {weak_count}",
        help="Count of CONFIG / STRONG / WEAK evidence items extracted from the input.",
    )
    c4.metric(
        "Faults shown",
        str(len(analysis.ranked_faults)),
        help="After suppression of weaker alternatives explained by a confirmed cause.",
    )


# ---------------------------------------------------------------------------
# Diagnosis chain
# ---------------------------------------------------------------------------


def render_diagnosis_chain(st, analysis: AnalysisResult) -> None:
    if not analysis.diagnosis_chain:
        return
    st.subheader("Diagnosis chain")
    st.caption(
        "Step-by-step trace of how the engine reached its conclusion. "
        "Reads top-down."
    )
    for line in analysis.diagnosis_chain:
        st.markdown(
            f'<div class="diag-chain">{_esc(line)}</div>',
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Evidence panel
# ---------------------------------------------------------------------------


def render_evidence_panel(st, analysis: AnalysisResult) -> None:
    st.subheader("Evidence collected")
    if not analysis.evidence:
        st.info(
            "No evidence extracted. Make sure the uploaded files contain "
            "valid show-command output."
        )
        return

    st.caption(
        "Every observation is tagged with its strength: CONFIG = confirmed "
        "configuration conflict, STRONG = mechanism observed directly, "
        "WEAK = symptom only."
    )

    for level, label in (
        (EvidenceLevel.CONFIG, "CONFIG  -  confirms a cause"),
        (EvidenceLevel.STRONG, "STRONG  -  strong indicator"),
        (EvidenceLevel.WEAK, "WEAK    -  symptom only"),
    ):
        items = [e for e in analysis.evidence if e.level == level]
        if not items:
            continue
        with st.expander(
            f"{label}  ({len(items)} items)",
            expanded=(level == EvidenceLevel.CONFIG),
        ):
            for ev in items:
                pill_label, pill_class = _LEVEL_PILL[ev.level]
                st.markdown(
                    f"{_pill(pill_label, pill_class)} "
                    f"<code>{_esc(ev.tag)}</code> "
                    f"&nbsp;<span style='color:#8B949E'>from {_esc(ev.source)}</span>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"<div style='color:#C9D1D9; margin: 2px 0 10px 0; "
                    f"line-height:1.55'>{_esc(ev.detail)}</div>",
                    unsafe_allow_html=True,
                )


# ---------------------------------------------------------------------------
# Ranked faults (cards)
# ---------------------------------------------------------------------------


def render_ranked_faults(st, analysis: AnalysisResult) -> None:
    st.subheader("Root cause analysis")
    if not analysis.ranked_faults:
        st.error(
            "No faults matched the available evidence. Collect additional "
            "show-command outputs (especially `show ip ospf interface` and "
            "`show ip interface`) and try again."
        )
        return

    if analysis.uncertain and analysis.verification_note:
        st.warning(analysis.verification_note)

    st.caption(
        "Ranked top-down by tier-driven confidence. The colour stripe on the "
        "left of each card shows the classification."
    )

    for fault in analysis.ranked_faults:
        _render_fault_card(st, fault)


def _render_fault_card(st, fault) -> None:
    conf_pct = int(fault.confidence * 100)
    border_class = _FAULT_BORDER.get(fault.classification, "fe-fault-possible")
    cls_label, cls_class = _CLASS_PILL.get(
        fault.classification, ("UNKNOWN", "ev-pill ev-pill-poss")
    )
    lvl_label, lvl_class = _LEVEL_PILL[fault.best_evidence_level]
    bar_class = _CONF_BAR_FILL[fault.best_evidence_level]

    # The header card is rendered as raw HTML so the colour stripe + pills sit
    # on a single, clean row. The verification commands & fix go below using
    # native Streamlit widgets (they need st.code for syntax highlighting).
    st.markdown(
        f"""
        <div class="fe-fault {border_class}">
            <div class="fe-fault-head">
                <div class="fe-fault-name">{_esc(fault.name)}</div>
                <div class="fe-fault-pct">{conf_pct}%</div>
            </div>
            <div>
                {_pill(cls_label, cls_class)}
                {_pill(lvl_label, lvl_class)}
                <span class="fe-fault-meta">&nbsp; {_esc(fault.label)}</span>
            </div>
            <div class="conf-bar"><div class="{bar_class}" style="width:{conf_pct}%"></div></div>
            <div class="fe-fault-cause">{_esc(fault.cause)}</div>
            <div class="fe-fault-meta"><b>Category:</b> {_esc(fault.category)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("Verification & fix template", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Supporting evidence**")
            if not fault.supporting_evidence:
                st.caption("(none recorded)")
            for ev in fault.supporting_evidence[:6]:
                pl, pc = _LEVEL_PILL[ev.level]
                st.markdown(
                    f"{_pill(pl, pc)} {_esc(ev.detail)}",
                    unsafe_allow_html=True,
                )
        with col2:
            st.markdown("**Verification commands**")
            for cmd in fault.verify:
                st.code(cmd, language="text")
        st.markdown("**Safe fix template** &mdash; review before applying")
        st.code(fault.fix, language="text")


# ---------------------------------------------------------------------------
# Considered & ruled out
# ---------------------------------------------------------------------------


def render_ruled_out(st, analysis: AnalysisResult) -> None:
    if not analysis.considered_and_ruled_out:
        return
    with st.expander(
        f"Considered and ruled out  ({len(analysis.considered_and_ruled_out)})",
        expanded=False,
    ):
        st.caption(
            "Faults the engine considered but suppressed because a stronger, "
            "confirmed cause already explains the same symptoms."
        )
        for c in analysis.considered_and_ruled_out:
            st.markdown(f"**{_esc(c.name)}**")
            st.caption(c.reason)


# ---------------------------------------------------------------------------
# Fix path
# ---------------------------------------------------------------------------


def render_fix_path(st, analysis: AnalysisResult) -> None:
    if not analysis.fix_path:
        return
    st.subheader("Recommended fix path")
    st.caption(
        "Steps are ordered so prerequisites are repaired first "
        "(e.g. L2 native VLAN before L3 OSPF). Verify before applying."
    )
    for step in analysis.fix_path:
        cls_label, cls_class = _CLASS_PILL.get(
            step.classification, ("?", "ev-pill ev-pill-poss")
        )
        st.markdown(
            f"""
            <div class="fe-card" style="margin-bottom:8px">
                <div class="fe-fault-head">
                    <div class="fe-fault-name">Step {step.step} &mdash; {_esc(step.fault)}</div>
                    <div class="fe-fault-pct">{int(step.confidence * 100)}%</div>
                </div>
                <div>{_pill(cls_label, cls_class)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.code(step.fix, language="text")


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------


def render_timeline(st, log_text: str, root_fault: str | None) -> None:
    if not log_text.strip():
        return
    from ospf_engine.reporting.timeline import build_timeline

    timeline = build_timeline(log_text, root_fault or "")
    if not timeline.events:
        return
    st.subheader("Fault timeline")
    st.caption(
        "Built from `show logging`. The first event tagged [ROOT EVENT] is "
        "what the engine believes is the trigger."
    )
    st.graphviz_chart(timeline.dot_source)
    if timeline.root_event:
        st.markdown(
            f'<div class="fe-tip">'
            f'<span class="fe-tip-label">First root event</span>'
            f'<b>{_esc(timeline.root_event.timestamp)}</b> &mdash; '
            f'{_esc(timeline.root_event.message)}'
            f'</div>',
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Accuracy (benchmark mode)
# ---------------------------------------------------------------------------


def render_accuracy(st, accuracy) -> None:
    st.subheader("Accuracy vs. ground truth")
    st.caption(
        "Computed against the injected faults bundled with this scenario. "
        "Not a real-world claim."
    )
    c1, c2, c3 = st.columns(3)
    c1.metric("Precision", f"{int(accuracy.precision * 100)}%")
    c2.metric("Recall", f"{int(accuracy.recall * 100)}%")
    c3.metric("F1 score", f"{accuracy.f1:.2f}")
    if accuracy.true_positives:
        st.success(f"Correct: {', '.join(accuracy.true_positives)}")
    if accuracy.false_positives:
        st.warning(f"False positives: {', '.join(accuracy.false_positives)}")
    if accuracy.false_negatives:
        st.error(f"Missed: {', '.join(accuracy.false_negatives)}")
