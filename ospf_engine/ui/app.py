"""Streamlit page wiring.

The dashboard has four modes:

    Home              - hero, "how to use" guide, what the engine detects
    Run a Scenario    - pick one of the 8 bundled scenarios + ground-truth comparison
    Upload Files      - drop your own .txt files (single or combined dump)
    Run All Scenarios - tabular benchmark across the whole suite

Mode is held in `st.session_state["mode"]` so the Home page CTAs can switch
to a working mode and Streamlit reruns naturally.
"""

from __future__ import annotations


_MODE_HOME = "Home"
_MODE_SCENARIO = "Run a Scenario"
_MODE_UPLOAD = "Upload Files"
_MODE_RUN_ALL = "Run All Scenarios"
_MODES = [_MODE_HOME, _MODE_SCENARIO, _MODE_UPLOAD, _MODE_RUN_ALL]


# ---------------------------------------------------------------------------
# Navigation callbacks
# ---------------------------------------------------------------------------
# Streamlit will raise StreamlitAPIException ("st.session_state.mode cannot be
# modified after the widget with key 'mode' is instantiated") if you write to
# st.session_state["mode"] in the body of a button click handler, because the
# sidebar radio with key="mode" already created the binding for THIS run.
#
# The supported pattern is a callback passed to `on_click=` - callbacks run at
# the *start* of the next rerun, BEFORE widgets are re-instantiated, so writing
# to session_state from inside a callback is safe.


def _go_to_mode(target: str) -> None:
    import streamlit as st

    st.session_state["mode"] = target


def _go_to_scenario(scenario_name: str) -> None:
    import streamlit as st

    st.session_state["mode"] = _MODE_SCENARIO
    st.session_state["scenario_pick"] = scenario_name


def render() -> None:
    """Render the full dashboard. Imports streamlit lazily so the package can
    still be imported in environments where streamlit isn't installed."""
    import streamlit as st

    from ospf_engine import analyze, parse_files
    from ospf_engine.reporting.accuracy import check_accuracy
    from ospf_engine.reporting.text_report import generate_text_report
    from ospf_engine.scenarios import ALL_SCENARIOS
    from ospf_engine.ui import components, theme

    st.set_page_config(
        page_title="OSPF Fault Engine - CET361",
        page_icon=":satellite:",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    theme.inject(st)

    if "mode" not in st.session_state:
        st.session_state["mode"] = _MODE_HOME

    _render_sidebar(st)

    mode = st.session_state["mode"]
    if mode == _MODE_HOME:
        _render_home(st, ALL_SCENARIOS)
    elif mode == _MODE_SCENARIO:
        _render_scenario_mode(
            st, components, analyze, parse_files,
            check_accuracy, generate_text_report, ALL_SCENARIOS,
        )
    elif mode == _MODE_UPLOAD:
        _render_upload_mode(
            st, components, analyze, parse_files, generate_text_report,
        )
    else:
        _render_run_all_mode(
            st, analyze, parse_files, check_accuracy, ALL_SCENARIOS,
        )

    _render_footer(st)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


def _render_sidebar(st) -> None:
    with st.sidebar:
        st.title("OSPF Fault Engine")
        st.markdown(
            '<p class="sb-tagline">CET361 - Routing &amp; Switching - Project 2</p>',
            unsafe_allow_html=True,
        )

        st.radio(
            "Navigate",
            _MODES,
            key="mode",
            label_visibility="collapsed",
        )

        st.markdown("---")
        st.markdown("**Evidence levels**")
        st.markdown(
            '<span class="ev-pill ev-pill-config">CONFIG</span> '
            "&nbsp;Confirmed configuration conflict",
            unsafe_allow_html=True,
        )
        st.markdown(
            '<span class="ev-pill ev-pill-strong">STRONG</span> '
            "&nbsp;Direct mechanism observed",
            unsafe_allow_html=True,
        )
        st.markdown(
            '<span class="ev-pill ev-pill-weak">WEAK</span> '
            "&nbsp;Symptom only, not proof",
            unsafe_allow_html=True,
        )

        st.markdown("---")
        st.markdown("**Classification**")
        st.markdown(
            '<span class="ev-pill ev-pill-root">ROOT CAUSE</span> '
            '&nbsp;<span class="ev-pill ev-pill-side">SIDE EFFECT</span>',
            unsafe_allow_html=True,
        )

        st.markdown("---")
        st.caption(
            "The engine reads text only. It never applies any configuration "
            "to a real device."
        )


# ---------------------------------------------------------------------------
# Home page
# ---------------------------------------------------------------------------


def _render_home(st, ALL_SCENARIOS) -> None:
    n_scenarios = len(ALL_SCENARIOS)

    st.markdown(
        f"""
        <div class="fe-hero">
            <div class="fe-hero-eyebrow">CET361 - PROJECT 2</div>
            <div class="fe-hero-title">OSPF Fault Engine</div>
            <div class="fe-hero-sub">
                A rule-based troubleshooting engine for Routing &amp; Switching
                labs. It reads simulated Cisco-style CLI output and ranks the
                most likely <b>root cause</b> across OSPF, STP, VLAN, ACL,
                DHCP relay and DNS. It also distinguishes the <b>main trigger</b>
                from <b>side-effects</b> and prints a safe, dependency-ordered
                fix path.
            </div>
            <div class="fe-hero-row">
                <div class="fe-hero-stat">
                    <div class="fe-hero-stat-label">Bundled scenarios</div>
                    <div class="fe-hero-stat-value">{n_scenarios}</div>
                </div>
                <div class="fe-hero-stat">
                    <div class="fe-hero-stat-label">Detectable faults</div>
                    <div class="fe-hero-stat-value">12</div>
                </div>
                <div class="fe-hero-stat">
                    <div class="fe-hero-stat-label">Evidence tiers</div>
                    <div class="fe-hero-stat-value">3</div>
                </div>
                <div class="fe-hero-stat">
                    <div class="fe-hero-stat-label">Pipeline stages</div>
                    <div class="fe-hero-stat-value">7</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---- How to use - three step cards ---------------------------------
    st.subheader("How to use it")
    st.caption("Three workflows, pick whichever fits what you're trying to do.")

    c1, c2, c3 = st.columns(3, gap="medium")
    with c1:
        _step_card(
            st,
            num="1",
            title="Try a sample scenario",
            body=(
                "Open one of the 8 pre-built scenarios. Each one ships with "
                "fake Cisco output, syslog, the injected faults, and the "
                "expected top fault, so you can compare the engine's answer "
                "to the ground truth."
            ),
            cta_label="Open a scenario",
            cta_target=_MODE_SCENARIO,
        )
    with c2:
        _step_card(
            st,
            num="2",
            title="Upload your own files",
            body=(
                "Collected `show ...` output from Packet Tracer or GNS3? "
                "Drop the .txt files (one per command, or one combined "
                "dump). The dispatcher routes each file to the right "
                "parser automatically."
            ),
            cta_label="Upload files",
            cta_target=_MODE_UPLOAD,
        )
    with c3:
        _step_card(
            st,
            num="3",
            title="Benchmark every scenario",
            body=(
                "Run the engine across every bundled scenario at once. "
                "You get a precision / recall / F1 table and an average "
                "score across the included benchmark only."
            ),
            cta_label="Run all scenarios",
            cta_target=_MODE_RUN_ALL,
        )

    # ---- Pro tip --------------------------------------------------------
    st.markdown(
        """
        <div class="fe-tip">
            <span class="fe-tip-label">Tip</span>
            For your CET361 demo open <b>Scenario 8 - Multi-Fault Demo</b>.
            Four independent faults are hidden in one capture and the engine
            has to identify all four root causes while suppressing the
            side-effects.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("")  # spacing
    st.button(
        "Open Scenario 8 (main demo)",
        type="primary",
        on_click=_go_to_scenario,
        args=("Scenario 8 - Multi-Fault Demo (4 hidden faults)",),
    )

    # ---- What the engine detects ---------------------------------------
    st.subheader("What the engine detects")
    st.markdown(
        """
        <div class="fe-cat-grid">
            <div class="fe-cat">
                <div class="fe-cat-name">OSPF</div>
                <div class="fe-cat-list">
                    Area mismatch &middot; Hello/Dead timer mismatch &middot;
                    Hellos blocked by ACL &middot; Network type mismatch &middot;
                    MTU mismatch (EXSTART/EXCHANGE) &middot; Duplicate router-ID
                </div>
            </div>
            <div class="fe-cat">
                <div class="fe-cat-name">ACL</div>
                <div class="fe-cat-list">
                    ACL applied in the wrong direction (in vs out swapped)
                </div>
            </div>
            <div class="fe-cat">
                <div class="fe-cat-name">STP / VLAN</div>
                <div class="fe-cat-list">
                    Native VLAN mismatch on trunk &middot;
                    STP topology change / wrong root bridge
                </div>
            </div>
            <div class="fe-cat">
                <div class="fe-cat-name">DHCP</div>
                <div class="fe-cat-list">
                    Missing <code>ip helper-address</code> &middot;
                    DHCP server unreachable
                </div>
            </div>
            <div class="fe-cat">
                <div class="fe-cat-name">DNS</div>
                <div class="fe-cat-list">
                    Isolated DNS resolution failure
                    (PC can ping by IP, <code>nslookup</code> fails)
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---- How does it work? ---------------------------------------------
    st.subheader("How does it work?")
    st.markdown(
        """
        <div class="fe-card">
            <div class="fe-card-body">
                <ol style="margin:0; padding-left: 1.2rem;">
                    <li><b>Parse</b> each <code>show ...</code> output into typed
                        evidence and structured topology facts (interfaces,
                        VLANs, ACL bindings, helpers, etc.).</li>
                    <li><b>Correlate</b> facts across devices on the same
                        link/trunk/subnet so a mismatch is only flagged when
                        <i>both ends disagree</i> - the same deduction a
                        network engineer makes by hand.</li>
                    <li><b>Score</b> every candidate fault on a tier-driven
                        confidence ladder (CONFIG &gt; STRONG &gt; WEAK).</li>
                    <li><b>Classify</b> each result as ROOT_CAUSE, LIKELY_ROOT,
                        CONTRIBUTING, SIDE_EFFECT or POSSIBLE.</li>
                    <li><b>Suppress</b> weaker alternatives that a confirmed
                        cause already explains - this is what turns a list of
                        symptoms into ranked root causes.</li>
                    <li><b>Plan</b> a dependency-ordered fix path so L2
                        prerequisites get repaired before L3.</li>
                    <li><b>Render</b> the diagnosis chain, the timeline, the
                        operator report and the verification commands. No
                        configuration is ever applied.</li>
                </ol>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _step_card(st, num: str, title: str, body: str, cta_label: str, cta_target: str) -> None:
    st.markdown(
        f"""
        <div class="fe-step">
            <div class="fe-step-num">{num}</div>
            <div class="fe-step-title">{title}</div>
            <div class="fe-step-body">{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.button(
        cta_label,
        key=f"home_cta_{num}",
        use_container_width=True,
        on_click=_go_to_mode,
        args=(cta_target,),
    )


# ---------------------------------------------------------------------------
# Page header (used on every non-Home page)
# ---------------------------------------------------------------------------


def _page_header(st, eyebrow: str, title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="fe-hero">
            <div class="fe-hero-eyebrow">{eyebrow}</div>
            <div class="fe-hero-title">{title}</div>
            <div class="fe-hero-sub">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _gather_log_text(files: dict[str, str]) -> str:
    """Concatenate any file whose name suggests it carries syslog content."""
    return "\n".join(
        content
        for name, content in files.items()
        if "log" in name.lower() or "syslog" in name.lower()
    )


# ---------------------------------------------------------------------------
# Mode: Run a Scenario
# ---------------------------------------------------------------------------


def _render_scenario_mode(
    st, components, analyze, parse_files,
    check_accuracy, generate_text_report, ALL_SCENARIOS,
):
    _page_header(
        st,
        eyebrow="MODE 01",
        title="Run a sample scenario",
        subtitle=(
            "Pick a pre-built scenario, see the injected faults, then run "
            "the engine and compare the diagnosis to the ground truth."
        ),
    )

    scenario_names = list(ALL_SCENARIOS.keys())
    default_idx = 0
    preselect = st.session_state.pop("scenario_pick", None)
    if preselect and preselect in scenario_names:
        default_idx = scenario_names.index(preselect)

    name = st.selectbox(
        "Scenario", scenario_names, index=default_idx,
        help="Each scenario carries simulated CLI output plus the list of injected faults.",
    )
    scenario = ALL_SCENARIOS[name]

    # --- Scenario summary card -----------------------------------------
    is_demo = "Multi-Fault" in name or "8 -" in name
    badge = (
        '<span class="ev-pill ev-pill-config">MAIN DEMO</span>'
        if is_demo else ""
    )
    st.markdown(
        f"""
        <div class="fe-card">
            <div class="fe-card-title">{name} {badge}</div>
            <div class="fe-card-sub">{scenario.description}</div>
            <div class="fe-card-body">
                <b>Injected faults:</b> {", ".join(scenario.ground_truth)}<br>
                <b>Expected top fault:</b> {scenario.expected_top}<br>
                <b>Files in this scenario:</b> {len(scenario.files)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("View raw input files", expanded=False):
        tab_objs = st.tabs(list(scenario.files.keys()))
        for tab, (fname, content) in zip(tab_objs, scenario.files.items()):
            with tab:
                st.code(content.strip() or "(empty)", language="text")

    cta_col, _ = st.columns([1, 4])
    with cta_col:
        run = st.button("Run analysis", type="primary", use_container_width=True)

    if not run:
        st.markdown(
            '<div class="fe-tip">'
            '<span class="fe-tip-label">Hint</span>'
            "Click <b>Run analysis</b> to feed every file in this scenario "
            "to the engine and see the diagnosis chain, ranked faults, "
            "fix path and timeline."
            "</div>",
            unsafe_allow_html=True,
        )
        return

    parse_result = parse_files(scenario.files)
    analysis = analyze(parse_result)
    accuracy = check_accuracy(analysis, scenario.ground_truth)

    components.render_top_metrics(st, analysis)
    components.render_accuracy(st, accuracy)
    st.divider()

    components.render_diagnosis_chain(st, analysis)
    components.render_evidence_panel(st, analysis)
    components.render_ranked_faults(st, analysis)
    components.render_ruled_out(st, analysis)
    components.render_fix_path(st, analysis)

    log_text = _gather_log_text(scenario.files)
    components.render_timeline(
        st, log_text, analysis.top_fault.name if analysis.top_fault else None,
    )

    st.divider()
    st.subheader("Operator report")
    report_text = generate_text_report(analysis, scenario.name, accuracy=accuracy)
    cd1, cd2 = st.columns([1, 3])
    cd1.download_button(
        "Download .txt report",
        data=report_text,
        file_name=f"fault_report_{scenario.name.replace(' ', '_')}.txt",
        mime="text/plain",
        use_container_width=True,
    )
    with st.expander("Preview the operator report"):
        st.text(report_text)


# ---------------------------------------------------------------------------
# Mode: Upload Files
# ---------------------------------------------------------------------------


def _render_upload_mode(st, components, analyze, parse_files, generate_text_report):
    _page_header(
        st,
        eyebrow="MODE 02",
        title="Analyse your own files",
        subtitle=(
            "Drop the <code>show ...</code> output you collected from Packet "
            "Tracer or GNS3. The dispatcher routes each file to the right "
            "parser automatically. Filenames containing keywords like "
            "<code>ospf_neighbor</code> or <code>trunk</code> route faster, "
            "but content sniffing also works."
        ),
    )

    uploaded = st.file_uploader(
        "Drop one or more .txt files here",
        type=["txt"],
        accept_multiple_files=True,
        help=(
            "One file per show command works best. A single combined dump "
            "with banners like '----- show ip ospf interface -----' or "
            "natural Cisco prompts ('R1#show ...') also works."
        ),
    )
    scenario_name = st.text_input(
        "Capture label",
        value="My Topology",
        help="Used in the downloaded operator report.",
    )

    if not uploaded:
        st.markdown(
            '<div class="fe-tip">'
            '<span class="fe-tip-label">No files yet</span>'
            "Upload at least one <code>show ...</code> output to start. "
            "Below is the recommended set of commands to collect."
            "</div>",
            unsafe_allow_html=True,
        )
        with st.expander("Recommended commands to collect", expanded=False):
            st.code(
                "terminal length 0\n"
                "show ip ospf neighbor detail\n"
                "show ip ospf interface\n"
                "show ip route\n"
                "show access-lists\n"
                "show ip interface gigabitEthernet 0/0\n"
                "show ip interface gigabitEthernet 0/1\n"
                "show interfaces trunk\n"
                "show vlan brief\n"
                "show spanning-tree\n"
                "show ip dhcp binding\n"
                "show logging\n"
                "! and on the PC:\n"
                "ipconfig /all\n"
                "ping <server-ip>\n"
                "nslookup <server-name>",
                language="text",
            )
        return

    files = {f.name: f.read().decode(errors="replace") for f in uploaded}
    st.success(f"Loaded {len(files)} file(s).")

    parse_result = parse_files(files)
    analysis = analyze(parse_result)
    log_text = _gather_log_text(files)

    components.render_top_metrics(st, analysis)
    st.divider()

    components.render_diagnosis_chain(st, analysis)
    components.render_evidence_panel(st, analysis)
    components.render_ranked_faults(st, analysis)
    components.render_ruled_out(st, analysis)
    components.render_fix_path(st, analysis)
    components.render_timeline(
        st, log_text, analysis.top_fault.name if analysis.top_fault else None,
    )

    st.divider()
    st.subheader("Operator report")
    report_text = generate_text_report(analysis, scenario_name)
    cd1, cd2 = st.columns([1, 3])
    cd1.download_button(
        "Download .txt report",
        data=report_text,
        file_name=f"fault_report_{scenario_name.replace(' ', '_')}.txt",
        mime="text/plain",
        use_container_width=True,
    )
    with st.expander("Preview the operator report"):
        st.text(report_text)


# ---------------------------------------------------------------------------
# Mode: Run All Scenarios
# ---------------------------------------------------------------------------


def _render_run_all_mode(st, analyze, parse_files, check_accuracy, ALL_SCENARIOS):
    _page_header(
        st,
        eyebrow="MODE 03",
        title="Benchmark every scenario",
        subtitle=(
            "Runs the engine across every bundled benchmark scenario and "
            "computes precision, recall and F1 against ground truth. The "
            "average score below is measured on the bundled benchmark only."
        ),
    )

    if not st.button("Run all scenarios", type="primary"):
        st.markdown(
            '<div class="fe-tip">'
            '<span class="fe-tip-label">Ready</span>'
            f"Click the button above to evaluate the engine across all "
            f"<b>{len(ALL_SCENARIOS)}</b> scenarios."
            "</div>",
            unsafe_allow_html=True,
        )
        return

    rows = []
    total_f1 = 0.0
    progress = st.progress(0.0, text="Starting...")
    items = list(ALL_SCENARIOS.items())
    for i, (name, scenario) in enumerate(items, start=1):
        progress.progress(i / len(items), text=f"Running: {name}")
        parse_result = parse_files(scenario.files)
        analysis = analyze(parse_result)
        accuracy = check_accuracy(analysis, scenario.ground_truth)
        total_f1 += accuracy.f1
        top = analysis.top_fault
        rows.append(
            {
                "Scenario": name,
                "Expected top": scenario.expected_top,
                "Detected top": top.name if top else "-",
                "Top OK": "yes" if top and top.name == scenario.expected_top else "no",
                "Evidence": top.best_evidence_level.value if top else "-",
                "Precision": f"{int(accuracy.precision * 100)}%",
                "Recall": f"{int(accuracy.recall * 100)}%",
                "F1": f"{accuracy.f1:.2f}",
            }
        )
    progress.empty()

    avg = total_f1 / len(rows) if rows else 0
    correct = sum(1 for r in rows if r["Top OK"] == "yes")

    c1, c2, c3 = st.columns(3)
    c1.metric("Scenarios", len(rows))
    c2.metric("Top-fault accuracy", f"{correct}/{len(rows)}")
    c3.metric("Average F1 (benchmark only)", f"{avg:.2f}")

    st.divider()
    st.table(rows)
    st.caption(
        "Note: the F1 score is measured on the bundled benchmark scenarios "
        "only. New topologies will need new scenarios and may expose new "
        "failure modes."
    )


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------


def _render_footer(st) -> None:
    st.markdown(
        '<div class="fe-footer">'
        "OSPF Fault Engine &middot; CET361 Routing &amp; Switching &middot; "
        "Project 2 &middot; Reads text input only - no configuration is applied."
        "</div>",
        unsafe_allow_html=True,
    )
