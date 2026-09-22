# 4. Action Plan

Phased, with owners and exit criteria. Phases are ordered so that the cheapest, highest-probability
findings surface first, and so that you never spend effort proving something the previous phase has
already ruled in or out.

Sequencing is by dependency, not by calendar. Phase 1 and Phase 2 items are mostly desk work and
counter pulls that can run concurrently; Phase 3 requires field coordination.

---

## Phase 0 — Establish that there is a problem, and agree how it will be measured

**Purpose:** avoid spending an entire organisation's effort on a measurement artefact, and remove the
"my data says otherwise" escape route from every subsequent meeting.

| # | Action | Owner | Exit criterion |
| --- | --- | --- | --- |
| P0.1 | Document the Ericsson baseline KPI formula and the Huawei formula side by side; reconcile layer (PDCP SDU vs PDU), last-TTI exclusion, EN-DC attribution, filters, weighting | Performance / OSS, both vendors | One signed mapping table; a stated "apples-to-apples corrected baseline" |
| P0.2 | Split reporting into **swapped sites** and **new sites**; never mix | Performance | Two independent trends |
| P0.3 | Define the **referee test**: fixed UE model, fixed firmware, fixed on-net server, fixed locations, fixed time windows, single-stream **and** 8-stream, cell load recorded | RF / Drive test | Written test spec, agreed by the vendor in advance |
| P0.4 | Re-measure 10 degraded swapped sites, 3 good swapped sites, 3 new sites with the referee test | RF / Drive test | Table of measured DL/UL per site, with RTT and cell load |
| P0.5 | Adopt the **measurement contract** (§2.3): p99 at ≤60 s, per-segment tests, evidence-bearing claims, the four-mechanism checklist | Programme lead | Contract circulated; both vendor and Tx team acknowledge |
| P0.6 | Compute the theoretical ceiling per cell with `tools/tx_budget.py` and confirm the baseline target is physically valid for the deployed TDD pattern, layers and modulation | RF planning | Target validated or corrected |

**Gate:** if the corrected baseline shows ≤5 % delta, close the issue as measurement change. Otherwise
carry a quantified, defensible degradation figure into Phase 1.

---

## Phase 1 — Desk audit: find the hard caps (no field visits, highest yield per hour)

**Purpose:** hard ceilings are configuration, and configuration can be read remotely. Most swap-related
throughput regressions are found here.

| # | Action | Owner | Exit criterion |
| --- | --- | --- | --- |
| P1.1 | **Per-site transport inventory**: BBU type, main control board, backhaul port type, **negotiated speed**, optical module rate, VLAN/IPsec status, first-mile media and capacity | RAN + Tx | Complete sheet for all swapped + new 5G sites; exception list of sites below 10G |
| P1.2 | **Compare the gNB's configured transport bandwidth** (IP path / logical port / transmission resource group) against the physical port speed and the `tx_budget.py` requirement | RAN | Exception list of self-throttling nodes (**expect findings here**) |
| P1.3 | Pull RAN transport drop and congestion counters for the hours of the failing tests: `VS.RscGroup.TxDropPkts`, `VS.IPRscGroup.TxDropPkts`, `VS.IPPath.TxDropPkts`/`RxDropPkts`, `VS.IP.TxDropPkts`, `VS.Gtpu.RxDropPkts`, plus resource-group congestion duration and flow-control available-bandwidth | RAN | Per-site table; any non-zero drop with low port utilisation is a confirmed internal bottleneck |
| P1.4 | Pull Ethernet-port **Max** rate counters (`VS.FEGE.TxMaxSpeed`, `VS.FEGE.RxMaxSpeed`, `VS.FEGE.TxTotalBW`, `VS.FEGE.RxErrPackets`) — never the Mean variants | RAN | Port headroom proven or disproven per site |
| P1.5 | Pull EN-DC transport evidence: `N.PDCP.DL.X2U.ReqRetransPackets`, `N.PDCP.Vol.DL.X2U.TrfPDU.Tx`, `N.PDCP.Vol.UL.X2U.TrfPDU.Rx`, `N.NsaDc.SgNB.AbnormRel.Trans`, `N.NsaDc.SgNB.Add.Att`/`.Succ`, PSCell change success | RAN | Quantified X2 health; bearer option (3 vs 3x) confirmed empirically |
| P1.6 | **Decode one `SGNB ADDITION REQUEST`** per failing and per good site; read `SgNB UE Aggregate Maximum Bit Rate` and the requested-vs-admitted E-RAB lists | RAN + Core | Value recorded and compared; cap ruled in or out |
| P1.7 | **Read the AMBRs**: HSS/UDM subscribed UE-AMBR and APN-AMBR (or Session-AMBR for SA) for the test SIMs; decode `Initial Context Setup Request` and `Attach Accept`. Test a 1023 Mbit/s and a 2000 Mbit/s profile to rule out boundary-encoding effects | Core | AMBR ceiling documented; test SIM confirmed uncapped |
| P1.8 | Check `DCNR` / `restrictDCNR` and the `NR Restriction in EPS as Secondary RAT` bit | Core | EN-DC permitted end to end |
| P1.9 | **Licence audit**: gNB throughput/MIMO/256QAM/CA/MU-MIMO keys, microwave capacity licences, router and UPF capacity licences | RAN + Tx + Core | No gaps, or a gap list with remediation |
| P1.10 | **Parameter diff**: golden template vs live config for eNB and gNB, focused on TDD pattern, max layers, modulation, energy saving, MU-MIMO, PDCP (`pdcp-SN-SizeDL`), and all transport objects | RAN + vendor | Diff report with each deviation accepted or corrected |
| P1.11 | **Policer / shaper / CIR audit** across the whole path: gNB, CSG, aggregation, core edge, security GW, plus per-VRF and per-service policies | Tx + IP | Every rate limit on the path listed with its value and justification |
| P1.12 | **LAG/ECMP hash audit**: is TEID-aware hashing enabled on every LAG/ECMP hop? | IP | Hash configuration documented; TEID hashing enabled or a change request raised |
| P1.13 | Confirm serving S-GW/PGW or UPF before vs after the swap, and the RTT to a fixed reference | Core + IP | Any anchor/RTT change quantified |
| P1.14 | Fronthaul audit: eCPRI negotiated rate per 32T AAU (25G expected) and eCPRI port errors | RAN | All 32T AAUs confirmed at 25G |

**Gate:** publish a findings list. In practice the majority of cases are resolved by P1.2, P1.6, P1.7,
P1.9, P1.11 or P1.1.

---

## Phase 2 — Active measurement: prove where the packets die

**Purpose:** convert opinion into per-segment measurement. Runs in parallel with Phase 1.

| # | Action | Owner | Exit criterion |
| --- | --- | --- | --- |
| P2.1 | **Enable the gNB's own TWAMP and Y.1731 DM/LM** towards the S-GW/UPF and towards the eNB X2-U address, on the **user-plane DSCP**, on 10 degraded + 3 good sites. Collect `VS.BSTWAMP.*`, `VS.ETHDM.MaxRttDelay`, `VS.ETHDM.MaxRttJitter`, `VS.ETHLM.Forward.DropRate`, `VS.IPPM.Forword.*` | RAN | Measured per-direction delay, jitter and loss per site — **owned by RAN, not blocked on the Tx team** |
| P2.2 | **MTU verification**: DF-bit ping sweep at 1400/1472/1500/1600 B, gNB → S-GW/UPF and gNB → eNB; record the largest size that passes on every path | RAN + IP | Per-path maximum MTU documented; target ≥1600 transport MTU |
| P2.3 | Verify **PMTUD** is not black-holed: confirm ICMP type 3 code 4 and ICMPv6 type 2 traverse every hop; read fragment/reassembly counters | IP | PMTUD proven working, or the blocking hop identified |
| P2.4 | **DSCP end-to-end capture**: capture at the gNB egress and at the core ingress, compare markings for S1-U/N3/X2-U | IP + Core | Marking preserved, or the remarking hop identified |
| P2.5 | **Re-poll every hop at ≤60 s** and publish p95/p99, plus **per-queue output/tail/WRED drops** | Tx | p99 utilisation and drop table per hop for the test window |
| P2.6 | **UDP ramp test** (0.5 / 1 / 1.5 / 2 / 2.5 Gbit/s) between a gNB-side and a UPF-side host; record the exact rate where loss starts | Tx + IP | A single number both teams accept as the transport ceiling |
| P2.7 | **Segment decomposition tests** per §2.3 Rule 2: gNB→CSG, gNB→UPF, eNB↔gNB, UPF→internet server | Tx + IP + Core | Throughput and RTT per segment, so the failing segment is named |
| P2.8 | **Leg isolation on air**: measure NR-only (LTE leg blocked), then EN-DC, then multi-stream vs single-stream | RF | Which leg and which traffic profile fails |
| P2.9 | **Microwave deep dive** on affected hops: ACM profile histogram over 7 days, capacity vs time, licensed capacity, XPIC state, G.826 | Tx | Time-series proof of sustained capacity |
| P2.10 | **Sync verification**: PTP servo state, phase error trend, GNSS lock, holdover events over 7 days | Tx + RAN | Phase error within the ~1100 ns network budget, no holdover during test windows |
| P2.11 | Y.1564 / RFC 2544 **service activation test** on any service that never had one, at the target rate with the target frame sizes | Tx | Pass certificate per service |
| P2.12 | UE-side capability and MSS check: decode UE capability, and capture a TCP SYN on SGi to read the negotiated MSS | RF + Core | UE capability and MSS confirmed correct |

**Gate:** the failing **segment** and the failing **mechanism** (capacity / loss / latency / MTU) are
both named, with evidence.

---

## Phase 3 — Fix, verify, and prevent recurrence

| # | Action | Owner | Exit criterion |
| --- | --- | --- | --- |
| P3.1 | Correct the gNB configured transport bandwidth / resource-group model to match real port capacity and the `tx_budget.py` requirement | RAN | Before/after throughput on the same referee test |
| P3.2 | Raise transport MTU to ≥1600 end to end; remove fragmentation; restore PMTUD; set MSS clamping correctly | IP + Tx | DF-bit 1500 B passes end to end; fragment counters flat |
| P3.3 | Remove or re-scale leftover policers/shapers/CIRs; align them to the dimensioned requirement | Tx + IP | Config evidence + retest |
| P3.4 | Restore DSCP marking and QoS maps end to end; re-tune queue/buffer sizing for NR microbursts | IP + Tx | Zero per-queue drops at the test rate |
| P3.5 | Upgrade ports / optical modules / first-mile hops / ring segments identified as sub-10G | Tx | Per-site upgrade completion, then retest |
| P3.6 | Enable TEID-aware LAG/ECMP hashing on all relevant hops | IP | Verified with exact-route checks; single-tunnel throughput improves |
| P3.7 | Correct `SgNB UE Aggregate Maximum Bit Rate`, UE-AMBR/APN-AMBR and policy caps | RAN + Core | Decoded values match intent; retest |
| P3.8 | Close licence gaps | RAN + Tx + Core | Licences installed; capability retested |
| P3.9 | Correct radio parameter deviations found in P1.10 (TDD pattern, layers, modulation, energy saving, MU-MIMO, PDCP SN size) | RAN | Parameter audit clean |
| P3.10 | Fix fronthaul negotiated below 25G on 32T AAUs | RAN | All AAUs at 25G |
| P3.11 | **Re-dimension the transport plan** for the new radio capability (FDD 4T, TDD 32T, NR 32T), per site and per ring segment, using `tx_budget.py` | RAN planning + Tx | Approved dimensioning rule, e.g. "10GE minimum per 5G site, 25GE where 3×100 MHz plus LTE 32T coexist" |
| P3.12 | Add permanent monitoring: p99 interface rate, per-queue drops, `VS.FEGE` Max counters, X2-U retransmissions, `N.NsaDc.SgNB.AbnormRel.Trans`, TWAMP delay/jitter/loss, fragment counters, PTP phase error | OSS + Tx | Dashboard live with thresholds and alarms |
| P3.13 | Make Y.1564 activation testing and an MTU/DSCP verification step **mandatory acceptance criteria** for every remaining swap and new site | Programme lead | Updated acceptance checklist in the rollout process |
| P3.14 | Retest the full referee suite on all Phase-0 sites and publish before/after | RF + Performance | Baseline achieved, or a residual gap quantified with its cause |

---

## 4.1 How to run the vendor conversation

The vendor's statement — "transmission capacity issues, so throughput cannot reach baseline" — is not
actionable as written. Convert it into a claim that can be tested. Ask exactly this:

1. **Which segment?** Fronthaul, last mile, ring, aggregation, core edge, or the node's own configured
   bandwidth? Name the interface.
2. **Which mechanism?** Capacity, loss, latency/jitter, or MTU? (The four in §2.3 Rule 5.)
3. **What is the evidence?** Node, interface, timestamp, granularity, **p99** rate, configured
   capacity, and drop counters. A 15-minute average is not evidence.
4. **What is the required capacity, per your own dimensioning rule, for this exact radio
   configuration?** Then compare it against `tx_budget.py` and against the delivered capacity.
5. **Have you checked your own node's configured transport bandwidth** (IP path / logical port /
   transmission resource group) against the physical port speed? Show the values.
6. **What are the values of** `VS.RscGroup.TxDropPkts`, `VS.IPPath.TxDropPkts`,
   `N.PDCP.DL.X2U.ReqRetransPackets`, `N.NsaDc.SgNB.AbnormRel.Trans`, and the resource-group
   flow-control available-bandwidth counters during the failing tests?
7. **What is the `SgNB UE Aggregate Maximum Bit Rate`** being signalled, and the MTU configured on the
   transport interfaces?

Because the vendor now supplies **both** the RAN and the transmission, they own the end-to-end
dimensioning. That removes the usual finger-pointing, and it means questions 4–7 are all answerable by
one organisation. Put them in writing with a due date.

Equally, hold the internal Tx team to the same standard. "No Tx issue" must be accompanied by: p99 at
≤60 s granularity per hop, per-queue drop counters, measured RTT/jitter, and an explicit MTU
confirmation. If any of those four is missing, the statement is incomplete rather than wrong.

## 4.2 The one-sentence summary for management

> A 100 MHz 32T32R NR cell can schedule ~1.7 Gbit/s downlink, which needs **>2 Gbit/s of transport**
> once encapsulation is counted; the LTE upgrades (FDD 2T→4T, TDD 4T→32T) raised the anchor's demand
> on the same transport at the same time. The dispute persists because the vendor is arguing about
> **instantaneous capacity and dimensioning** while the transmission team is reporting **availability
> and average utilisation** — so both can be correct. It is resolved by measuring p99 rates and
> per-queue drops per segment, verifying MTU end to end, and checking the caps configured inside the
> RAN and the core, all of which are desk-level checks.

Continue to [Chapter 5: Evidence templates](05-evidence-templates.md).
