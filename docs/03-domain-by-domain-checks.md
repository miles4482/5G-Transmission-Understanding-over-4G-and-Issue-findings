# 3. Domain-by-Domain Checks and Action Points

Every place a 5G user packet can be slowed down, with the check that proves it and the action that
follows. Work top to bottom. The early checks are configuration reads; they close most swap-related
cases before anyone opens a packet capture.

Counter and MML names below come from Huawei base-station performance references (multi-mode Node and
gNodeBFunction). **Confirm the exact name in the counter reference for your software version** before
you build a report on it. Where a name is given, it was taken from a published reference; where a
check is described without a counter name, the object model differs enough between releases that
inventing one would be worse than leaving it out.

Companion documents: [how the transport actually works](01-how-5g-transport-works-over-4g.md),
[the budget and the measurement rules](02-baseline-and-transport-budget.md),
[the phased plan](04-action-plan.md).

---

## 3.0 Decision tree — localise before you deep-dive

Run this on one degraded swapped site and one healthy new Huawei site, then diff.

```
A. Single-UE test, NR cell only (force LTE leg off / block EN-DC)
   |
   +-- throughput near the TS 38.306 ceiling (Ch.2) --> radio and gNB backhaul are fine.
   |     The loss appears only when the LTE leg or the core path is added.
   |     Go to: X2-U (3.1.6), SgNB AMBR (3.1.7), core AMBR (3.3.1), RTT (3.3.3).
   |
   +-- throughput stuck near 900-950 Mbit/s, flat, any radio condition
   |     --> GE port or GE-equivalent hop. Go to 3.1.1 and 3.2.1.
   |
   +-- throughput stuck at a round policy number (100 / 150 / 300 / 500 / 1000 Mbit/s)
   |     --> AMBR, license, or policer. Go to 3.1.7, 3.1.8, 3.3.1, 3.2.4.
   |
   +-- TCP stalls after a few MB, UDP at the same rate is fine
   |     --> MTU / PMTUD black hole. Go to 3.1.4 and 3.4.1.
   |
   +-- UDP ramps cleanly to ~2 Gbit/s but TCP does not
   |     --> latency, loss, or server window. Go to 3.4.2 and 3.5.2.
   |
   +-- both UDP and TCP cap well below the port rate, and it moves with RSRP/rank
         --> this is radio, not transport. Go to 3.5.1 before spending more on Tx.
```

If the healthy new site passes step A and the swapped site fails it, the delta between them is the
investigation. If both fail the same way, the cause is common (core policy, a shared aggregation
node, the test server) and per-site RAN work will not fix it.

---

## 3.1 RAN-side transmission

The base station is itself a router. It has ports, IP paths, shapers, an MTU, a QoS map, and — in
NSA — an X2 path whose behaviour the transport team cannot see.

### 3.1.1 Backhaul port: negotiated rate, not designed rate

| Check | How | Fail looks like | Action |
| --- | --- | --- | --- |
| Main control board | Inventory: UMPTe / UMPTga (10GE class, ~10 Gbit/s aggregate) vs UMPTg (25GE ports) | 32T site on UMPTe with only one optical port in use, carrying LTE FDD + LTE TDD + NR | Move NR (or the whole site) to a 10GE optical port; plan UMPTg or a second 10GE where the busy-hour budget in Ch.2 exceeds ~7 Gbit/s |
| Negotiated speed | Port status on the BBU and on the facing CSG/ATN port. Both ends. | One side 10GE, the other auto-negotiated to **1GE**; or an electrical RJ45 in use (GE only, per Huawei site design) | Force 10GE full duplex both ends. Replace 1G SFPs. Remove RJ45 backhaul from every 5G site. |
| Errors | `VS.FEGE.RxErrPackets`, CRC, and the Tx/Rx max speeds `VS.FEGE.TxMaxSpeed`, `VS.FEGE.RxMaxSpeed` against `VS.FEGE.TxMeanSpeed` | Max near line rate while Mean looks idle; or rising error packets | Max-near-line-rate = microburst congestion, go to 3.2. Optics errors = clean the patch, swap the SFP, check the optical budget. |
| Duplex / pause | Both ends full duplex; note whether 802.3x pause is on | Half duplex, or pause frames incrementing | Lock full duplex. Pause on a RAN port back-pressures the whole BBU; find the congested downstream queue instead of relying on pause. |

**Exit criterion:** every 5G site shows 10GE (or 25GE) negotiated, full duplex, zero error growth over 24 h, and `TxMaxSpeed` during a controlled speed test reaches the radio's demand without sitting on the line rate.

### 3.1.2 Fronthaul: 32T needs 25G eCPRI, and this is invisible to the backhaul team

Huawei 2.6 GHz 32T/64T AAUs (AAU5636w class) expose **two eCPRI ports at 10/25 Gbit/s**, and a 100 MHz 32T32R cell is specified at **1 × 25 Gbit/s eCPRI**. A link that trained at 10G restricts cell bandwidth or the number of layers. The user throughput falls. The S1/NG interface stays quiet and healthy.

| Check | How | Action |
| --- | --- | --- |
| Negotiated eCPRI rate per AAU | Port status on the UBBP (UBBPfw1 / UBBPg class) and on the AAU. Expect 25.78125 Gbit/s. | Recable or refit the optical module. 25G SFP28, correct fibre type, within the optical budget. |
| Errors and FEC | eCPRI port measurement (`ECPRIPORT` in the Node counter reference: `VS.ECPRIPORT.*` Rx/Tx). | Any growth in error/drop counters: swap the optical module, check bend radius and patch cleanliness. |
| Cascading | AAU5636w-class AAUs do not support CPRI cascading toward the BBU. | Remove any leftover Ericsson-style cascade. One AAU, one direct eCPRI link. |
| Distance | Spec distance is ~20 km on the right optical module. | Beyond that, move the BBU or add the transport the design allows; do not stretch the optical budget. |

**Exit criterion:** every 32T AAU reports 25G, zero error growth, one hop to its baseband board.

### 3.1.3 IP path and transmission resource group: the shaper inside the base station

Huawei carries user plane on an IP path. The path has a configured bandwidth, and it can sit on a
transmission resource group that **shapes**. A resource group left at a default, or copied from the
old 2T FDD design, will pace a 1.7 Gbit/s NR flow down to whatever number was typed in during
commissioning. This is a RAN-configuration transmission limit. It never appears on a router interface.

| Check | How | Action |
| --- | --- | --- |
| IP path bandwidth | Dump every user-plane IP path on the eNB and the gNB. Compare configured TX/RX bandwidth with the Ch.2 budget for that site. | Raise the path bandwidth to at least the single-user peak (about 2.2 Gbit/s for one 100 MHz cell) and above the busy-hour figure where several cells share the path. |
| What the path is bound to | `CARRYFLAG`: `IPLGCPORT` (a logical port), `RSCGRP` (a resource group), or `NULL` (the physical port). | If `RSCGRP`, open the resource group and read its bandwidth. This is the actual ceiling. |
| Drops on the path and the group | `VS.IPPath.TxDropPkts`, `VS.IPPath.RxDropPkts`, `VS.IPPath.TxMaxSpeed` vs `VS.IPPath.TxMeanSpeed`; `VS.RscGroup.TxDropPkts`, `VS.RscGroup.TxDropBytes`, `VS.IPRscGroup.TxDropPkt` | Non-zero drops during a speed test, with `TxMaxSpeed` flat at the configured bandwidth, is a confirmed shaper. Raise it or remove it. |
| One path shared by LTE and NR | List which cells and which RATs ride which path and which VLAN. | After the 2T→4T and 4T→32T upgrade, the LTE share grew. If NR was added onto the same shaped path, split NR onto its own path and its own bandwidth allocation. |

**Exit criterion:** during a single-UE peak test, `VS.IPPath.TxDropPkts` does not increment and `TxMaxSpeed` is below the configured path bandwidth.

### 3.1.4 MTU, fragmentation, and IPsec

This is the failure mode that leaves every utilisation graph green.

| Check | How | Action |
| --- | --- | --- |
| Interface MTU on BBU, CSG, aggregation, CSG-to-core, and the S-GW/UPF | Read it. Do not trust the design document. Target **≥ 1600** on every hop that carries GTP-U so a 1500-byte inner packet survives GTP-U + UDP + IP + VLAN, and **≥ 1700** where IPsec is added (TS 23.501 Annex J puts IPsec overhead near 142 bytes, leaving a 1358-byte user packet on a 1500-byte transport MTU). | Raise the MTU on the short hop. If one leased-line hop cannot move, lower the **advertised link MTU / TCP MSS** to the real path MTU so clients stop sending packets that will fragment. |
| DF-bit behaviour | From the gNB service IP, ping the S-GW/UPF user-plane IP with DF set at 1400, 1472, 1500, 1600 bytes. Repeat toward the eNB X2-U address. | The largest size that passes **is** the path MTU. Anything below 1500 means inner packets fragment or black-hole. |
| Fragment counters | `VS.IP.RxDropPkts`, `VS.IP.TxDropPkts`, `VS.Gtpu.RxDropPkts`, `VS.Gtpu.RxDropBytes`, and fragment/reassembly counters on the CSG and the UPF. | Drops that rise only when the speed test uses full-size packets are an MTU fault. |
| IPsec | Confirm whether the swap turned IPsec on, changed the cipher, or moved the tunnel endpoint. `VS.IPSec.RxESPFailDropPkts` (reference name `VS.IPSec.RxESPFailDropP…`) must be flat. Check the IPsec engine's **licensed throughput**, not just that the tunnel is up. | A tunnel that is up and a throughput cap at a round number (1 Gbit/s, 2 Gbit/s) is a licence or an crypto-engine limit. Upgrade the licence or terminate IPsec somewhere with the capacity. |
| PMTUD | ICMP "fragmentation needed" (IPv4 type 3 code 4) and "packet too big" (IPv6 type 2) must be allowed on the GTP path and on N6/SGi. | If a firewall drops them, TCP stalls after the slow-start window exceeds the path MTU. Allow the specific ICMP types; do not open ICMP broadly. |

**Exit criterion:** a 1500-byte DF ping passes gNB→UPF and eNB↔gNB, fragment counters stay at zero during a full-size TCP download, and the negotiated MSS observed on N6 matches the path.

### 3.1.5 QoS marking inside the RAN

The base station marks GTP-U packets with a DSCP (commonly mapped from QCI/5QI). The transport network
then queues on that DSCP. Two swap failures are routine:

* The Huawei default DSCP for QCI 9 / 5QI 9 differs from the Ericsson value the transport policy was built for. User plane lands in the **scavenger / best-effort queue**, which is small on microwave and on aggregation routers.
* The transport policy was rebuilt "clean" during the Huawei E2E swap and the new map **polices** the data class to a CIR copied from LTE-era numbers.

| Check | How | Action |
| --- | --- | --- |
| DSCP on the wire | Capture 60 seconds at the CSG facing the BBU during a speed test. Record DSCP on GTP-U (UDP 2152) for S1-U, N3, and X2-U separately. | Build a one-page map: QCI/5QI → RAN DSCP → transport class → queue size → CIR/PIR. |
| Class continuity | Compare that DSCP at the CSG, at the aggregation egress, and at the core ingress. | Any hop that rewrites DSCP to 0, or that classifies only on VLAN and ignores DSCP, gets a corrected policy. |
| X2-U specifically | X2-U carries the split-bearer data **and** the TS 36.425 Downlink Data Delivery Status feedback. Both must sit in a low-latency class, not best effort. | Put X2-U in the same latency class as signalling, with a PIR large enough for the LTE-leg share (Option 3x) or the full NR share (Option 3). |

**Exit criterion:** a speed-test flow is observed in the intended class at every hop, and that class has no drops during the test.

### 3.1.6 X2-U: the 4G/5G seam

This is the direct answer to "how does 5G transmission depend on 4G".

| Check | How | Action |
| --- | --- | --- |
| Which EN-DC option | Read the bearer configuration. Option 3 sends **all** NR user plane across X2-U. Option 3x sends only the LTE share. | If you are on Option 3, either provision X2-U for the full NR peak (~2.2 Gbit/s per active cell, see Ch.2) or migrate the user-plane split to Option 3x so the gNB has its own S1-U. |
| X2 path physical route | Trace the eNB X2 IP to the gNB X2 IP: same BBU (internal), same site different boxes, or hairpin via the aggregation site. | A hairpin to the aggregation router and back adds milliseconds and shares the backhaul port twice. For co-sited NSA, terminate X2 locally. |
| Loss, delay, jitter on X2 | Enable TWAMP on the base station (`BSTWAMP` measurement: `VS.BSTWAMP.Rtt.Means`, `VS.BSTWAMP.MaxRttDelay`, `VS.BSTWAMP.Forward.DropMeans`, `VS.BSTWAMP.Forward.Peak.DropRates`, and the jitter counters) or Ethernet OAM (`VS.ETHDM.MaxRttDelay`, `VS.ETHDM.Rtt.Means`, `VS.ETHLM.Forward.Drop…`). Run it **in the X2-U DSCP**. | Peak drop rate above zero, or RTT jitter in the milliseconds, means the flow-control loop is being starved of fresh buffer reports. Fix the queue, then re-test. |
| Retransmission on X2-U | `N.PDCP.DL.X2U.TrfPDU.TxPackets` against `N.PDCP.DL.X2U.ReqRetransPackets`, and the volume counters `N.PDCP.Vol.DL.X2U.TrfPDU.Tx`, `N.PDCP.Vol.UL.X2U.TrfPDU.Rx`. | A retransmission ratio that tracks the throughput drop is transport loss on X2-U, even when S1-U looks clean. |
| EN-DC setup health | `N.NsaDc.SgNB.Add.Att`, `N.NsaDc.SgNB.Add.Succ`, `N.NsaDc.SgNB.AbnormRel.Trans` (abnormal release, transport cause). | A rising `AbnormRel.Trans` is the gNB itself declaring a transport cause. Pair each spike with the port and IP-path counters at the same timestamp. |
| PDCP SN size | `pdcp-SN-SizeDL` on the split bearer: 12-bit vs 18-bit. | For a high-rate NR split bearer use **18-bit**. A 12-bit reordering window is small relative to the SN gap two legs of very different delay can open, and the receiver stalls. |

**Exit criterion:** SgNB addition success stays at the pre-swap level, `AbnormRel.Trans` is ~0, X2-U TWAMP peak loss is 0, and NR throughput with the LTE leg enabled is at least the NR-only result (leg on must not reduce the total).

### 3.1.7 The silent cap: SgNB UE Aggregate Maximum Bit Rate

In the X2-AP `SGNB ADDITION REQUEST` the **LTE eNB** sets `SgNB UE Aggregate Maximum Bit Rate` — the
share of UE-AMBR it will allow the gNB to schedule. The MME does not set it. It does not appear in any
transport counter.

| Check | How | Action |
| --- | --- | --- |
| Decode one addition | Trace X2-AP on a test UE. Read `SgNB UE Aggregate Maximum Bit Rate` UL and DL. | If it is a round LTE-era number (150, 300, 450 Mbit/s), the eNB configuration was not updated for NR. Raise the MeNB's EN-DC AMBR split parameters so the gNB receives the full non-GBR entitlement. |
| Compare with the core | The value cannot exceed the UE-AMBR the MME sent on S1. If S1 UE-AMBR is already low, fixing the eNB does nothing; fix the subscription (3.3.1). | Align HSS APN-AMBR, MME UE-AMBR, and the eNB split. One change, all three checked. |
| Per-PLMN and per-QCI exceptions | Roamers and MVNOs often have a separate, tighter profile that survived the swap untouched. | Check the profile the complaint SIMs actually use, not the lab SIM. |

**Exit criterion:** on a decoded trace the SgNB AMBR is at or above the throughput target, for the commercial subscriber profile.

### 3.1.8 RAN licences, scheduler, and board load

| Check | How | Action |
| --- | --- | --- |
| Throughput / peak-rate licence | Licence file on the gNB: cell throughput cap, user throughput cap, layer count, 256QAM enabled. | A licence left at a trial value produces a perfectly flat ceiling. Expand the licence. |
| 256QAM and MIMO layers actually in use | During the test, record MCS table (TS 38.214, 256QAM needs the higher MCS table), RI (rank indicator), and scheduled layers. | If the UE stays at rank 2 or 64QAM, the ceiling is radio or UE capability, and transport is not the constraint. Fix RI/CSI reporting, beamforming weights, and UE capability filtering before chasing transport. |
| Baseband and main-control CPU | Board CPU during the test. | Sustained CPU above the vendor's engineering limit drops scheduling. Move cells off the busy board or add a baseband board. |
| User count and scheduler fairness | A speed test while the cell is busy is shared by the scheduler. | Compare busy-hour results with a low-load window. Quote both. A transport problem shows the same ceiling in an empty cell; a scheduler problem does not. |

### 3.1.9 Synchronisation (TDD only, and it masquerades as capacity)

A 2.6 GHz TDD layer needs phase alignment, not just frequency. Cross-link interference from a
drifting site, or from a site whose TDD pattern does not match its neighbours, raises UL and DL
BLER and cuts throughput. Nothing in the transport utilisation graph moves.

| Check | How | Action |
| --- | --- | --- |
| Sync source after the swap | GNSS on the main board, or PTP (G.8275.1 full timing support) from the new Huawei transport. Confirm the board variant actually has a satellite receiver (UMPTe1-class boards do not). | Sites that lost GNSS during the swap and fell back to a frequency-only clock need a PTP path with boundary/ordinary clocks designed for TDD, or a GNSS refit. |
| Clock quality | PTP lock state, time error estimate, holdover flag, at the BBU. | Any site in holdover or unlocked is excluded from the throughput study until it locks. Otherwise it pollutes the average. |
| TDD pattern consistency | Compare `tdd-UL-DL-ConfigurationCommon` across neighbouring 2.6 GHz cells, including cells still on a different software or a different vendor. | One site on a different pattern from its neighbours creates cross-link interference at the pattern boundary. Align the pattern, then re-measure. |

---

## 3.2 Transmission network (first mile, IP RAN, microwave, fibre)

The Tx team's statement "there is no Tx issue" is accepted as true **for the checks they ran**. This
section is the list of checks that statement usually does not cover. Agree it in the measurement
contract (Ch.2, Rule 5) before commissioning more tests.

### 3.2.1 First mile is the capacity, not the core ring

Most capacity misses sit between the BBU and the first aggregation node: the CSG port, the microwave
hop, the GPON/XGS-PON profile, the leased-line EVC, or a 1G tail on an otherwise 10G ring.

| Check | How | Action |
| --- | --- | --- |
| Draw the path for 20 sites | BBU port → CSG port → access hop → aggregation → core edge. Write the **configured CIR and the physical rate** of each hop. | Any hop below the Ch.2 single-user requirement (~2.2 Gbit/s) is a confirmed bottleneck for peak throughput, regardless of ring utilisation. |
| Microwave | Current modulation, channel width, ACM minimum, and the **guaranteed** (not peak) throughput. | Dimension the guaranteed rate, at the ACM floor you are willing to live with in rain, to at least the busy-hour budget. If the floor is below the single-user peak, a speed test during a fade will fail and look random. |
| PON | The service profile (CIR/AIR) on the OLT, per site. | GPON profiles inherited from LTE (for example 300/100 or 1G/1G) cannot carry a 100 MHz NR peak. Move 5G sites to XGS-PON or to active Ethernet with a 10G CIR. |
| Leased line / EVC | The contracted CIR and burst size (CBS/EBS), from the provider's service record, not from your router config. | Police happens at the provider edge. Your CSG can show an idle link while the provider policer drops. Ask for drop counters on the EVC, or run a Y.1564 test. |
| Ring protection state | Confirm no ring is running on its protection path, and no LAG member is down. | A 2×10G LAG with one member down is a 10G link with the traffic of a 20G design. Restore the member; alert on member-down, not only on bundle-down. |

### 3.2.2 Policing versus shaping, and the CIR copied from LTE

A policer drops. A shaper queues. A CIR set to an LTE-era average (200–600 Mbit/s) with a small CBS
will pass every availability check and destroy a 1.7 Gbit/s burst inside a few milliseconds.

| Check | How | Action |
| --- | --- | --- |
| Per-class CIR/PIR/CBS | On the CSG egress toward the ring, the aggregation egress toward the core, and any provider EVC. For the queue that actually carries QCI 9. | PIR at least the single-user peak; CBS large enough to absorb a TCP slow-start burst (tens of ms at line rate, not the default few kB). Prefer shaping toward the core and policing only at the true capacity edge. |
| Queue drops at low average utilisation | Output-drop, tail-drop, and WRED counters **per class**, at ≤ 60 s, over a window that includes a speed test. | Drops with mean utilisation under 30 % are a microburst or a too-small CBS. Increase CBS and queue depth for the data class; do not raise the mean-utilisation alarm threshold and call it fixed. |
| Buffer on microwave and on low-speed tails | Buffer size versus the bandwidth-delay product of the hop. | A shallow buffer plus a high-latency hop produces loss at modest rates. Increase the data-class buffer where the platform allows, and keep signalling in a separate small priority queue so the extra buffer does not delay X2-C/S1-MME. |

### 3.2.3 QoS trust boundary

| Check | How | Action |
| --- | --- | --- |
| Trust | Which hops trust DSCP, which reclassify, which mark down. | Trust DSCP from the BBU on the access port (the BBU is yours), and keep the mark stable to the core. |
| VLAN-only classification | Common after a swap: the new VLAN carrying NR is not in the class map, so it falls into default. | Add the NR user-plane VLAN and the X2 VLAN explicitly. Verify with the capture from 3.1.5. |
| Queue weights | The data class must be allowed to use idle priority bandwidth. | A hard cap on the data class "to protect signalling" at a few hundred Mbit/s recreates the problem. Use priority for signalling with a policer, and let data take the rest. |

### 3.2.4 The latency the swap added

Capacity can be fine and throughput still drops, because a single TCP flow is limited by
`window / RTT` and because EN-DC flow control degrades with X2 delay and jitter.

| Check | How | Action |
| --- | --- | --- |
| RTT, same UE, same server, before vs after | You need a number from the Ericsson period (drive-test logs, probe history) and a number now. | If RTT to the test server rose by more than a few ms with no radio cause, find the hop that added it: new aggregation site, new IPsec gateway, new firewall, new UPF location, hairpin routing. |
| Per-segment delay | TWAMP or Y.1731: BBU→CSG, CSG→aggregation, aggregation→UPF, and eNB↔gNB. `VS.BSTWAMP.Rtt.Means` and `VS.BSTWAMP.MaxRttDelay` cover the BBU-originated part. | The segment whose delay is both large and variable is the one to redesign. Jitter hurts EN-DC more than a fixed offset does. |
| Asymmetric routing | Forward and return path traced (TTL-limited probes, or interface counters during the test). | Asymmetry inflates RTT and defeats stateful firewalls. Make the user-plane return path explicit. |

### 3.2.5 Sync distribution is a transmission deliverable

If TDD phase sync moved from per-site GNSS to PTP over the new Huawei transport, the transport
network must meet **ITU-T G.8275.1** full timing support: boundary clocks or ordinary clocks on the
path, not transparent-clock guesses, and a time-error budget that leaves the air-interface error
inside the TDD requirement (the network budget commonly quoted for this profile is on the order of
1100 ns, leaving margin to the ±1.5 µs air-interface figure).

| Check | How | Action |
| --- | --- | --- |
| PTP profile and hop count | Grandmaster → every boundary clock → BBU. Confirm full timing support, and that every node on the path is PTP-aware. | A single non-PTP switch in the path breaks the budget. Reroute sync or insert a boundary clock. |
| Time error at the BBU | Vendor clock-quality report, over 24 h, including holdover events. | Sites exceeding the budget are radio problems caused by transport. Treat them as P1 sync faults, separate from the throughput study. |

---

## 3.3 Core-side transmission and policy

"Core-side Tx" splits into two things people mix up: the **policy ceiling** (AMBR), which is not
transmission at all but produces the identical symptom, and the **user-plane path** through the
S-GW/PGW or UPF, which is transmission.

### 3.3.1 AMBR: the ceiling that looks exactly like a full link

For NSA the relevant objects are in TS 23.401:

* **APN-AMBR**, stored per APN in the HSS, enforced by the P-GW in downlink and by the UE and P-GW in uplink. It caps the sum of non-GBR bearers on that APN.
* **UE-AMBR**, derived by the MME as the sum of active APN-AMBRs bounded by the subscribed UE-AMBR, enforced by E-UTRAN in both directions.
* On top of those, the eNB's own **SgNB UE AMBR** (3.1.7) can be lower still.

For SA the equivalents are Session-AMBR (enforced in the UPF) and UE-AMBR (enforced in the RAN), per TS 23.501 §5.7.2.6 and §5.7.1.8.

| Check | How | Action |
| --- | --- | --- |
| Read the profile the customer actually has | HSS/UDM dump for the test MSISDN and for two complaining subscribers: APN-AMBR UL/DL, UE-AMBR UL/DL, and any roaming restriction (`NR Restriction in EPS as Secondary RAT`, `restrictDCNR`). | Raise APN-AMBR and UE-AMBR to at least the peak of one NR cell (~1.7 Gbit/s DL, ~300 Mbit/s UL for the Ch.2 configuration) for profiles that are sold as unlimited 5G. Keep a lower profile only where the product genuinely includes one. |
| Confirm what was signalled | S1AP Initial Context Setup: UE-AMBR. NAS Attach Accept: APN-AMBR. X2AP SgNB Addition: SgNB UE AMBR. All three, one trace. | The smallest of the three is the ceiling. Fix that element. |
| Watch for the 1 Gbit/s boundary | Several stacks have mishandled the encoding at exactly 1 Gbit/s / 1024 Mbit/s. If the cap sits at ~1 Gbit/s while the subscription says unlimited, try a value just below and just above and compare. | If the behaviour changes at the boundary, it is an encoding/interop defect between MME/HSS and the new eNB. Raise a vendor case with the trace; use a temporary value that encodes cleanly so customers are not held at the boundary. |
| PCRF/PCF override | A dynamic rule can lower APN-AMBR per location, per time, or per FUP (fair-usage) state. | Check the rule that hit the test subscriber. A fair-usage policy applied by default after the swap is a product decision, not a fault — but it must be labelled as such and excluded from the engineering baseline. |

**Exit criterion:** one traced session shows HSS, MME, and eNB AMBR all above the target, and the measured throughput is no longer a round number matching any of them.

### 3.3.2 S1-U / N3 capacity at the core edge

| Check | How | Action |
| --- | --- | --- |
| S-GW/PGW or UPF interface rates | p99 throughput and drops on the S1-U/N3 facing interfaces, and on the N6/SGi facing interfaces, at ≤ 60 s. | If p99 sits on the port or on the licensed throughput of the gateway, add capacity or rebalance S-GW/UPF selection. |
| Gateway selection after the swap | Which S-GW/UPF does the swapped region now land on? Compare with the Ericsson period. | A whole region moved onto one gateway, or onto a remote gateway, shows up as extra RTT plus a shared bottleneck. Rebalance DNS/NRF selection so the region uses a local gateway. |
| Per-bearer shaping on the gateway | Some P-GW/UPF builds rate-limit non-GBR bearers to a default (for example 1 Gbit/s) independently of AMBR. | Read the default bearer shaping template applied to the new APNs. Remove the hidden template cap. |

### 3.3.3 Path length, DPI, and TCP proxies

| Check | How | Action |
| --- | --- | --- |
| Inline DPI / firewall / CGNAT added or moved | Compare the service chain before and after the swap. | Each inline box adds latency and has its own pps and throughput licence. Measure RTT with it in and out of path for one test APN. |
| TCP optimisation | Ericsson cores are often deployed with a TCP proxy. A Huawei core swap frequently **removes** it, or inserts a different one. | If single-stream throughput fell and multi-stream did not, measure server RTT and window. Decide explicitly whether a TCP optimiser is in the design; do not leave its presence to the default build. |
| N6 peering and cache | Throughput from the UPF to your speed-test server, using UDP and TCP, from a host on the SGi LAN. | If this hop is the first one that loses rate, the RAN and the transport are cleared. Fix peering, the cache, or the test server (3.5.2). |

### 3.3.4 Control plane, because it removes the 5G leg entirely

A transport problem on S1-MME or X2-C does not slow throughput. It drops the UE back to LTE, and the
"5G throughput" KPI then mixes in LTE-only samples.

| Check | How | Action |
| --- | --- | --- |
| SCTP retransmission | SCTP retransmit and congestion counters on S1-MME and X2-C. | Retransmits mean loss or a too-aggressive RTO on the signalling class. Fix the queue; keep signalling in a priority class with a policer rather than a deep buffer. |
| SgNB addition failure causes | Break down `N.NsaDc.SgNB.Add` failures by cause: transport, radio, licence, capacity. | Transport-cause failures go to 3.1.6. A step-change at the swap date with cause "radio" or "capability" is a parameter migration issue (3.5.3), not Tx. |

---

## 3.4 IP network

Everything after the RAN port is an IP network, whether the Tx team or the IP core team owns the box.
These checks catch the cases where every individual link is within target and the **path** is still wrong.

### 3.4.1 MTU consistency across domains

The MTU has to be the same story from BBU to UPF. One domain at 1500 and the next at 1600 means
fragmentation at the boundary.

| Check | How | Action |
| --- | --- | --- |
| MTU per domain | Access, aggregation, core, interconnect, firewall, IPsec, SGi. One table. | Set a network-wide underlay MTU (1600 without IPsec, 1700+ with it) and a documented UE link MTU. |
| ICMP filtering | Filter policy on every security device in the user-plane path. | Permit ICMP fragmentation-needed and packet-too-big both ways. |
| MSS clamping | Where it is applied (firewall, CGNAT, TCP proxy). | Clamp to the real path MSS so TCP never depends on PMTUD. Clamping fixes TCP only; UDP and IPsec still need a correct MTU. |

### 3.4.2 ECMP and LAG: one GTP tunnel is one flow

GTP-U uses **UDP port 2152 at both ends**. All the traffic of a bearer, and often of a whole
node-pair, shares one source IP, one destination IP, and one UDP port pair. A 5-tuple ECMP or LAG
hash therefore pins a user's entire throughput to **one member link**.

Two consequences:

* A 4×10G bundle does not give one user 40G. It gives one user whatever one member has left.
* If the hash is only IP-based, **every** bearer between a given gNB and a given UPF uses the same
  member. One site's whole 5G throughput sits on one 10G link while the other three are idle. This
  is the classic post-migration surprise when the new IP design introduced ECMP that the old one did
  not have.

| Check | How | Action |
| --- | --- | --- |
| Hash algorithm on every LAG and ECMP group in the user-plane path | Read it. Identify whether the GTP TEID is an input. | Enable TEID-aware hashing where the platform supports it (vendor features exist on Cisco, Juniper, and others; the mechanism is "hash the TEID, because the UDP ports are constant"). This balances **bearers** across members. It does not split **one** bearer. |
| Polarisation | Consecutive routers using the same hash and the same seed. | Vary the hash seed per hop so a flow that lands on member 1 at the first router does not always land on member 1 at the next. |
| Member utilisation during a test | Per-member p99, not bundle average, while one site runs a peak test. | One member at line rate with its siblings idle confirms polarisation. TEID hashing plus a seed change is the fix; adding more members without changing the hash does nothing for a single flow. |
| IPsec and the same problem | An IPsec tunnel collapses the inner flows into one outer flow unless the gateway does per-TEID load distribution inside the tunnel. | Check the IPsec gateway's per-tunnel throughput and whether it can spread one tunnel across crypto cores. A single tunnel capped at one core's rate is a known cause of a flat regional ceiling. |

### 3.4.3 Firewalls, CGNAT, and route symmetry

| Check | How | Action |
| --- | --- | --- |
| Session limits and throughput licence on the firewall/CGNAT | Session creation rate and throughput during the busy hour, compared with the licence. | A licence limit presents as a regional, flat ceiling affecting every site behind that device. Raise the licence or bypass the device for the speed-test APN to prove it. |
| State created by asymmetric routing | Trace both directions. | Pin the return path, or the firewall drops the flow after setup and the UE shows a stall rather than a low rate. |
| Fragment handling | Whether the firewall reassembles, drops, or passes fragments. | Dropping fragments on the GTP path recreates the MTU black hole even though the routers are correct. Pass or reassemble; do not drop. |

### 3.4.4 Routing after an end-to-end swap

| Check | How | Action |
| --- | --- | --- |
| Summarisation and default routes | Did the new design aggregate prefixes so that X2 between two neighbouring sites now hairpins through the core? | For co-sited and neighbouring NSA pairs, prefer a local or regional X2 route. Hairpin doubles backhaul use and adds RTT. |
| MTU on the IGP/MPLS underlay | MPLS labels add 4 bytes each. A 1500-byte access MTU on top of two labels over a 1500-byte core **will** fragment. | Account for the label stack in the MTU plan. Set the underlay high enough that access 1600 plus labels still fits. |
| BFD and convergence | Flapping BFD during the swap period. | A path that reroutes every few minutes produces loss bursts and TCP collapse while average availability stays above target. Stabilise the IGP before judging throughput. |

---

## 3.5 Others — the causes that survive after transport is cleared

These are included because a transport-only plan will stall if the real cause is here, and because
several of them were introduced by the same swap.

### 3.5.1 Radio reality check (do this in parallel with 3.1, not after)

Transport can only deliver what the air interface schedules. Before a site is called a transport
case, record during the same test:

| Observation | Transport case | Radio case |
| --- | --- | --- |
| DL MCS and rank | High MCS, rank 3–4, throughput still low | MCS and rank low; throughput tracks RSRP |
| PRB allocation | UE is given most of the PRBs and still slow | UE is given few PRBs (load, or a scheduler/licence cap) |
| BLER / residual BLER | Nominal | High BLER with good RSRP: interference, TDD pattern clash, SSB/beam problem |
| UL specifically | UL PRBs full, MCS high, throughput flat at a round number → AMBR or grant throttling from transport feedback | UL PRBs full, MCS low → coverage, power, or interference |

Also confirm the **baseline and the new test used the same UE category**. A phone that supports 2 layers
and 64QAM cannot reach the 4-layer 256QAM number in Ch.2, on either vendor. State the UE model in
every test record.

Massive MIMO (32T) throughput depends on SRS and CSI. If the swap changed SRS periodicity, CSI-RS
configuration, or the maximum number of layers signalled to the UE, the air interface will schedule
fewer layers and the throughput drop is real and **not** a transmission issue. That check belongs to
the RAN team and should be reported alongside the transport tests so the two are not argued in
sequence for weeks.

### 3.5.2 The test itself

| Check | Why it creates false degradation | Action |
| --- | --- | --- |
| Server location changed | A speed-test server that moved from on-net to across a peering point adds RTT and a new bottleneck | Pin the reference server. Host one inside your own N6. |
| Single vs multi stream | Baselines taken with multi-stream apps, compared with a single-stream test | Standardise on both: 1 stream and 8 streams, same server, same duration. |
| UE radio conditions | An indoor test compared with a rooftop baseline | Fix RSRP/SINR windows for acceptance (for example RSRP better than −80 dBm, SINR better than 20 dB) and discard samples outside them. |
| Time of day and cell load | Busy-hour fairness vs an empty-cell baseline | Report empty-cell peak and busy-hour average as separate numbers. |
| Handset software | New phones schedule differently | Lock the reference handset model and firmware. |

### 3.5.3 Parameter migration from Ericsson to Huawei

A swap imports thousands of parameters through a mapping tool. The ones that cap throughput:

| Parameter area | What to diff against the Ericsson dump | Failure signature |
| --- | --- | --- |
| EN-DC AMBR split / SgNB AMBR ratios | MeNB parameters that compute the value in 3.1.7 | Flat per-user cap |
| PDCP SN length, discard timer, reordering timer | 12-bit left in place; discard timer shorter than the new X2 RTT | Throughput collapses only when both legs are active |
| Preamble / power / CSI / SRS | Layer and MCS capability | Low rank on a 32T cell |
| QCI/5QI to DSCP table | DSCP values the transport no longer queues correctly | Loss confined to one traffic class |
| Admission control and congestion thresholds | Thresholds copied from a 2T FDD cell | Users throttled while the port is idle |
| Cell bandwidth, TDD pattern, SSB power | A 100 MHz cell brought up at 60 or 80 MHz; pattern mismatch | Ceiling far below Ch.2 with perfect transport |
| Neighbour and X2 relations | Missing X2 so EN-DC never establishes, or establishes over a remote path | 5G icon with LTE-like throughput |

Produce the diff as a table: Ericsson value, Huawei value, intended value, match (yes/no). Work the
"no" rows that touch the list above before any hardware upgrade.

### 3.5.4 Software defects and known interop boundaries

Treat these as a checklist to raise with Huawei and, where the anchor is involved, to verify in your
own parameter set:

* AMBR encoding around 1 Gbit/s (see 3.3.1).
* Flow-control behaviour when X2 RTT exceeds the value the build was tested at.
* 256QAM or 4-layer MIMO silently disabled by a feature flag after a software upgrade.
* IPsec anti-replay drops when packets reorder across ECMP (a reason to keep one bearer on one path, and to enable TEID hashing rather than per-packet balancing).

Ask the vendor for the defect list for your exact release against "EN-DC throughput", "X2 flow control",
"transport MTU", and "AMBR", and close each open item with a version or a workaround.

### 3.5.5 New sites versus swapped sites

New Huawei 5G sites have no Ericsson baseline. Mixing them into the trend makes a real regression
look smaller, or a healthy expansion look like a failure.

| Population | Compare against | Extra check |
| --- | --- | --- |
| Swapped sites | Their own Ericsson baseline, after Step 0 in Ch.2 | Parameter diff (3.5.3) and port reuse (old GE tail kept) |
| New sites | The Ch.2 theoretical ceiling and the best swapped site | Commissioning defaults: path bandwidth, MTU, licence, sync |

---

## 3.6 What each team brings to the table

| Team | Brings | Leaves with |
| --- | --- | --- |
| RAN / Huawei | Port speed, eCPRI rate, IP-path and resource-group bandwidth, DSCP map, X2 option, SgNB AMBR trace, `N.NsaDc.SgNB.AbnormRel.Trans`, PDCP retransmission, licence, sync state, parameter diff | A list of RAN-side caps actually found, each with the counter |
| Transmission | Per-hop CIR/PIR/CBS, per-class drop counters at ≤ 60 s, microwave guaranteed rate, PTP time-error, Y.1564/TWAMP per segment | A per-site hop table; every hop either meets the Ch.2 number or has an upgrade action |
| Core | HSS/UDM AMBR, S1/X2/NAS trace of the three AMBR values, S-GW/UPF p99 and licence, service-chain RTT | AMBR aligned, or an explicit product decision to keep a cap |
| IP | MTU map, ECMP/LAG hash including TEID, firewall/CGNAT licence, route symmetry, underlay MTU vs label stack | Hash and MTU corrected; one-flow ceiling documented |
| Performance | The Step 0 formula comparison and the split between swapped and new sites | A baseline both sides accept |

---

## 3.7 Ranked hypotheses

Ordered by how likely each is **given this swap** (NR radio stayed 32T, LTE capacity went up, transport was rebuilt end to end) and by how cheap it is to confirm. Work down the list. Confirm rank 2 before spending field time on rank 12.

| Rank | Hypothesis | Where | Confirm in |
| --- | --- | --- | --- |
| 1 | The KPI definition changed with the vendor, so part of the "drop" is not physical | Method | Ch.2 §2.1 |
| 2 | A shaper inside the gNB (IP path or resource group) is below the port's real capacity, and the node reports that as "transmission" | RAN | §3.1.3 |
| 3 | MTU / fragmentation / PMTUD black hole on the new end-to-end path | IP | §3.1.4, §3.4.1 |
| 4 | Backhaul port, SFP, or first-mile hop is below 10G. The vendor is right about capacity; the Tx team is right that nothing is faulty | RAN + Tx | §3.1.1, §3.2.1 |
| 5 | `SgNB UE Aggregate Maximum Bit Rate`, UE-AMBR, or APN-AMBR is a round cap | RAN + Core | §3.1.7, §3.3.1 |
| 6 | DSCP was re-marked in the swap, so user plane sits in a small queue and drops on microbursts | RAN + Tx | §3.1.5, §3.2.3 |
| 7 | An LTE-era CIR/policer survived on the new service | Tx | §3.2.2 |
| 8 | The swap added RTT (new UPF, hairpinned X2, IPsec gateway), which cuts EN-DC flow control and single-stream TCP with zero loss | IP + Core | §3.2.4, §3.3.3 |
| 9 | A licence cap: RAN throughput, IPsec engine, microwave, or firewall | RAN + IP | §3.1.8, §3.4.3 |
| 10 | Fronthaul on a 32T AAU trained at 10G instead of 25G | RAN | §3.1.2 |
| 11 | LAG/ECMP hash pins each GTP-U tunnel to one member | IP | §3.4.2 |
| 12 | The ring or aggregation is oversubscribed now that LTE FDD is 4T and LTE TDD is 32T | Tx | §3.2.1 |
| 13 | PTP or a mismatched TDD pattern creates cross-link interference | Tx + RAN | §3.1.9, §3.2.5 |
| 14 | Radio defaults differ from the Ericsson baseline: layers, 256QAM, SRS/CSI, energy saving | RAN | §3.5.1, §3.5.3 |
| 15 | TCP optimiser removed, or CGNAT / peering / the test server changed | Core | §3.3.3, §3.5.2 |

Continue to [Chapter 4: the action plan](04-action-plan.md).
