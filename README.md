# 5G Transmission Over 4G — Understanding and Issue Findings

Investigation framework for **5G DL/UL user-throughput degradation after an Ericsson → Huawei
modernisation/swap**, where the RAN vendor attributes the shortfall to transmission capacity and the
internal transmission team reports no transmission issue.

Scope of the network under analysis:

* 5G TDD 2.6 GHz, launched on Ericsson, now swapped to Huawei, **32T32R before and after**
* LTE FDD upgraded **2T → 4T**; LTE TDD upgraded **4T → 32T**
* Additional greenfield 5G sites that never existed on Ericsson
* **Transmission is now Huawei end to end**

---

## Start here

| Chapter | Content |
| --- | --- |
| [1. How 5G transmission works over 4G](docs/01-how-5g-transport-works-over-4g.md) | NSA/EN-DC anchoring, bearer Options 3 / 3a / 3x, X2-U and flow control, fronthaul vs midhaul vs backhaul, protocol overhead, and **why the vendor and the Tx team can both be right** |
| [2. Baseline, budget and the measurement contract](docs/02-baseline-and-transport-budget.md) | Proving the degradation is real before chasing it; the physical ceiling; computed transport budgets; the evidence standard that ends the dispute; a one-day joint test drill |
| [3. Domain-by-domain checks](docs/03-domain-by-domain-checks.md) | ~75 tracked checks across **RAN-side Tx, Tx side, Core side, IP network, and Others**, with Huawei counters and a ranked hypothesis list |
| [4. Action plan](docs/04-action-plan.md) | Phase 0–3 with owners and exit criteria, plus the seven questions to put to the vendor in writing |
| [5. Evidence templates](docs/05-evidence-templates.md) | Inventory and test-record templates, verified Huawei counter shortlist, command checklist, dimensioning rule, standing monitoring set, sources |

Tooling: [`tools/tx_budget.py`](tools/tx_budget.py) — transport budget calculator implementing the
3GPP TS 38.306 §4.1.2 peak-rate formula with TDD time share, protocol expansion and EN-DC X2-U
allowance.

---

## Answers to the three questions asked

### 1. How does 5G transmission work over 4G?

If you are on **NSA (EN-DC, Option 3 family)** — which a 2.6 GHz NR layer over an existing LTE network
almost always is — the LTE eNodeB is the **Master Node** and owns the RRC connection and the signalling
to the MME. The gNodeB is the **Secondary Node** and has no MME connection at all. A single data session
can be **split across both radios**, and where that split happens decides what the transport carries:

* **Option 3** — split at the eNB: **all** NR traffic crosses eNB → gNB over **X2-U**, on top of the
  eNB's own S1-U. The eNB's backhaul must carry the entire 5G peak.
* **Option 3a** — split at the S-GW: each node has its own S1-U, minimal X2-U, but no per-packet
  aggregation gain.
* **Option 3x** — split at the gNB (normal best practice): the gNB has its own S1-U and only the
  smaller **LTE share** returns over X2-U.

Consequently a 5G speed test is usually **not** a pure 5G transport event. The ceiling is set by the
**slowest of {gNB backhaul, eNB backhaul, X2-U path}**. A transmission team that verified only the 5G
site's uplink can truthfully report "no issue" while the bottleneck sits on the LTE anchor or the X2
path.

Two further mechanisms matter and are almost never measured:

* **Split-bearer flow control** (TS 36.300 §20.1.1, TS 36.425 §5.4.2) is a **closed control loop over
  the transport network**: the gNB reports Downlink Data Delivery Status and the eNB uses it to decide
  how much to forward. **Latency and jitter therefore reduce throughput even with zero packet loss and
  zero congestion.**
* **Encapsulation shrinks the usable MTU.** With GTP-U + UDP + IP + VLAN + IPsec, TS 23.501 Annex J
  puts total overhead at **142 bytes**, leaving **1358 bytes** of user payload on a 1500-byte transport
  MTU. Exceed it and you get fragmentation, or worse a **PMTUD black hole** — the classic "no errors
  anywhere but throughput is broken" failure.

### 2. Why is the vendor saying there are transmission issues?

Because the vendor and the Tx team are answering different questions with different evidence:

| | Vendor | Tx team |
| --- | --- | --- |
| Question | Can transport deliver the **peak** rate the radio schedules, **at the instant** it schedules it? | Is any link **unavailable, errored, or congested on average**? |
| Evidence | Flow-control, discard and retransmission counters; buffer occupancy; per-second bursts | 5–15 minute average utilisation; alarms; availability reports |
| Blind spot | Rarely names *which* element | **Averaging.** A 1.7 Gbit/s burst into a 1 Gbit/s port for 200 ms destroys a speed test and shows as ~2 % on a 15-minute average. Also blind to MTU, DSCP remarking, and added latency |

And the vendor may well be **dimensionally** correct. From `tools/tx_budget.py`:

| Quantity | Value |
| --- | --- |
| One NR cell, 100 MHz, 30 kHz SCS, 4 DL layers, 256QAM, DDDSU | **1736 Mbit/s DL** (2337 before the TDD split) |
| Wire capacity needed for a **single-UE** DL peak test | **~2116 Mbit/s** |
| Max user goodput a **1GE** port can ever deliver | **~945 Mbit/s** |
| Full swapped site (3× NR + 6× LTE carriers, IPsec), busy hour | **~5.2 Gbit/s** |
| Same site, all cells full buffer | **~9.4 Gbit/s** — about **94 % of a 10GE port** |

So: **a single 100 MHz 32T cell needs more than 2 Gbit/s of transport for one speed test, and a GE port
tops out near 945 Mbit/s.** Meanwhile the LTE upgrades (FDD 2T→4T, TDD 4T→32T) raised the anchor's
demand on the **same** transport at the **same** time. If any site sits on a GE electrical port, a 1G
SFP, a 1G microwave hop, or a GE-limited ring segment, the vendor is right that capacity is
insufficient — **and the Tx team is right that nothing is faulty.** That is a *dimensioning* gap, not a
*fault*, which is precisely why the two reports never reconcile.

Equally, "transmission capacity issue" is often used loosely by a RAN vendor to mean "the node's own
**configured** transport bandwidth limit was hit". Huawei RAN admits and shapes against a configured
bandwidth on the IP path / logical port / transmission resource group. If that was provisioned at a
legacy value on a new 10GE port, **the node throttles itself and reports transport congestion, and the
Tx team will find nothing because the limit is inside the gNB.** Check `VS.RscGroup.TxDropPkts` and
`VS.IPPath.TxDropPkts` against port utilisation — non-zero drops on an idle port proves it.

### 3. Where might the problem be?

Ranked by probability × ease of verification, given NR radio config is **unchanged** (32T → 32T) and
transport is **newly Huawei end to end**. Full detail in [Chapter 3](docs/03-domain-by-domain-checks.md).

| Rank | Hypothesis | Domain |
| --- | --- | --- |
| 1 | **KPI definitions are not apples-to-apples.** Ericsson measures EN-DC stage-2 volume at PDCP **PDU** level and others at **SDU** level; last-TTI exclusion, EN-DC attribution and filters all differ. Easily 10–30 % apparent delta with no physical change | Method |
| 2 | **gNB's configured transport bandwidth below the port's real capacity** — node self-throttles and blames transport | RAN-side Tx |
| 3 | **MTU / fragmentation / PMTUD black hole** on the new end-to-end path | IP network |
| 4 | **Backhaul port, optical module, or first mile below 10G** (genuine capacity gap) | RAN Tx + Tx |
| 5 | **`SgNB UE Aggregate Maximum Bit Rate`, UE-AMBR or APN-AMBR cap.** The **MeNB** chooses how much of the UE-AMBR the 5G node may schedule — a conservative value caps NR invisibly, in no transport KPI and no NR counter | RAN + Core |
| 6 | **DSCP remarking → wrong queue → microburst drops** | IP + Tx |
| 7 | **Leftover policer / shaper / CIR** on a re-created service | IP + Tx |
| 8 | **Added latency** (new UPF/S-GW anchor, hairpinned X2, longer path) degrading flow control and single-stream TCP | IP + Core |
| 9 | **Licence / capacity-key gaps** (gNB, microwave, router, UPF) | Others |
| 10 | **Fronthaul negotiated at 10G instead of 25G** on 32T AAUs — restricts bandwidth/layers, and no backhaul test will ever see it | RAN Tx |
| 11 | **LAG/ECMP polarisation**: GTP-U uses UDP 2152 both ways, so a 5-tuple hash pins a tunnel to **one** member link | IP network |
| 12 | **Ring/aggregation oversubscription** after the large LTE capacity increase | Tx |
| 13 | **Sync degradation → TDD interference** (phase sync, ~1100 ns network budget) | Tx |
| 14 | Radio-side deviations: TDD pattern, layers, modulation, energy saving, MU-MIMO defaults | RAN |
| 15 | TCP optimiser, CGNAT, security GW, or test-server change on N6/SGi | Core + Others |

---

## The two things to do first

1. **Reconcile the KPI definitions** (Chapter 2 §2.1). Cheap, fast, and a meaningful share of
   post-swap "degradation" turns out to be measurement change. Do not spend field effort before this.
2. **Enable the gNodeB's own transport measurement** (Chapter 3, Action A0). Huawei base stations have
   built-in **TWAMP** (`Transport.BSTWAMP`), **Y.1731 delay** (`DataLink.ETHDM`) and **loss**
   (`DataLink.ETHLM`) measurement. Point them at the S-GW/UPF **and** at the eNB's X2-U address, on the
   user-plane DSCP. Within a day you have per-direction delay, jitter and loss owned by the RAN team,
   **not blocked on anyone else's instrumentation** — which settles the two mechanisms (added latency,
   and loss under burst) that nobody is currently measuring.

Then run the **one-day joint test drill** in Chapter 2 §2.4 on one bad site and one good site, and diff
every value. The diff is the root cause.

---

## Using the calculator

```bash
# One 100 MHz TDD cell: the minimum transport to pass a single-UE peak test
python3 tools/tx_budget.py --preset single-cell

# The full swapped site with IPsec
python3 tools/tx_budget.py --preset swap-site --ipsec

# Option 3 rather than 3x: X2-U carries the entire NR share
python3 tools/tx_budget.py --preset swap-site --ipsec --x2u-share 1.0

# Your own carrier mix (LTE TDD uses its 3GPP UL/DL configuration, e.g. LTE_C2)
python3 tools/tx_budget.py --nr 100:30:4:2:256qam --nr-cells 3 --tdd DDDSU \
    --lte 20:4:1:256qam --lte 20:4:1:256qam:LTE_C2 --ipsec

# Small packets: exposes packet-rate (pps) rather than bit-rate limits
python3 tools/tx_budget.py --preset swap-site --ipsec --payload 256

# Machine-readable
python3 tools/tx_budget.py --preset swap-site --ipsec --json
```

No dependencies beyond Python 3.9+. NR figures follow TS 38.306 §4.1.2 with the TDD time share
applied; LTE figures are an estimate calibrated to the well-known 150 Mbit/s per 20 MHz 2-layer 64QAM
reference.

---

## A note on expected values

A healthy single-user result on a lightly loaded 100 MHz DDDSU 4-layer cell is roughly **70–80 %** of
the 1736 Mbit/s theoretical figure, i.e. **~1.2–1.4 Gbit/s DL**. Published commercial 32T32R results at
100 MHz sit around **1.19 Gbit/s DL**, a useful sanity reference.

Diagnostic shortcuts from the *shape* of the number:

| Observed DL ceiling | Suspect |
| --- | --- |
| ~900–945 Mbit/s | **GE bottleneck** (a 1GE port yields ~945 Mbit/s of user goodput) |
| ~1000 Mbit/s exactly | **AMBR or policer cap** |
| Multi-stream fine, single-stream poor | **Latency, loss, or MTU** — not capacity |
| Falls only at busy hour | Genuine capacity or queueing |
| Falls uniformly, all hours, all sites | Configuration or KPI definition |
