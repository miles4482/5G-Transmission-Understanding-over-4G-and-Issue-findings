# 5G throughput after the Ericsson → Huawei swap

Investigation pack for a 2.6 GHz TDD network whose downlink and uplink user throughput fell after an end-to-end swap from Ericsson to Huawei.

What changed: NR stayed **32T32R**, LTE FDD went **2T → 4T**, LTE TDD went **4T → 32T**, new 5G sites were added that never existed on Ericsson, and **transmission is now Huawei from the site to the core**. The RAN vendor attributes the drop to transmission capacity. The transmission team reports no transmission fault.

## The short answers

**How 5G transport depends on 4G.** On NSA (EN-DC), the LTE eNodeB is the master node: it owns the signalling to the MME, and it decides how much of each session the 5G node is allowed to schedule (`SgNB UE Aggregate Maximum Bit Rate`). User traffic is split per 3GPP TS 37.340. In Option 3 the whole NR flow crosses the LTE site over X2-U; in Option 3x the gNodeB has its own path to the core and only the LTE share returns over X2-U. Either way a 5G speed test is limited by the slowest of the gNodeB backhaul, the eNodeB backhaul, and the X2 path. X2 also carries a flow-control loop (TS 36.300 §20.1.1, TS 36.425), so latency and jitter cut throughput even when nothing is full and nothing is dropped.

**Why the vendor says transmission, and why that can be true while the transmission team is also right.** One 100 MHz 32T cell, 4 layers, 256QAM, DDDSU pattern, can schedule **1736 Mbit/s** downlink (TS 38.306). On the wire, after GTP-U encapsulation, that is about **2.1 Gbit/s**. A GE port delivers at most **~945 Mbit/s** of user data. The vendor is talking about that instantaneous peak. The transmission team is usually looking at 15-minute average utilisation, alarms, and link availability, which a 200 ms burst barely moves. Separately, the base station itself shapes traffic on an IP path and a transmission resource group; when that shaper is the ceiling, the node reports a transmission problem and no router in the network shows congestion.

**Where the bottleneck can sit.** In rough order of likelihood for this swap: the KPI definition changed between vendors; a shaper inside the gNodeB; an MTU/fragmentation black hole on the new path; a 1G port or 1G first-mile hop; an AMBR cap in HSS, MME, or the eNodeB; DSCP or CIR left over from the LTE design; extra latency from a new core anchor; a 10G eCPRI link on a 32T radio that needs 25G; LAG/ECMP pinning a GTP tunnel to one member; sync or a TDD-pattern clash; and only then the air interface itself. NR radio capability stayed 32T in this swap, so it is the least likely cause; still record MCS, rank, and PRB allocation in the same test so a radio problem is recognised on the day.

## Read in this order

| | Document | What it gives you |
| --- | --- | --- |
| 1 | [How 5G transport rides on 4G](docs/01-how-5g-transport-works-over-4g.md) | Options 3 / 3a / 3x, fronthaul vs backhaul, overhead, the four ways transport hurts throughput |
| 2 | [Baseline and transport budget](docs/02-baseline-and-transport-budget.md) | Proving the drop is real, the Mbit/s budget, the measurement rules, a one-day joint test |
| 3 | [Checks by domain](docs/03-domain-by-domain-checks.md) | RAN, transmission, core, IP, and the rest — check, signature, action, ranked list |
| 4 | [Action plan](docs/04-action-plan.md) | Phases 0–5, owners, exit criteria, questions to send the vendor |
| 5 | [Evidence templates](docs/05-evidence-templates.md) | Site record, hop table, AMBR trace, counters, commands, alarms |
| 6 | [Standards and references](docs/06-standards-and-references.md) | The 3GPP and ITU-T clauses behind each claim |

## Reproduce the budget

```bash
python3 tools/tx_budget.py --preset single-cell
python3 tools/tx_budget.py --preset swap-site --ipsec
python3 -m unittest tools/test_tx_budget.py
```
