# 4. Action Plan

Phased so that cheap configuration checks run before drive tests, and so each phase has an exit
criterion. Durations are omitted on purpose: the sequence is set by dependencies (you cannot
interpret a drive test until Phase 0 has fixed the KPI definition), not by a calendar.

Owners below match a typical split (RAN, Tx, Core, IP, Performance). Rename them to your actual
teams; keep the rule that **every action has one owner and one piece of evidence**.

The detailed checks live in [Chapter 3](03-domain-by-domain-checks.md). This chapter is the order in
which to run them and the bar for moving on.

---

## Phase 0 — Make the comparison honest

**Goal:** decide whether a real throughput drop exists, separately for swapped sites and new sites.

| # | Action | Owner | Evidence |
| --- | --- | --- | --- |
| 0.1 | Write the Ericsson baseline formula and the Huawei formula side by side: layer (PDCP SDU vs PDU), last-TTI exclusion, EN-DC volume attribution, filters, aggregation | Performance | Formula sheet, signed by RAN vendor and Performance |
| 0.2 | Recompute the last pre-swap month and the latest month with one common method | Performance | Two numbers, one method, delta in % |
| 0.3 | Split the population: swapped sites vs new Huawei sites. Report DL and UL separately, per TDD carrier | Performance | Two trend lines |
| 0.4 | Pick the reference cluster: 10 swapped sites with a clear drop, 5 swapped sites that held up, 5 new sites. Freeze this list; all later phases use it | Performance + RAN | Site list with cell IDs, baseline value, current value |

**Exit:** a single agreed delta, in percent, for swapped sites, computed one way. If the delta is
within the formula uncertainty established in 0.1, stop and re-baseline on the Huawei definition.
Otherwise proceed, and quote this delta — not a dashboard screenshot — as the problem statement.

---

## Phase 1 — Configuration sweep (no field work)

**Goal:** find every ceiling that is a configured number. These cause the majority of post-swap
throughput drops and none of them require a night outage to *diagnose*.

Run on the 20-site reference list first, then on the full 5G population.

| # | Action | Owner | Pass mark |
| --- | --- | --- | --- |
| 1.1 | Inventory per site: BBU, main board, backhaul port, negotiated speed, SFP type, eCPRI rate per AAU | RAN | 10GE+ backhaul, 25G eCPRI on every 32T AAU |
| 1.2 | Dump IP-path bandwidth, `CARRYFLAG`, and resource-group bandwidth for user plane | RAN | Configured bandwidth ≥ Ch.2 single-user peak (~2.2 Gbit/s) on the NR path |
| 1.3 | MTU on BBU, CSG, aggregation, core edge, firewall, UPF/S-GW | RAN + Tx + IP | ≥ 1600 end to end (≥ 1700 with IPsec), or a documented UE MTU that matches the real path |
| 1.4 | One X2-AP trace: EN-DC option (3 / 3a / 3x), `SgNB UE Aggregate Maximum Bit Rate`, PDCP SN size | RAN | SgNB AMBR ≥ target; SN size 18-bit on the split bearer |
| 1.5 | One S1 trace plus HSS dump for the same UE: APN-AMBR, UE-AMBR, `restrictDCNR` | Core | All three AMBRs ≥ target and consistent with 1.4 |
| 1.6 | DSCP map QCI/5QI → RAN → CSG class → CIR/PIR/CBS, including the X2-U class | RAN + Tx | User plane in a class whose PIR ≥ single-user peak; X2-U in a low-latency class |
| 1.7 | Licence: RAN throughput/layers/256QAM, IPsec throughput, UPF/S-GW throughput, firewall/CGNAT | RAN + Core + IP | No licence ceiling below the target |
| 1.8 | Sync: GNSS vs PTP, lock state, TDD pattern compared across neighbouring cells | RAN + Tx | Locked, pattern identical across the 2.6 GHz neighbour set |
| 1.9 | Parameter diff Ericsson → Huawei for the rows in Ch.3 §3.5.3 | RAN | Diff table; every mismatch either corrected or explicitly accepted |

**Exit:** a punch list of confirmed configuration defects, each with site count. Fix the ones that are
a parameter change (AMBR, path bandwidth, DSCP, SN size, TDD pattern) immediately, re-measure the
reference cluster with the Phase 0 method, and carry only the **remaining** delta into Phase 2.
Hardware changes (SFP, board, microwave) go onto the Phase 4 list with the evidence attached — do not
wait for them to start Phase 2.

---

## Phase 2 — Segment isolation on two sites

**Goal:** on one site that is still degraded after Phase 1 and one healthy new site, name the segment
that loses the throughput. Use the drill in Chapter 2 §2.4 and the decision tree in Chapter 3 §3.0.

| # | Action | Owner | Output |
| --- | --- | --- | --- |
| 2.1 | DF-bit ping sweep gNB → UPF and eNB ↔ gNB at 1400 / 1472 / 1500 / 1600 | Tx | Path MTU per direction |
| 2.2 | TWAMP or Y.1731 in the user-plane DSCP and in the X2-U DSCP, 15 min, both sites | Tx + RAN | Loss, RTT mean, RTT max, jitter per segment |
| 2.3 | UDP ramp 0.5 / 1.0 / 1.5 / 2.0 Gbit/s from a host at the site to a host at the UPF | Tx + IP | The rate at which loss begins — this is the transport ceiling |
| 2.4 | Per-class output-drop counters at ≤ 60 s during 2.3, on CSG, aggregation, and core edge | Tx + IP | The hop whose drops rise first |
| 2.5 | Single-UE test: NR-only, then EN-DC, then 8 TCP streams, same server, RSRP/SINR window recorded | RAN | Three numbers per site |
| 2.6 | During 2.5, capture MCS, rank, PRB allocation, and the port `TxMaxSpeed` | RAN | Radio-vs-transport classification per the table in §3.5.1 |
| 2.7 | Diff every value against the healthy site | Performance | The first row that differs is the leading cause |

**Exit:** a one-page finding of the form "on site X, throughput is lost between A and B, evidence C".
If the two sites differ at the radio row and nowhere in transport, close the transport track for that
site and hand it to RF optimisation. If they differ at a hop, that hop is a Phase 4 work item, and
you repeat Phase 2 on two more sites to confirm it is a class of fault rather than one bad tail.

---

## Phase 3 — Population proof

**Goal:** show the finding applies to the fleet, not just the lab site.

| # | Action | Owner | Output |
| --- | --- | --- | --- |
| 3.1 | Turn the Phase 2 signature into a counter rule (examples: `VS.IPPath.TxDropPkts` > 0 while a speed test runs; `VS.FEGE.TxMaxSpeed` pinned at 1 Gbit/s; `N.NsaDc.SgNB.AbnormRel.Trans` > 0; TWAMP peak drop > 0) | Performance + RAN | A report, all 5G sites |
| 3.2 | ECMP/LAG audit on the common path: hash inputs, per-member utilisation under load, TEID hashing yes/no | IP | Pass/fail per bundle, with a template change if it fails |
| 3.3 | RTT comparison for the reference cluster against the pre-swap probe history | Tx + Core | Sites where RTT, not loss, explains the TCP drop |
| 3.4 | Separate the punch list into: port/hop upgrade, parameter fix, core policy, IP design, radio, sync | Performance | Five lists, no site in two lists unless the evidence says so |

**Exit:** a ranked list. Rank by the size of the throughput gap times the number of sites, so the
first remediation returns the most baseline.

---

## Phase 4 — Remediate in evidence order

Apply fixes in this order. Each one is verifiable on the reference cluster within one measurement
cycle, so a fix that did nothing is visible immediately.

| Order | Fix | Why this order |
| --- | --- | --- |
| 1 | AMBR alignment (HSS, MME, SgNB AMBR) and RAN licence | Parameter-only, largest single-user effect, reversible |
| 2 | IP-path / resource-group bandwidth, DSCP class, PDCP SN size, EN-DC option | Still parameter-only; removes RAN-internal shapers |
| 3 | MTU uplift or MSS clamp, ICMP PMTUD allowed | Parameter plus a firewall rule; removes the black hole |
| 4 | TEID hashing and hash-seed change on LAG/ECMP | Design change with a bounded blast radius; fixes the "one member full" case |
| 5 | Port and first-mile upgrades: 1G → 10G SFP, RJ45 removed, microwave channel, PON profile, EVC CIR | Spend. Only for sites whose Phase 2 UDP ramp proved the hop ceiling |
| 6 | UPF/S-GW rebalance, TCP optimiser decision, peering | Only when Phase 2 showed the loss past the RAN |
| 7 | Sync and TDD-pattern alignment | Where clock or cross-link interference was evidenced |
| 8 | Radio parameters (SRS, CSI, layer cap) | Where Phase 2 classified the site as radio |

**Rule:** one change family at a time on the reference cluster, then re-measure with the Phase 0
method. Stacking five changes before measuring makes the next degradation undiagnosable.

---

## Phase 5 — Lock the baseline so this does not recur

| # | Action | Owner |
| --- | --- | --- |
| 5.1 | Publish the Huawei-era baseline, split by swapped vs new, DL vs UL, with the formula in the same document | Performance |
| 5.2 | Add permanent alarms: backhaul negotiated speed < 10GE, eCPRI < 25G on a 32T AAU, IP-path drop counters increasing, SCTP retransmits, PTP unlock, LAG member down | RAN + Tx |
| 5.3 | Add a commissioning gate for every new 5G site: port speed, eCPRI rate, path bandwidth, MTU, AMBR trace, PTP lock. A site that fails the gate does not join the throughput KPI | RAN |
| 5.4 | Keep `tools/tx_budget.py` with the site design pack. When a carrier is added, rerun it and update the CIR before the carrier is on-air | RAN planning + Tx |
| 5.5 | Agreement with the RAN vendor: a "transport capacity" statement is submitted with the four-mechanism evidence from Ch.2 Rule 5, or it is returned | RAN + Tx |

---

## Working agreement for the vendor meeting

Open with this, so the meeting spends its time on evidence:

1. We accept that transport can limit 5G throughput, and we will upgrade every hop that a UDP ramp shows is short of the TS 38.306-based budget.
2. A 15-minute utilisation average is not evidence either way. The shared standard is p99 at one minute or finer, plus per-class drops, plus RTT, plus a DF-bit MTU test.
3. The RAN side will arrive with the Phase 1 dumps (port, path bandwidth, SgNB AMBR, licence, sync) so any cap inside the base station is on the table at the same time as the hop table.
4. Sites are split into swapped and new. They are not one KPI.
5. We will name the segment on two reference sites before any network-wide re-architecture.

Suggested standing agenda, one page per item, evidence attached:

| Item | Presented by |
| --- | --- |
| Agreed delta from Phase 0 | Performance |
| Phase 1 punch list: configuration ceilings found | RAN |
| Hop table for the reference sites vs the Ch.2 budget | Tx |
| AMBR trace, three values | Core |
| MTU map and ECMP hash | IP |
| Decision: which Phase 4 items start now | All |

---

## Questions to put to the vendor in writing

"Transmission capacity, so throughput cannot reach baseline" is not actionable. Because the vendor now supplies both the RAN and the transmission, the answers below all sit with one organisation. Ask for each one with a node, an interface, and a timestamp attached.

1. **Which segment?** Fronthaul, last mile, ring, aggregation, core edge, or the bandwidth configured inside the base station?
2. **Which mechanism?** Capacity, loss, latency/jitter, or MTU? (Chapter 2, Rule 5.)
3. **What is the evidence?** p99 rate at one minute or finer, configured capacity, and per-class drops. A 15-minute average is not evidence.
4. **What capacity does your own dimensioning rule require** for this radio configuration? Compare it with `tools/tx_budget.py` and with what was delivered.
5. **What is the configured IP-path and resource-group bandwidth**, and how does it compare with the physical port speed?
6. **What did these counters do during a failing test?** `VS.RscGroup.TxDropPkts`, `VS.IPPath.TxDropPkts`, `N.PDCP.DL.X2U.ReqRetransPackets`, `N.NsaDc.SgNB.AbnormRel.Trans`.
7. **What `SgNB UE Aggregate Maximum Bit Rate` is signalled**, and what MTU is configured on the transport interfaces?

Hold the internal transmission team to the same bar. "No transmission issue" needs p99 per hop, per-queue drops, measured RTT and jitter, and a DF-bit MTU result. A statement missing any of those four is incomplete.

## One paragraph for management

A 100 MHz 32T32R NR cell can schedule about **1.7 Gbit/s** downlink, which needs **over 2 Gbit/s of transport** once encapsulation is counted, and the LTE upgrades (FDD 2T→4T, TDD 4T→32T) raised demand on the same ports at the same time. The dispute continues because the vendor is describing instantaneous capacity and dimensioning, while the transmission team is reporting availability and average utilisation, so both can be correct. It is closed by desk checks first — port speed, the shaper inside the base station, MTU, and the AMBR values — and only then by a per-segment UDP ramp on two reference sites.
