# 3. Domain-by-Domain Checks and Action Points

Every check below has an ID so it can be tracked in a war-room tracker. Priority:
**P1** = do first, high probability or cheap; **P2** = do if P1 is clean; **P3** = completeness.

The "Huawei hooks" columns name counters and objects verified against Huawei 3900/5900-series
performance-counter references. **Confirm exact names and MML syntax against your own software
release** — they move between versions.

A deliberately useful property of the Huawei base station: it has **built-in active transport
measurement**. You do not need to wait for the transmission team to instrument anything.

| Function | Measurement set | What it gives you |
| --- | --- | --- |
| **TWAMP** (RFC 5357) | `Transport.BSTWAMP` — e.g. `VS.BSTWAMP.Forward.DropMeans`, `VS.BSTWAMP.Backward.DropMeans`, `VS.BSTWAMP.Forward.Peak.DropRates` | Two-way **delay, jitter and loss** per direction on a real transport path |
| **Ethernet Delay Measurement** (Y.1731 DMM) | `DataLink.ETHDM` — `VS.ETHDM.MaxRttDelay`, `VS.ETHDM.MaxRttJitter`, `VS.ETHDM.RttJitterStandardDeviation` | Per-link delay and jitter, incl. peaks |
| **Ethernet Loss Measurement** (Y.1731 LMM) | `DataLink.ETHLM` — `VS.ETHLM.Forward.DropRate`, `VS.ETHLM.Backward.Drop*`, `VS.ETHLM.Forward.Peak*` | Directional frame loss with peaks |
| **IP PM** | `VS.IPPM.Forword.DropMeans`, `VS.IPPM.Forword.Peak.DropRates` | IP-layer loss on the path |
| **eCPRI port** | `Measurement of eCPRI Port Performance (ECPRIPORT)` | Fronthaul port health |

**Action A0 (P1, do today):** enable TWAMP and Y.1731 DM/LM from the gNodeB towards the S-GW/UPF
address **and** towards the eNB's X2-U address, on the **same DSCP** as user traffic, on 10 degraded
and 3 good sites. This single step converts "we think it is transmission" into measured delay, jitter
and loss per direction — and it settles mechanisms #3 and #4 from §2.3 within a day.

---

## 3.1 RAN-side transport analysis

The RAN node's own transport configuration. This is where post-swap regressions concentrate, because
it is configuration that was **re-created from scratch** rather than migrated.

### 3.1.1 Physical port and capacity

| ID | Check | Why it matters | How | Huawei hooks | P |
| --- | --- | --- | --- | --- | --- |
| R1 | **Backhaul port type and negotiated rate** on every 5G site | RJ45 electrical = **GE only**; a 1G negotiation caps user goodput at **~945 Mbit/s shared with LTE**, below a single NR cell's 1.7 Gbit/s capability | Read port status; do not trust design docs | `DSP ETHPORT`, `LST ETHPORT`; `VS.FEGE.TxMaxSpeed` / `RxMaxSpeed` / `TxTotalBW` | **P1** |
| R2 | Main control board type vs required capacity | UMPTe/UMPTga: 2×FE/GE electrical + 2×FE/GE/**10GE** optical, ~10 Gbit/s class. UMPTg: **25GE**. A 10G-class board is ~94 % loaded at all-cells-full-buffer (§2.2) | Board inventory vs `tx_budget.py` output | Board inventory | P1 |
| R3 | **Optical module rate** actually fitted | A GE or 2.5GE SFP in a 10GE-capable cage silently caps the site. Huawei's design default for NR backhaul is a **10GE** single-mode module | Read SFP inventory per site | SFP/optical module query | **P1** |
| R4 | Port errors, CRC, discards, **pause frames** | CRC/errors indicate bad optics/fibre; **received pause frames mean the far-end switch is throttling the gNB** — a classic hidden throttle | Port statistics | `VS.FEGE.RxErrPackets`; pause-frame counters in `DSP ETHPORT` | P1 |
| R5 | Autonegotiation / duplex | A half-duplex or mis-negotiated link collapses throughput while showing "up" | Port status | `DSP ETHPORT` | P2 |
| R6 | **Fronthaul: eCPRI negotiated at 25 Gbit/s per 32T AAU** | 32T/64T at 100 MHz is specified around 1×25 Gbit/s eCPRI. At 10G the baseband restricts bandwidth/layers — looks exactly like "throughput below baseline" and **no backhaul test will find it** | eCPRI port rate + error stats per AAU | `ECPRIPORT` measurement set | **P1** |
| R7 | LAG/trunk on the backhaul: member count, member speeds, hash | A single GTP-U tunnel hashes to **one member**, so a 2×1GE LAG still gives one user only ~945 Mbit/s (see N5) | LAG config both ends | Eth trunk config | P1 |

### 3.1.2 Transport resource model, shaping and admission

This is the most commonly mis-migrated area, and it produces exactly the symptom you describe:
throughput capped below baseline with no alarms.

| ID | Check | Why it matters | How | Huawei hooks | P |
| --- | --- | --- | --- | --- | --- |
| R8 | **Configured transport bandwidth vs physical port speed** | Huawei RAN admits and shapes traffic against a *configured* bandwidth (IP path / logical port / transmission resource group). If it was provisioned at the legacy Ericsson-era value (e.g. 1000 Mbit/s or 2 Gbit/s) on a new 10GE port, the **node throttles itself** and reports "transmission congestion". The Tx team will find nothing, because the limit is inside the gNB. | Compare the configured bandwidth of the IP path / logical port / resource group against the real port speed and against `tx_budget.py` | `LST IPPATH` (note `CARRYFLAG`: `NULL` = physical port, `IPLGCPORT` = IP logical port, `RSCGRP` = transmission resource group), logical-port and resource-group bandwidth settings | **P1 — top suspect** |
| R9 | **Resource-group / IP-path drops and congestion time** | Direct proof of self-throttling. Non-zero here with an idle physical port means the bottleneck is the configured model, not the network | Pull counters for the same hour as a failing speed test | `VS.RscGroup.TxDropBytes`, `VS.RscGroup.TxDropPkts`, `VS.IPRscGroup.TxDropPkts`, `VS.IPPath.TxDropPkts`, `VS.IPPath.RxDropPkts`, `VS.IPPath.TxMaxSpeed`; resource-group congestion-duration and flow-control available-bandwidth counters | **P1** |
| R10 | IP-layer and GTP-U drops at the node | Separates "transport dropped it" from "the node dropped it" | Counters | `VS.IP.TxDropPkts`, `VS.IP.RxDropPkts`, `VS.IPv6.*DropPkts`, `VS.Gtpu.RxDropPkts`, `VS.Gtpu.RxDropBytes` | P1 |
| R11 | Adaptive/transport flow control enabled and its measured available bandwidth | The node may be *dynamically* reducing available bandwidth based on measured delay/loss. If it has latched low, throughput stays low after the original transport fault cleared | Flow-control available-bandwidth counters (max/min/avg, increase-times based on delay and on packet loss) | Resource-group flow-control measurement set | **P1** |
| R12 | IPsec on the node: enabled? SA count? ESP failures? | IPsec costs ~5 points of overhead, shrinks MTU, and can be CPU-bound on the board | Config + counters | `VS.IPSec.RxESPFailDropPkts` | P2 |
| R13 | Board/CPU load on the main control and baseband boards during peak | A board-bound node throttles regardless of transport | Board performance measurement | `NRBoard` measurement set, CPU load counters | P2 |

### 3.1.3 EN-DC / NSA specifics — the highest-yield non-obvious checks

| ID | Check | Why it matters | How | Huawei hooks | P |
| --- | --- | --- | --- | --- | --- |
| R14 | **`SgNB UE Aggregate Maximum Bit Rate` in `SGNB ADDITION REQUEST`** | The **MeNB** chooses how much of the UE-AMBR the 5G node may schedule. A conservative or badly migrated value **caps NR throughput invisibly** — it appears in no transport KPI and no NR counter. After an eNB vendor swap this is a prime suspect | Decode a real X2-AP `SGNB ADDITION REQUEST` on a failing site; compare with a good site | X2-AP trace / signalling trace | **P1 — top suspect** |
| R15 | Bearer option in use: 3, 3a or **3x** | In Option 3 the **whole NR share crosses X2-U** and the eNB must buffer at combined peak. If the swap changed the option (or it differs per region), transport load changes radically | Configuration + X2-U volume counters vs NR air volume | `N.PDCP.Vol.DL.X2U.TrfPDU.Tx`, `N.PDCP.Vol.UL.X2U.TrfPDU.Rx` | **P1** |
| R16 | **X2-U volume vs NR volume ratio** | Cross-check R15 empirically and size the X2 path. If X2-U DL volume ≈ NR DL volume you are effectively in Option 3 | Ratio of counters over the same period | `N.PDCP.Vol.DL.X2U.TrfPDU.Tx` ÷ NR DL PDCP volume | P1 |
| R17 | **X2-U retransmission requests** | Direct evidence of loss or excessive delay on the split path — the cleanest single proof that X2 transport is hurting throughput | Counter trend vs throughput | `N.PDCP.DL.X2U.ReqRetransPackets`, `N.PDCP.DL.X2U.TrfPDU.TxPackets`, `N.PDCP.UL.X2U.TrfPDU.RxPackets` | **P1** |
| R18 | **Transport-caused SgNB abnormal releases** | A counter that explicitly attributes EN-DC failures to transport. Non-zero = the vendor's claim has teeth; zero = it does not | Counter trend | `N.NsaDc.SgNB.AbnormRel.Trans` (vs `N.NsaDc.SgNB.AbnormRel.Radio`) | **P1** |
| R19 | SgNB addition success rate and PSCell change success | Low EN-DC attach/retention means users spend time on LTE only, which **looks like** low 5G throughput | Counters | `N.NsaDc.SgNB.Add.Att` / `.Succ`, `N.NsaDc.IntraSgNB.PSCell.Change.Att/Succ`, `N.NsaDc.InterSgNB.PSCell.Change.Att/Succ` | P1 |
| R20 | **`pdcp-SN-SizeDL` = 18 bits** for high-rate split bearers | With 12-bit SN the PDCP reordering window can itself limit a fast split bearer whose two legs have different delay | RRC reconfiguration message / PDCP config | UE RRC trace | P2 |
| R21 | PDCP reordering / discard timers vs measured X2 delay | Timers tuned for a low-latency X2 will discard on a higher-latency path, silently wasting capacity | Compare configured timer vs measured p99 X2 RTT (from A0) | PDCP config + TWAMP result | P2 |
| R22 | X2-C SCTP health (retransmissions, congestion) | SCTP loss delays or fails SgNB addition, so the user never gets the 5G leg | SCTP link counters | SCTP retransmission/congestion counters, `DSP SCTPLNK` | P2 |
| R23 | **X2 path routing: does it hairpin?** | If eNB↔gNB traffic is routed up to an aggregation or core site instead of switching locally, X2 RTT can go from <1 ms to 10 ms+, crushing flow control | `traceroute` between node IPs; compare with intended design | Node-to-node trace | **P1** |
| R24 | Are eNB and gNB co-sited but transported separately? | Co-sited nodes sometimes end up with X2 across the whole metro because of VRF/VLAN design | Topology review | Design vs actual | P2 |

### 3.1.4 Radio-side sanity checks (rule out, do not skip)

You said NR stayed 32T → 32T, so the radio is the *least* likely cause. Confirm cheaply, then move on.

| ID | Check | Why | P |
| --- | --- | --- | --- |
| R25 | **TDD slot pattern identical to the Ericsson baseline** (e.g. DDDSU vs DDDDDDDSUU) | Directly rescales the DL/UL ceiling: 74.3 % vs 77.1 % DL, and UL 22.9 % vs 21.4 %. A pattern change alters the *target*, not the performance | **P1** |
| R26 | Max MIMO layers, max modulation (256QAM DL / UL), and that 4-layer SU-MIMO is actually being scheduled | 4L→2L halves DL. Check the rank distribution, not just the config | **P1** |
| R27 | **Licences / capacity keys**: throughput, MIMO-layer, 256QAM, CA, MU-MIMO features | A missing or expired capacity licence is a silent hard cap and is very common right after a swap | **P1** |
| R28 | Output power per branch and total EIRP vs Ericsson baseline | 32T at lower per-branch power changes coverage and achievable MCS | P2 |
| R29 | Beamforming / SSB beam config, CSI-RS and codebook settings | Wrong codebook or restricted rank limits layers | P2 |
| R30 | PRB utilisation and active users during the failing test | If the cell is loaded, low per-user throughput is correct behaviour, not a fault | **P1** |
| R31 | Cross-link interference / external interference on 2.6 GHz TDD, and neighbour-network sync | TDD UL is very sensitive; new 32T sites plus new neighbours change the interference floor. Check UL noise/interference levels vs baseline | P1 |
| R32 | UL-specific: UL MIMO layers, UL 256QAM, SUL config, UL power control | Your UL degraded too; UL has its own independent set of caps | **P1** |

---

## 3.2 Transmission (Tx) side analysis

The transmission team's domain: first mile, microwave, optical, and the packet transport network.
Their "no issue" statement is almost certainly true *for what they measured*. The checks below target
what usually is **not** measured.

| ID | Check | Why it matters | How | P |
| --- | --- | --- | --- | --- |
| T1 | **First-mile media and its true capacity**: fibre, microwave, GPON, leased line | A 1G microwave hop or a GPON ONT behind a 10GE port is the real ceiling. This is the most frequent physical bottleneck after a swap | Per-site first-mile inventory with capacity | **P1** |
| T2 | **Microwave: adaptive modulation state, licensed capacity, ACM downshifts, XPIC state** | Microwave capacity is weather- and modulation-dependent. A link licensed at 1 Gbit/s that drops to 400 Mbit/s in rain "has no alarms" but has lost 60 % of capacity. Also check **capacity licences**, which are often under-purchased | Radio-link statistics: ACM profile histogram, capacity vs time, G.826 errors | **P1** |
| T3 | **p99 interface utilisation at ≤60 s granularity on every hop** carrying S1-U/X2-U/N3 | 15-minute averages hide microbursts completely (§2.3 Rule 1). This is the crux of the vendor/Tx disagreement | Re-poll at 1-minute (or stream telemetry) and report p95/p99 | **P1** |
| T4 | **Per-queue output drops / tail drops / WRED drops on every hop** | **Output drops with low average utilisation is the definitive microburst signature.** It proves capacity insufficiency that averages deny | Per-class queue statistics on CSG/ASG/RSG | **P1** |
| T5 | Buffer sizing and shaping on the cell-site gateway egress | Too-small buffers drop NR microbursts; too-large buffers add latency (bufferbloat) and hurt TCP. NR bursts are far larger than LTE bursts | Queue depth/latency config review | P1 |
| T6 | **Ring/aggregation segment dimensioning vs sum of attached sites** | Each site may be fine while the ring segment is oversubscribed. Post-swap capacity per site rose (FDD 2T→4T, TDD 4T→32T, plus NR) — the ring was probably dimensioned for the old numbers | Sum `tx_budget.py` busy-hour per site vs segment capacity | **P1** |
| T7 | **Shaper/policer/CIR-EIR on the access EVC or service instance** | A 1 Gbit/s CIR on a 10GE port is invisible to a link-utilisation report and is an exact match for "capped below baseline". Check both ends and any intermediate service policy | Service/EVC policy review + policer drop counters | **P1** |
| T8 | Was the **transport service re-created or migrated** during the swap? | New Huawei transport means new service definitions. CIR/EIR values, MTU and QoS maps are frequently re-entered with legacy or default values | Config diff: old vs new service parameters | **P1** |
| T9 | **Sync: PTP (G.8275.1) / GNSS status, holdover events, phase error** | TDD requires phase sync (±1.5 µs at the air interface, ~1100 ns network budget). Degraded sync → interference → MCS collapse → low throughput. Often appears as "RAN problem" | PTP servo state, phase error trend, GNSS lock, holdover alarms | **P1** |
| T10 | Optical layer: power levels, OSNR, FEC error counts, protection switching events | Marginal optics cause intermittent errors that averaged reports smooth away | DWDM/OTN performance data | P2 |
| T11 | Any remaining **legacy/non-Huawei segment** in the path | You state the path is end-to-end Huawei; verify, because a surviving legacy hop is where MTU and QoS assumptions break | Hop-by-hop path audit | P2 |
| T12 | Protection/restoration path capacity | If a link is running on its protection path, capacity may be a fraction of nominal — with no alarm | Check active vs protect path per site | P2 |
| T13 | **Service activation test evidence (Y.1564 / RFC 2544)** for each new 5G service | If the service was never activation-tested at 10G with the right frame sizes and MTU, nobody has ever proven it can carry the load | Test reports per site | **P1** |

---

## 3.3 Core-side analysis

The core rarely causes a *uniform* degradation, but it causes **hard ceilings** — and hard ceilings look
exactly like "cannot reach baseline".

| ID | Check | Why it matters | How | P |
| --- | --- | --- | --- | --- |
| C1 | **UE-AMBR / APN-AMBR (NSA) or UE-AMBR / Session-AMBR (SA)** for the test subscriptions | These are absolute caps. Per TS 23.501 §5.7.1.8, the (R)AN enforces UE-AMBR in UL and DL, and the UPF/PGW enforces Session/APN-AMBR. A 1 Gbit/s profile means you will never see more than ~1 Gbit/s regardless of radio or transport | Read HSS/UDM subscription; decode `Initial Context Setup Request` (UE-AMBR) and `Attach Accept` (APN-AMBR) | **P1** |
| C2 | **AMBR value encoding at boundaries** | Known field: some implementations misbehave exactly at the 1024 Mbit/s boundary while 1023 Mbit/s works. If your profile is "1 Gbps", test 1023 and 2000 to rule out an encoding/overflow edge | Lab or single-subscriber test with modified profile | **P1** |
| C3 | Did the swap change the **S-GW/PGW or UPF** serving these sites? | A different anchor changes RTT, MTU, policing and peering. A +10 ms RTT change alone can halve single-stream TCP throughput with zero loss | Compare serving node and RTT before/after | **P1** |
| C4 | **UPF/PGW user-plane capacity and per-session/per-core limits** | A "fat" GTP-U tunnel can be pinned to one core/PIC, capping a single session well below the platform's aggregate rating. TEID-aware distribution exists specifically to fix this | Platform per-session throughput data; check TEID-based session distribution | P1 |
| C5 | DCNR / `restrictDCNR` and the `NR Restriction in EPS as Secondary RAT` bit in the S1AP Handover Restriction List | If subscription or MME policy restricts NR, the UE never gets the 5G leg. Decode both: if `DCNR`=0 in Attach Request the device/policy is at fault; if `DCNR`=1 and `restrictDCNR`=1 in Attach Accept, subscription/MME policy is | **P1** |
| C6 | **Per-E-RAB admitted vs requested list** in `SGNB ADDITION REQUEST ACKNOWLEDGE` | A partial admission is a success message that silently carries less traffic than requested. Diff requested vs admitted on every addition | P1 |
| C7 | 5QI/QCI mapping and whether the test traffic lands in the expected class | Wrong class → wrong queue → wrong treatment across the whole transport network | **P1** |
| C8 | PCRF/PCF policy: rate limits, fair-use throttling, plan-based shaping | A policy-based throttle applied to the test SIM is a classic false alarm | **P1** |
| C9 | Charging/quota (OCS) interactions | Quota exhaustion can silently downgrade a plan mid-test | P3 |
| C10 | **MTU signalled to the UE / PDU-session MTU** | TS 23.501 Annex J: a 1358-byte link MTU avoids fragmentation in most deployments on a 1500-byte transport. If the core signals 1500 while the path supports less, you get the fragmentation cliff | **P1** |
| C11 | TCP optimiser / proxy / video-pacing middlebox on SGi/N6 | Optimisers routinely cap or pace throughput and are often re-tuned or newly inserted during a modernisation | **P1** |
| C12 | CGNAT capacity and per-subscriber session limits | Exhaustion produces packet loss and stalls that look like transport | P2 |
| C13 | Firewall / security gateway throughput and per-flow limits | A security GW that terminates IPsec is frequently the hidden per-flow bottleneck | P1 |

---

## 3.4 IP network analysis

The IP/packet layer between RAN and core. Four of the highest-probability root causes for your exact
symptom live here.

| ID | Check | Why it matters | How | P |
| --- | --- | --- | --- | --- |
| N1 | **End-to-end MTU, hop by hop** | The single most common "no transport issue but throughput is broken" cause. With GTP-U + UDP + IP + VLAN + IPsec the overhead reaches **142 bytes** (TS 23.501 Annex J) — a 1500-byte transport MTU leaves only **1358** for user data. Target **transport MTU ≥ 1600** end to end | DF-bit ping sweep at 1400/1472/1500/1600 B between node IPs; check configured MTU on every interface **and every tunnel** | **P1 — top suspect** |
| N2 | **Fragmentation counters and PMTUD reachability** | If ICMP "fragmentation needed" / "packet too big" is filtered anywhere, you get a **PMTUD black hole**: connections establish, transfer a little, then stall. Every interface counter stays green | Fragment/reassembly counters per hop; verify ICMP type 3 code 4 and ICMPv6 type 2 are permitted | **P1** |
| N3 | **TCP MSS clamping** value on the relevant path | Clamping is a mitigation, not a fix, but a missing or wrong clamp with broken PMTUD is fatal. MSS = effective MTU − 40 (IPv4) or − 60 (IPv6) | Capture a TCP SYN/SYN-ACK on SGi and read the MSS option | **P1** |
| N4 | **DSCP marking preserved end to end**, and the QoS map on every hop | If S1-U/N3/X2-U traffic is remarked to best-effort at one hop (very common after re-provisioning), it lands in a small queue and drops under burst. Looks like capacity, is actually classification | Capture at both ends and compare DSCP; audit the ingress/egress QoS policy per hop, including the **trust boundary** | **P1** |
| N5 | **LAG / ECMP hashing of GTP-U** | GTP-U uses UDP 2152 for **both** source and destination ports, so a 5-tuple hash pins **all** traffic between a node pair to **one member link** — polarisation. A 4×10GE LAG then gives one user 10G, and an N×1GE LAG gives one user 1G. Fix: **TEID-aware hashing** (Cisco `ip cef load-sharing algorithm include-ports … gtp`, Junos `enhanced-hash-key gtp-tunnel-endpoint-identifer`, Cumulus `hash_config.gtp_teid = true`), or IPv6 flow-label entropy per RFC 6438 | Audit hash configuration on every LAG/ECMP hop; verify with the platform's "exact-route" command | **P1** |
| N6 | **Routing symmetry and path length**, before vs after | Asymmetric or hairpinned paths inflate RTT and break stateful middleboxes. Check the X2 path especially (R23) | `traceroute` both directions between node, S-GW/UPF and internet | **P1** |
| N7 | RTT to a fixed reference, before vs after the swap | A single TCP stream is capped at `window/RTT`. +10 ms can halve a speed test with zero loss. **If nobody recorded RTT before the swap, start recording now and compare swapped vs new-site vs legacy clusters** | TWAMP/ping to an unchanged reference host | **P1** |
| N8 | **Policers / rate limits on any interface, VRF, or service policy** | A leftover or default policer is a perfect match for "capped below baseline with no congestion". Search the whole path, including the core-facing side | Config audit for `policer`/`shaper`/`CIR`/`rate-limit` + policer drop counters | **P1** |
| N9 | IPsec: overhead, MTU impact, engine throughput, anti-replay window | IPsec adds ~57–73 B, shrinks MTU, and the crypto engine may be the real per-flow ceiling. A too-small anti-replay window with reordering causes silent drops | SA config, crypto engine load, ESP error counters | P1 |
| N10 | QinQ / extra VLAN tags added during re-provisioning | Each tag costs 4 B of MTU and can break an MTU assumption | Interface config | P2 |
| N11 | Control-plane policing (CoPP) hitting data-plane traffic | Misclassified user traffic punted to CPU is rate-limited hard | CoPP counters | P3 |
| N12 | Load-balancer / firewall session limits on the N6/SGi path | Per-session or per-flow limits cap single-stream tests | Platform statistics | P2 |
| N13 | Packet rate (pps) limits, not just bit rate | With small packets a policer or IPsec engine hits a **pps** ceiling long before the bit-rate ceiling. Run `tx_budget.py --payload 256` to see the expansion | Platform pps ratings vs measured pps | P2 |

---

## 3.5 Others — the categories most often missed

| ID | Check | Why it matters | P |
| --- | --- | --- | --- |
| O1 | **Test methodology itself**: UE model/category, firmware, server, time of day, location, single vs multi-stream, cell load | A baseline measured with a flagship UE on an unloaded cell against a nearby server, compared against a mid-tier UE on a loaded cell against a distant server, "proves" a regression that does not exist. **Fix the methodology before trusting any number** | **P1** |
| O2 | **UE capability**: supported layers, 256QAM, CA combinations, EN-DC band combination, UE category cap | Some UE categories cap aggregate throughput regardless of network capability. Confirm the reported UE capability matches the baseline UE | **P1** |
| O3 | **Speed-test server capacity and placement** | A server that moved, or is now reached via a different peering point, changes results with no network fault. Test against an **on-net** server as the referee | **P1** |
| O4 | **Licences and capacity keys across every node**: gNB throughput/feature licences, microwave capacity licences, router/UPF capacity licences | Post-swap licence gaps are extremely common and produce exact hard ceilings | **P1** |
| O5 | **New sites vs swapped sites separated in all reporting** | New sites have no baseline and often different (unoptimised) neighbour relations and parameters. Mixing them corrupts every trend | **P1** |
| O6 | **Parameter audit: Huawei defaults vs the intended design** | After a swap, thousands of parameters take Huawei defaults. Produce a full diff of the golden template vs live config, for both eNB and gNB | **P1** |
| O7 | Software version consistency and known issues | Mixed releases across eNB/gNB/routers/UPF, plus release-specific defects, are a real cause. Ask the vendor for the release-note list of throughput-affecting fixes | P1 |
| O8 | **Sync quality over time**, not just current status | An intermittent GNSS/PTP problem causes intermittent interference and intermittent throughput loss, which averages into "general degradation" | P1 |
| O9 | Neighbour relations / ANR completeness, and mobility settings | Poor mobility keeps UEs on weak cells or drops the 5G leg early, reducing measured 5G throughput | P1 |
| O10 | Antenna installation quality: azimuth, tilt, VSWR, cross-connected feeders/branches on new 32T AAUs | A swapped or mis-installed branch reduces achievable rank — throughput falls with no alarm | P1 |
| O11 | OSS/counter collection integrity: missing granularity periods, partially reporting cells, timezone offsets | Missing samples skew averages | P2 |
| O12 | **Customer-perceived vs KPI-perceived**: are complaints correlated with the KPI drop?| If KPIs dropped but complaints did not, suspect measurement (Step 0). If complaints rose but KPIs did not, suspect latency/consistency rather than peak rate | P1 |
| O13 | Energy-saving / power-saving features (symbol/channel shutdown, deep sleep) | Aggressive energy-saving defaults reduce available capacity at low load — and low load is exactly when you run a drive test | **P1** |
| O14 | MU-MIMO / SU-MIMO scheduler settings on 32T | Default MU-MIMO behaviour can reduce **single-user** peak in exchange for cell capacity. Your KPI is single-user, so this matters | **P1** |

---

## 3.6 Ranked hypothesis list

Ordered by probability × ease of verification, given that NR radio config is unchanged (32T → 32T) and
transport is newly Huawei end to end.

| Rank | Hypothesis | Domain | Check IDs | Cost to verify |
| --- | --- | --- | --- | --- |
| 1 | **KPI definition / baseline comparison is not apples-to-apples** | Method | §2.1, O1, O5 | Hours |
| 2 | **Configured transport bandwidth / resource-group limit inside the gNB is below the port's real capacity** (node self-throttles and reports "transmission") | RAN Tx | R8, R9, R11 | Hours |
| 3 | **MTU / fragmentation / PMTUD black hole** on the new end-to-end Huawei path | IP | N1, N2, N3, C10 | Hours |
| 4 | **Backhaul port, optical module, or first-mile hop below 10G** (genuine capacity gap — vendor right, Tx team also right) | RAN Tx + Tx | R1, R2, R3, T1, T2 | Hours |
| 5 | **`SgNB UE Aggregate Maximum Bit Rate` or UE-AMBR/APN-AMBR cap** | RAN + Core | R14, C1, C2 | Hours |
| 6 | **DSCP remarking / wrong queue → microburst drops** | IP + Tx | N4, T4, T5 | 1–2 days |
| 7 | **Leftover policer / shaper / CIR on the service** | IP + Tx | N8, T7, T8 | Hours |
| 8 | **Added latency** (new UPF/S-GW anchor, hairpinned X2, longer path) degrading EN-DC flow control and single-stream TCP | IP + Core | N6, N7, C3, R23 | 1–2 days |
| 9 | **Licence / capacity key gap** (gNB, microwave, router) | Others | O4, R27, T2 | Hours |
| 10 | **Fronthaul negotiated at 10G instead of 25G on 32T AAUs** | RAN Tx | R6 | Hours |
| 11 | **LAG/ECMP polarisation** pinning a tunnel to one member | IP | N5, R7 | Hours |
| 12 | **Ring/aggregation oversubscription** after the large LTE capacity increase | Tx | T6, T3, T4 | Days |
| 13 | **Sync degradation → TDD interference** | Tx | T9, O8 | Hours |
| 14 | Radio-side: layers/modulation/pattern/energy-saving/MU-MIMO defaults differ from baseline | RAN | R25–R32, O13, O14 | 1–2 days |
| 15 | TCP optimiser, CGNAT, security GW, or test-server change on N6/SGi | Core + Others | C11, C12, C13, O3 | Days |

Continue to [Chapter 4: Action plan](04-action-plan.md).
