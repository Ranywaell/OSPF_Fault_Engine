# CET361 - OSPF Fault Troubleshooting Engine

> **Project 2 - Routing & Switching**
> A rule-based troubleshooting engine that reads simulated Cisco-style CLI
> output and ranks the most likely **root cause** of an OSPF / STP / VLAN /
> ACL / DHCP / DNS failure, distinguishes it from secondary symptoms, and
> prints safe verification and corrective steps. Configurations are
> **never** applied automatically; the engine only reads text and reports.

---

## Table of contents

1. [What the engine does](#what-the-engine-does)
2. [Quick start](#quick-start)
3. [Architecture](#architecture)
4. [Evidence model](#evidence-model)
5. [Benchmark results](#benchmark-results)
6. [Running the tests](#running-the-tests)
7. [Packet Tracer topology guide](#packet-tracer-topology-guide)
8. [Fault injection scenarios](#fault-injection-scenarios)
9. [How to discuss this in CET361](#how-to-discuss-this-in-cet361)

---

## What the engine does

The engine accepts the kind of CLI output an operator collects during
troubleshooting:

* `show ip ospf neighbor [detail]`
* `show ip ospf interface`
* `show ip route`
* `show ip interface <if>`
* `show access-lists`
* `show interfaces trunk`
* `show spanning-tree`
* `show ip dhcp binding`
* `show logging`
* PC-side `ipconfig`, `ping`, `nslookup`

It then:

1. **Parses** each output into typed evidence and structured topology facts.
2. **Correlates** facts across devices on the same link/trunk/subnet -
   the right way to detect mismatches that no single-router parser can see.
3. **Scores** every candidate fault on a tier-driven confidence ladder
   (WEAK / STRONG / CONFIG).
4. **Classifies** results as ROOT_CAUSE, LIKELY_ROOT_CAUSE, CONTRIBUTING_FACTOR,
   SIDE_EFFECT, or POSSIBLE_CAUSE.
5. **Suppresses** weak alternatives that are fully explained by a confirmed
   cause (so an "OSPF Area Mismatch" symptom does not show up alongside a
   confirmed "Hellos Blocked by ACL").
6. **Plans** a dependency-ordered fix path (e.g. fix native VLAN before STP).
7. **Renders** an operator-friendly Streamlit dashboard, a syslog timeline,
   and a downloadable text report.

### Faults the engine can identify

| Category    | Fault                                |
|-------------|--------------------------------------|
| OSPF        | Area mismatch                        |
| OSPF        | Hello / dead timer mismatch          |
| OSPF        | Hellos blocked by ACL                |
| OSPF        | Network type mismatch                |
| OSPF        | MTU mismatch (EXSTART/EXCHANGE hang) |
| OSPF        | Duplicate router-ID                  |
| ACL         | Wrong direction (in/out swapped)     |
| STP / VLAN  | Native VLAN mismatch on trunk        |
| STP / VLAN  | Topology change / wrong root bridge  |
| DHCP        | Missing helper-address               |
| DHCP        | Server unreachable                   |
| DNS         | Isolated DNS resolution failure      |

---

## Quick start

```bash
pip install -r requirements.txt

# Run the Streamlit dashboard
streamlit run streamlit_app.py

# OR run the headless benchmark over all scenarios
python run_benchmark.py

# OPTIONAL: snapshot the fault knowledge base into SQLite (data/faults.db)
python -m ospf_engine.reasoning.kb_sqlite snapshot
python -m ospf_engine.reasoning.kb_sqlite list
python -m ospf_engine.reasoning.kb_sqlite show "OSPF Area Mismatch"
```

The dashboard opens at <http://localhost:8501>. Three modes:

* **Upload Files** - drop your own `.txt` files (one per show command, or one
  combined dump with `R1#show ...` banners).
* **Benchmark Scenarios** - run a single pre-built scenario with ground truth
  comparison (precision / recall / F1).
* **Run All Scenarios** - tabular summary across the whole benchmark.

The runtime catalogue lives as a typed Python dict for speed. The optional
`kb_sqlite` command above mirrors it into a queryable SQLite file so the
project covers the brief's full "Suggested tools" list.

---

## Architecture

```
ospf_fault_engine/
+-- streamlit_app.py            <- Streamlit entrypoint (thin)
+-- run_benchmark.py            <- CLI benchmark
+-- pyproject.toml              <- ruff / black / pytest config
+-- requirements.txt
+-- .streamlit/config.toml      <- dark professional theme
+-- ospf_engine/                <- the package
|   +-- __init__.py
|   +-- models/                 <- typed dataclasses (no logic)
|   |   +-- evidence.py
|   |   +-- fault.py
|   |   +-- analysis.py
|   |   +-- topology.py
|   +-- parsers/                <- one module per show-command family
|   |   +-- base.py
|   |   +-- dispatcher.py       <- routes by filename + content
|   |   +-- ospf_neighbor.py
|   |   +-- ospf_interface.py
|   |   +-- access_lists.py
|   |   +-- ip_interface.py
|   |   +-- interfaces_trunk.py
|   |   +-- spanning_tree.py
|   |   +-- ip_route.py
|   |   +-- dhcp.py
|   |   +-- syslog.py
|   |   +-- endpoint.py
|   |   +-- dns.py
|   +-- reasoning/              <- pure analysis (no I/O)
|   |   +-- knowledge_base.py   <- 12 typed Fault definitions
|   |   +-- tag_map.py          <- evidence-tag -> fault contributions
|   |   +-- correlator.py       <- cross-device link/trunk reasoning
|   |   +-- combinations.py     <- in-device evidence combinations
|   |   +-- side_effects.py     <- "X explains Y" causal graph
|   |   +-- scorer.py           <- tier-driven confidence ladder
|   |   +-- classifier.py       <- ROOT_CAUSE vs SIDE_EFFECT etc.
|   |   +-- suppressor.py       <- removes weak / ambiguous alternatives
|   |   +-- fix_planner.py      <- dependency-ordered fix path
|   |   +-- pipeline.py         <- single public analyze() entrypoint
|   +-- scenarios/              <- 8 typed benchmark scenarios
|   +-- reporting/              <- timeline, accuracy, text report
|   +-- ui/                     <- Streamlit theme + components + app
|   +-- utils/
+-- tests/                      <- 68 pytest tests
+-- data/                       <- generated benchmark output (gitignored)
```

Both `streamlit_app.py` and `run_benchmark.py` call exactly **one** entrypoint
(`ospf_engine.analyze(parse_files(files))`) so the UI and the CLI cannot
disagree about the diagnosis.

---

## Evidence model

The engine never claims something is a root cause without proof. Every parsed
observation is tagged with one of three confidence tiers:

| Tier   | Meaning                                                               | Example                                                              |
|--------|-----------------------------------------------------------------------|----------------------------------------------------------------------|
| WEAK   | Symptom only - proves something is wrong, NOT what caused it          | `ospf_no_neighbor`, `ospf_no_routes`                                 |
| STRONG | Direct observation of a fault mechanism                               | `acl_blocks_ospf` (ACL has `deny ospf`)                              |
| CONFIG | Explicit configuration conflict between two devices, *or* a confirmed | `area_mismatch_link` (R1 area 0 vs R2 area 1 on the same /30 link)   |
|        | combination (e.g. ACL + ACL applied inbound on OSPF interface)        |                                                                      |

The scorer caps confidence by tier (CONFIG <= 0.95, STRONG <= 0.72,
WEAK <= 0.40). The label "Confirmed Cause" is reserved for CONFIG-level
findings.

### Why cross-device correlation matters

A single router with two different OSPF areas on two different interfaces is
a perfectly legitimate ABR. A single router with two different hello timers
on two different interfaces is also fine. The legacy engine flagged both as
"area / timer mismatch" - false positives.

The correlator joins parsed interface facts on **subnet** and only flags a
mismatch when *both ends of the same link* disagree. This is the same
deduction a network engineer makes by hand, and it eliminates an entire class
of false positives.

---

## Benchmark results

8 pre-built scenarios are bundled (5 from the brief, 2 added for DNS and MTU
coverage, and **Scenario 8 - the main demo** with 4 simultaneous hidden
faults). Run `python run_benchmark.py` to evaluate.

> The numbers below are the engine's accuracy **on the included benchmark
> scenarios only**. They are not a claim about real-world networks - new
> topologies will need new scenarios and may expose new failure modes.

| Scenario                                  | Top fault                       | Confidence | F1   |
|-------------------------------------------|---------------------------------|------------|------|
| 1 - OSPF Area Mismatch                    | OSPF Area Mismatch              | 85%        | 1.00 |
| 2 - OSPF Timer Mismatch                   | OSPF Timer Mismatch             | 85%        | 1.00 |
| 3 - OSPF Hellos Blocked by ACL            | OSPF Hellos Blocked by ACL      | 95%        | 1.00 |
| 4 - Native VLAN + DHCP Relay              | Native VLAN Mismatch            | 95%        | 1.00 |
| 5 - ACL Direction + STP Root              | ACL Wrong Direction             | 95%        | 1.00 |
| 6 - DNS Dependency Failure                | DNS Resolution Failure          | 85%        | 1.00 |
| 7 - OSPF MTU Mismatch                     | OSPF MTU Mismatch               | 85%        | 1.00 |
| **8 - Multi-Fault Demo (main demo)**      | OSPF Hellos Blocked by ACL      | 95%        | 1.00 |
| **Average (across these 8 scenarios)**    |                                 |            | **1.00** |

### Scenario 8 - main demo

This is the scenario to use when discussing the project, because it answers
the brief's "inject 3 to 5 hidden problems and ask the engine to identify the
main trigger and the side effects". Four independent faults are hidden in one
capture:

1. ACL on R1 inbound denies OSPF multicast.
2. Native VLAN mismatch (1 vs 99) on the SW1 <-> SW2 trunk.
3. R1 LAN interface is missing `ip helper-address`.
4. PC1 can ping the server by IP but `nslookup` fails (isolated DNS).

The engine is expected to:

* surface **all four as ROOT_CAUSE at CONFIG confidence**,
* **suppress** the side-effect alternatives - Area / Timer mismatch (from the
  empty neighbor table), DHCP Server Unreachable (from the empty bindings),
* produce a **dependency-ordered fix path** that lists prerequisites first.

To open this scenario in the dashboard: `streamlit run streamlit_app.py` ->
*Benchmark Scenarios* -> *Scenario 8 - Multi-Fault Demo (4 hidden faults)*.

---

## Running the tests

```bash
pytest -q
```

The suite has 68 tests covering:

* every parser in isolation (with captured Cisco output fixtures),
* the cross-device correlator,
* the scorer / classifier / suppressor,
* the dispatcher (single-file, content-sniffed, and combined-output modes),
* the optional SQLite knowledge-base mirror (round-trip + idempotence),
* every benchmark scenario end-to-end (per-scenario F1 floor + global average floor).

---

## Packet Tracer topology guide

If you want to feed the engine real captures from Packet Tracer, build the
following topology, configure the **clean** baseline, then inject a fault.

### Devices

* 4 routers (R1, R2, R3, R4)
* 2 switches (SW1, SW2)
* 2 PCs (PC1, PC2)
* 1 server (DHCP / DNS)

### Physical connections

```
PC1 -- SW1 -- R1 -- R2 -- R3 -- R4
              |                 |
             SW2              Server (DHCP / DNS)
              |
             PC2
```

### IP addressing

| Device | Interface | IP             | Subnet         |
|--------|-----------|----------------|----------------|
| R1     | Gi0/0     | 10.0.1.1/30    | R1 <-> R2 link |
| R2     | Gi0/0     | 10.0.1.2/30    | R1 <-> R2 link |
| R2     | Gi0/1     | 10.0.2.1/30    | R2 <-> R3 link |
| R3     | Gi0/0     | 10.0.2.2/30    | R2 <-> R3 link |
| R3     | Gi0/1     | 10.0.3.1/30    | R3 <-> R4 link |
| R4     | Gi0/0     | 10.0.3.2/30    | R3 <-> R4 link |
| R1     | Gi0/1     | 192.168.1.1/24 | LAN segment    |
| R4     | Gi0/1     | 192.168.4.1/24 | Server segment |

### Baseline OSPF (apply on every router first)

```
R1: router ospf 1
    router-id 1.1.1.1
    network 10.0.1.0 0.0.0.3 area 0
    network 192.168.1.0 0.0.0.255 area 0

R2: router ospf 1
    router-id 2.2.2.2
    network 10.0.1.0 0.0.0.3 area 0
    network 10.0.2.0 0.0.0.3 area 0

R3: router ospf 1
    router-id 3.3.3.3
    network 10.0.2.0 0.0.0.3 area 0
    network 10.0.3.0 0.0.0.3 area 0

R4: router ospf 1
    router-id 4.4.4.4
    network 10.0.3.0 0.0.0.3 area 0
    network 192.168.4.0 0.0.0.255 area 0
```

### SW1 <-> SW2 trunk + DHCP relay (clean state)

```
SW1(config-if)# switchport mode trunk
SW1(config-if)# switchport trunk native vlan 1
SW2(config-if)# switchport mode trunk
SW2(config-if)# switchport trunk native vlan 1

R1(config-if)# ip helper-address 192.168.4.10
```

### Collecting outputs (one .txt per command per device)

```
terminal length 0
show ip ospf neighbor detail
show ip ospf interface
show ip route
show access-lists
show ip interface gigabitEthernet 0/0
show ip interface gigabitEthernet 0/1
show interfaces trunk
show vlan brief
show ip dhcp binding
show logging
```

Suggested filenames so the dispatcher routes correctly without sniffing:

```
ScenarioX/
  R1_ospf_neighbor.txt
  R1_ospf_interface.txt
  R1_ip_route.txt
  R1_access_lists.txt
  R1_ip_interface_g00.txt
  R1_logging.txt
  SW1_trunk.txt
  SW1_spanning_tree.txt
  SW1_vlan.txt
  PC1_ipconfig.txt
  PC1_nslookup.txt
```

You can also paste a single combined dump with `=====` or `-----` banners,
or with the natural `R1#show ...` prompt+command lines - the dispatcher
splits and routes automatically.

---

## Fault injection scenarios

Save a separate `.pkt` for each.

### 1 - OSPF area mismatch

```
R2(config)# router ospf 1
R2(config-router)# no network 10.0.1.0 0.0.0.3 area 0
R2(config-router)# network 10.0.1.0 0.0.0.3 area 1
```

### 2 - OSPF timer mismatch

```
R3(config-if)# ip ospf hello-interval 20
R3(config-if)# ip ospf dead-interval 80
```

### 3 - OSPF hellos blocked by ACL

```
R1(config)# ip access-list extended BLOCK_OSPF
R1(config-ext-nacl)# deny ospf any host 224.0.0.5
R1(config-ext-nacl)# deny ospf any host 224.0.0.6
R1(config-ext-nacl)# permit ip any any
R1(config-if)# ip access-group BLOCK_OSPF in
```

### 4 - Native VLAN mismatch + missing helper

```
SW2(config-if)# switchport trunk native vlan 10
R1(config-if)# no ip helper-address 192.168.4.10
```

### 5 - ACL wrong direction + STP root steal

```
R1(config)# ip access-list extended WRONG_DIR
R1(config-ext-nacl)# deny ip 192.168.1.0 0.0.0.255 any
R1(config-ext-nacl)# permit ip any any
R1(config-if)# ip access-group WRONG_DIR out

SW2(config)# spanning-tree vlan 1 priority 0
```

### 6 - DNS dependency failure (new)

Stop the DNS service on the server (or delete the DNS A record). The PC
should still be able to ping the server by IP. Capture
`PC1_ping_by_ip.txt` and `PC1_nslookup.txt`.

### 7 - OSPF MTU mismatch (new)

```
R4(config-if)# mtu 1400
```

The R3 <-> R4 adjacency will hang in EXSTART/EXCHANGE - exactly the symptom
the engine fingerprints with `mtu_mismatch_link` + the syslog
"Mismatched hello parameters" pattern.

### 8 - Multi-fault demo (main demo)

Apply all four of these on the same baseline topology, then collect outputs:

```
! 1) ACL blocks OSPF on R1 Gi0/0
R1(config)# ip access-list extended BLOCK_OSPF
R1(config-ext-nacl)# deny ospf any host 224.0.0.5
R1(config-ext-nacl)# deny ospf any host 224.0.0.6
R1(config-ext-nacl)# permit ip any any
R1(config-if)# ip access-group BLOCK_OSPF in

! 2) Native VLAN mismatch on the SW1 <-> SW2 trunk
SW2(config-if)# switchport trunk native vlan 99

! 3) Missing DHCP helper on R1 LAN
R1(config-if)# no ip helper-address 192.168.4.10

! 4) DNS service stopped on the server (so nslookup fails but ping by IP works)
```

Expected engine output: four ROOT_CAUSE findings, area/timer/DHCP-server-
unreachable alternatives suppressed, and a fix path that schedules the L2
fix (native VLAN) before the L3 fixes (ACL, DHCP, DNS).

---

## How to discuss this in CET361

A two-minute walkthrough of the report:

1. **What is the input?** Plain `.txt` files with simulated `show ...`
   output and `show logging` syslog. The brief lists exactly these inputs.
2. **How does the engine read them?** One small parser per command in
   `ospf_engine/parsers/`. Each parser extracts two things: typed
   *evidence* and structured *topology facts* (interface IPs, VLANs, ACL
   bindings, etc.).
3. **How does it find the root cause?**
   - Every observation gets a tier: `WEAK` (symptom), `STRONG` (mechanism
     observed), or `CONFIG` (configuration mismatch confirmed across
     devices).
   - `correlator.py` joins facts on subnet / trunk / VLAN so the engine
     only flags a mismatch when *both ends of the same link disagree*.
     This is why a single ABR with two areas is **not** a false positive.
   - `scorer.py` caps confidence by tier; `classifier.py` labels each
     fault as ROOT_CAUSE / SIDE_EFFECT / etc.
   - `suppressor.py` removes weaker alternatives that a confirmed cause
     already explains - the difference between "list of symptoms" and
     "ranked root causes".
4. **Why are the fixes safe?** The engine never applies anything. It
   prints verification commands first, then a fix template. The fix path
   is topologically ordered using `Fault.fix_dependencies`.
5. **How is accuracy measured?** `reporting/accuracy.py` computes
   precision / recall / F1 against the ground-truth fault list bundled
   with each scenario. Numbers are reported per-scenario and as an
   average **across the eight included scenarios** - not as a general
   real-world claim.
6. **Where is the demo?** Scenario 8. Four hidden faults, the engine
   ranks all four, suppresses three plausible-looking side effects, and
   produces an ordered fix plan.

If asked "why no machine learning?" the honest answer is that this domain
has small, well-understood failure modes and the brief expects an
explainable evidence-to-cause mapping. Rules give a transparent
diagnosis chain (`analysis.diagnosis_chain`), which is exactly what an
operator would expect to see during an incident.
