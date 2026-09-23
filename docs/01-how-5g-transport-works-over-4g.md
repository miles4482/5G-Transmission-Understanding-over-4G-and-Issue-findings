# 1. How 5G Transmission Works Over 4G

This chapter answers the first question: *what exactly does "5G transport over 4G" mean, and why can a
4G/transport decision silently cap a 5G user's throughput?*

Read this before the analysis chapters, because almost every argument between a RAN vendor and a
transmission team comes from the two sides measuring different things on different interfaces.

---

## 1.1 The deployment option decides who carries the traffic

If your 5G is **NSA (Non-Standalone, EN-DC, "Option 3 family")** — which is what almost every operator
launched with, and what a 2.6 GHz TDD NR layer on top of an existing LTE network normally is — then:

* The **LTE eNodeB is the Master Node (MeNB)**. It owns the RRC connection and the S1-MME signalling.
* The **5G gNodeB is the Secondary Node (SgNB)**. It has **no connection to the MME** and, in some
  variants, no user-plane connection to the core at all.
* The UE is connected to **both** radios at the same time, and a single data session can be split
  across the LTE leg and the NR leg.

3GPP TS 37.340 defines the bearer types. The three commercially relevant user-plane variants:

| Option | Where the user plane splits | What the transport must carry | Practical consequence |
| --- | --- | --- | --- |
| **3** | At the eNB (LTE PDCP/NR PDCP at eNB) | **All NR traffic traverses eNB → gNB over X2-U**, on top of the eNB's own S1-U | Worst case for transport. The eNB site's backhaul must carry the *entire* 5G peak plus its own LTE peak. eNB must buffer at combined peak rate. |
| **3a** | At the S-GW (separate S1-U per node) | Each node has its own S1-U to EPC; almost no X2-U user plane | Cheapest for X2, but no per-packet aggregation gain — the split is per-bearer, not per-packet. |
| **3x** | At the gNB (NR PDCP at gNB) | gNB has its own S1-U carrying the full session; **only the LTE share is sent back gNB → eNB over X2-U** | Best practice, and what most networks use. X2-U carries the smaller (LTE) share. |

**Why this matters to your problem:** in Option 3, and in Option 3x whenever the LTE leg is active, a
5G speed test is *not* a pure 5G transport event. Packets cross an inter-site or intra-site X2-U path,
and the **slowest of {gNB backhaul, eNB backhaul, X2-U path}** sets the ceiling. A transport team that
only measured the 5G cell site's uplink to the aggregation router has, quite genuinely, "found no
issue" while the bottleneck sat on the LTE anchor's port or on the X2 path.

If you are on **SA (Standalone)**, the anchoring argument disappears, but the NG/N3 (gNB → UPF) path
and the UPF placement then become the dominant transport factors instead. Confirm which mode each
market is running before you spend a single hour on analysis; mixed NSA/SA per region is common.

### The single most under-monitored parameter in NSA

In the `SGNB ADDITION REQUEST` (X2-AP), the **MeNB — not the core — chooses the
`SgNB UE Aggregate Maximum Bit Rate`**: the share of the UE-AMBR it is willing to let the 5G node
schedule. A conservative or mis-migrated value here caps NR throughput and is **invisible from the NR
side and from every transport probe you will ever run**. After an eNB vendor swap, this is one of the
highest-probability regressions in the whole system. Chapter 3 gives the check.

---

## 1.2 The three transport segments, and which one you actually changed

Modern 5G RAN splits transport into three segments with wildly different requirements. Conflating them
is the second big source of vendor/operator deadlock.

| Segment | Endpoints | Typical interface | Per-site rate for a 3-sector 100 MHz site | Latency class |
| --- | --- | --- | --- | --- |
| **Fronthaul** | RU/AAU ↔ BBU/DU | eCPRI (7-2x split) or CPRI | **Provisioned with the radio: ~25 Gbit/s per 32T/64T AAU, so 3 × 25GE** | ~100 µs one-way |
| **Midhaul** | DU ↔ CU | F1 | ~5 Gbit/s peak early, growing to ~20 Gbit/s | ~1 ms |
| **Backhaul** | eNB/gNB (or CU) ↔ EPC/5GC | S1/NG (N2/N3) | Same class as midhaul: ~5 Gbit/s peak early | ~10 ms |

Two facts that matter enormously for your specific swap:

1. **Fronthaul is flat and huge; backhaul is statistical and much smaller.** Fronthaul capacity is a
   *hardware provisioning* decision made when the AAU is installed — it does not grow with traffic.
   Huawei 2.6 GHz 32T/64T AAUs (e.g. the AAU5636w class) expose **2 eCPRI ports at 10/25 Gbit/s**, and
   the baseband boards that drive a 32T32R 100 MHz cell are specified around **1 × 25 Gbit/s eCPRI per
   cell**. If a 32T AAU was cabled or negotiated at **10G instead of 25G**, the baseband will restrict
   cell bandwidth and/or MIMO layers. That looks exactly like "throughput below baseline", it is
   genuinely a transmission-capacity problem, and **no backhaul measurement will ever show it.**
2. **The BBU main control board is a hard aggregate ceiling.** On Huawei BBU5900:
   * **UMPTe / UMPTga**: 2 × FE/GE electrical (RJ45) + 2 × FE/GE/**10GE** optical (SFP), with a total
     transmission bandwidth in the **10 Gbit/s** class.
   * **UMPTg**: **25GE** optical ports (YGE1/YGE3).
   * The electrical RJ45 backhaul path is **GE only** — Huawei's own site design guidance says the NR
     backhaul requirement exceeds GE and therefore a **10GE optical module is the default**, not GE
     or 2.5GE.

   **A 5G site that ended up on an RJ45 GE port, or on an SFP negotiated at 1G, is capped at well
   under 1 Gbit/s of goodput — shared with all the LTE carriers on the same BBU.** After a swap this
   is one of the most common single root causes, and it is invisible in end-to-end "the ring is not
   congested" reports.

---

## 1.3 The protocol stack expansion: why "1 Gbit/s of transport" is not 1 Gbit/s of user data

Every user packet on S1-U / N3 / X2-U is encapsulated. From the Ethernet wire's point of view a
1400-byte user payload becomes considerably larger:

| Layer | Bytes | Notes |
| --- | --- | --- |
| Ethernet (incl. preamble + IFG) | ~18–38 | Depends on whether you count preamble/IFG; ~38 on the wire |
| VLAN (802.1Q) | 4 | Per tag; QinQ doubles it |
| Outer IPv4 | 20 | 40 for IPv6 |
| UDP | 8 | |
| GTP-U | 8–12 | 8 minimum, 12 with sequence number / extension headers |
| **IPsec (ESP, tunnel mode)** | **~57–73** | Only if IPsec is used — and it usually is on a swapped network |

3GPP TS 23.501 Annex J works the arithmetic for the IPsec case: on a **1500-byte transport MTU the
total overhead reaches 142 octets**, leaving a maximum user packet of **1358 bytes**. That is the
canonical number to quote to your transport team.

**Two consequences:**

* **Overhead tax.** Without IPsec, plan on **~4–8 %** expansion for typical (1400-byte) packets; with
  IPsec and VLANs, **12–15 %**. A 1 Gbit/s port therefore delivers roughly **870–960 Mbit/s** of user
  goodput at best — before any queueing.
* **Fragmentation cliff.** If the RAN or core sends 1500-byte inner packets into a path whose
  effective MTU is 1358 (or lower), every packet fragments. Fragmentation costs router CPU, doubles
  packet rate, and — if any device drops fragments or PMTUD ICMP is filtered — produces a **PMTUD
  black hole**: TCP connections establish, transfer a few kilobytes, then stall. The user sees
  "throughput collapsed"; every interface counter looks healthy. **This is the single most common
  "there is no transmission issue, but throughput is broken" failure mode after an end-to-end
  vendor change**, because MTU defaults differ per vendor and per board.

The correct design is: **transport MTU ≥ 1600 (jumbo-capable) end to end**, so that the 1500-byte
inner packet survives GTP-U + IPsec without fragmentation. Verify it hop by hop with DF-bit pings,
not from a design document.

---

## 1.4 EN-DC flow control: the mechanism that turns transport latency into lost throughput

This is the part most often missed, and it is why "there is no packet loss, so transport is fine" is
not a valid argument.

Per **TS 36.300 §20.1.1** and **TS 36.425 §5.4.2**, a split bearer runs a **Downlink Data Delivery
Status** loop: the secondary node (gNB) continuously reports delivery status back to the master node
(eNB), and the master node uses it to decide **how much data to forward over X2-U**. It is a closed
control loop over the transport network.

The consequences are non-linear:

* **Latency and jitter on X2-U directly reduce the aggregation gain.** The eNB cannot keep the NR leg's
  buffer optimally filled if its feedback is stale, so it under-feeds the fast leg. Throughput drops
  even though **no packet was lost and no link was full.**
* **Differential delay between the two legs causes PDCP reordering.** The receiver must hold packets
  until the gap closes; the reordering window is set by `pdcp-SN-SizeDL` (12 or 18 bits). With
  `len12bits` and a high-rate split bearer whose legs have very different delay, the window can be
  the limiting factor. `len18bits` gives far more room and is the right setting for high-rate NR
  split bearers.
* **TCP amplifies it.** A single TCP flow is limited to `window / RTT`. Adding 10 ms of RTT — by
  rehoming to a different aggregation site, a different UPF/PGW, or a longer IPsec path — can halve a
  single-stream speed test result with **zero** loss and **zero** congestion. If the swap also moved
  the S-GW/UPF or the internet peering point, **the "5G degradation" may be entirely a
  latency/BDP effect**, measurable only by comparing RTT to the test server before and after.

So the honest framing to bring to the vendor–Tx meeting is:

> Transport can degrade 5G throughput through **four independent mechanisms**: insufficient capacity,
> packet loss, **added latency/jitter**, and **MTU/fragmentation**. The transmission team has usually
> only disproven the first two. The last two leave every traditional transport KPI green.

---

## 1.5 Why the vendor says "transmission" and the Tx team says "no issue" — both can be right

They are answering different questions:

| | RAN vendor's claim | Tx team's claim |
| --- | --- | --- |
| **Question answered** | "Can the transport deliver the *peak* rate the radio can schedule, at the *instant* it is scheduled?" | "Is any link *unavailable, errored, or congested on average*?" |
| **Typical evidence** | gNB flow-control / discard / retransmission counters, buffer occupancy, per-second bursts | 5- or 15-minute average interface utilisation, alarm history, availability reports |
| **Blind spot** | Rarely proves *which* transport element; often just "transport is slow" | **Averaging.** A 10 Gbit/s burst into a 1 Gbit/s port for 200 ms is a total throughput killer and shows up as ~2 % on a 15-minute average. Also blind to MTU, QoS remark, and added latency. |

**The resolution is a measurement-methodology agreement, not an argument.** The deadlock breaks when
both sides accept the same evidence: per-second (or at minimum 1-minute p95/p99) counters on the exact
ports carrying S1-U/X2-U/N3, plus an active throughput test that isolates each segment. Chapters 2–5
build that evidence chain.

---

## 1.6 What changed in *your* network — the honest risk list

You swapped Ericsson → Huawei **end to end, including transmission**, and simultaneously increased
radio capacity substantially:

| Layer | Before (Ericsson) | After (Huawei) | Transport implication |
| --- | --- | --- | --- |
| LTE FDD | 2T | 4T | Higher LTE cell throughput → **more backhaul demand from the anchor**, competing with 5G on the same port |
| LTE TDD | 4T | 32T | Large LTE TDD capacity increase; if it shares the 2.6 GHz AAU and the same BBU, it shares fronthaul and backhaul too |
| NR TDD | 32T | 32T | Radio config nominally unchanged → **if 5G throughput fell, the radio is the least likely cause** |
| Transport | Mixed / legacy | Huawei end to end | New MTU defaults, new QoS/DSCP maps, new shaping/policing, possibly new IPsec, possibly new UPF/S-GW anchor and new RTT |
| New 5G sites | n/a | Greenfield Huawei | These have **no baseline at all** — do not average them with swapped sites, or you will corrupt the comparison |

Three high-value observations fall straight out of this table:

1. **The NR radio configuration is essentially unchanged (32T → 32T).** So the regression is very
   unlikely to be an NR air-interface capability problem. That shifts prior probability strongly
   toward transport, transport-adjacent RAN configuration (MTU, QoS, X2/SgNB-AMBR), and core/policy.
2. **Total site demand went up a lot while the site's physical port may not have changed.** If the
   FDD and TDD LTE upgrades and the NR layer all land on one BBU with one 10GE (or worse, GE)
   backhaul port, the vendor's "transmission capacity" claim is *dimensionally* correct even though no
   link is "faulty". This is a **dimensioning** finding, not a **fault** finding — which is exactly
   why the two teams disagree.
3. **You must separate KPI-definition change from real degradation before anything else.** Ericsson
   and Huawei do not compute "user throughput" identically. Both follow the TS 28.552 /
   TS 32.425 pattern (`ThpVol / ThpTime`, excluding the last slot that empties the buffer), but
   Ericsson's EN-DC counters measure volume **on PDCP PDU level for UEs in EN-DC stage 2 and on PDCP
   SDU level for other UEs**, whereas the Huawei equivalents are defined per its own counter
   reference. Different layer, different burst-exclusion rule, different EN-DC filter, different
   aggregation scope → **easily a 10–30 % apparent delta with no physical change whatsoever.**
   Chapter 2 makes this Step 0 for a reason.

---

## 1.7 Reference map: interface → what rides on it → what breaks it

| Interface | Between | Carries | Breaks throughput when… |
| --- | --- | --- | --- |
| eCPRI / CPRI (fronthaul) | AAU ↔ BBU/DU | I/Q or split-7.2x samples | Rate negotiated below 25G for 32T/64T; optical budget/CRC errors; cascading beyond spec |
| S1-U | eNB ↔ S-GW | LTE user plane (GTP-U) | Port/QoS/MTU; anchor congestion (dominant in Option 3) |
| S1-MME | eNB ↔ MME | LTE signalling (SCTP) | SCTP retransmission → slow/failed SgNB addition |
| X2-C | eNB ↔ gNB | SgNB addition/modification (SCTP) | Loss → EN-DC setup failure or fallback to LTE-only |
| **X2-U** | eNB ↔ gNB | Split-bearer user plane + **DDDS flow control** | Capacity, **latency, jitter**, MTU, DSCP misclassification |
| NG-C / N2 | gNB ↔ AMF | SA signalling | — |
| **NG-U / N3** | gNB ↔ UPF | SA user plane (GTP-U) | Capacity, MTU, UPF placement/RTT, Session-AMBR |
| N6 / SGi | UPF/PGW ↔ internet | Post-core traffic | Peering congestion, CGNAT, TCP proxy, test-server capacity |
| Sync (PTP/GNSS) | Grandmaster ↔ node | G.8275.1 / 1PPS | TDD needs phase sync; holdover → interference → throughput loss |

Continue to [Chapter 2: Baseline, budget and the measurement contract](02-baseline-and-transport-budget.md).
