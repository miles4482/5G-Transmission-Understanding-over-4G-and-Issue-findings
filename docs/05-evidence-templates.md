# 5. Evidence Templates, Counters and Commands

Copy these into your tracker. The point of a template is to make an incomplete answer visibly
incomplete.

---

## 5.1 Per-site transport inventory (Action P1.1)

| Field | Example | Notes |
| --- | --- | --- |
| Site ID / gNB ID | ENB12345 / GNB12345 | |
| Category | swapped / new | **Never mix these in reporting** |
| NR cells × bandwidth × TDD pattern | 3 × 100 MHz, DDDSU | Drives the theoretical ceiling |
| NR antenna config | 32T32R | |
| LTE carriers on the same BBU | 3× FDD 20 MHz 4T, 3× TDD 20 MHz 32T | Shares the same backhaul |
| BBU type | BBU5900 | |
| Main control board | UMPTe / UMPTg / UMPTga | UMPTe ≈10 Gbit/s class; UMPTg = 25GE |
| **Backhaul port used** | XGE1 optical / FE-GE0 RJ45 | **RJ45 = GE only** |
| **Negotiated port speed** | 10000 / 1000 Mbit/s | Read from the node, not the design |
| Optical module rate | 10GE / 1GE / 2.5GE | A GE SFP in a 10GE cage caps the site |
| **Configured transport bandwidth in the node** | 10000 / 1000 Mbit/s | IP path / logical port / resource group. **Compare against the port speed** |
| MTU configured | 1600 / 1500 | Target ≥1600 |
| VLAN tags | 1 / 2 (QinQ) | 4 B of MTU each |
| IPsec | on / off | ~57–73 B overhead, shrinks MTU |
| First-mile media | fibre / microwave / GPON | |
| First-mile capacity | 10 Gbit/s / 1 Gbit/s licensed | The real ceiling if lower than the port |
| LAG members and speeds | 1×10GE / 2×1GE | With 5-tuple hashing, one tunnel uses one member |
| Fronthaul eCPRI rate per AAU | 25 / 10 Gbit/s | 32T at 100 MHz expects 25G |
| Serving S-GW/PGW or UPF | name | Note if it changed at swap |
| RTT to fixed reference | ms | Before vs after if available |
| **Required capacity (`tx_budget.py`)** | 5227 Mbit/s busy hour | Attach to any upgrade request |
| Verdict | OK / under-dimensioned / self-throttled | |

---

## 5.2 Throughput test record (Actions P0.4, P2.7, P2.8)

Every throughput claim in this investigation must arrive with all of these fields.

| Field | Value |
| --- | --- |
| Test ID / date / time (with timezone) | |
| Site / cell / sector | |
| Category (swapped / new / legacy reference) | |
| UE model, firmware, category, supported layers/modulation | |
| Location and RF conditions: RSRP, SINR, reported CQI, **reported rank** | |
| Cell load at test time: PRB utilisation, active users | |
| Mode: NR-only / EN-DC / LTE-only | |
| Streams: 1 / 8 / 16 | |
| Protocol: TCP / UDP | |
| Server: name, on-net or off-net, location, capacity | |
| **RTT (min/avg/p99) to that server** | |
| **Negotiated TCP MSS** | |
| DL throughput (Mbit/s) | |
| UL throughput (Mbit/s) | |
| Packet loss observed | |
| Theoretical ceiling from `tx_budget.py` | |
| Ratio achieved / theoretical | |
| Notes (retransmissions, stalls, ramp-up shape) | |

A healthy single-user result on a lightly loaded 100 MHz DDDSU 4-layer cell is roughly **70–80 % of the
1736 Mbit/s theoretical figure**, i.e. **~1.2–1.4 Gbit/s DL**. Publicly demonstrated commercial 32T32R
results at 100 MHz sit around **1.19 Gbit/s DL**, which is a reasonable sanity reference. If you are
seeing that band, the network is behaving; if you are seeing a suspiciously round figure near
**~900 Mbit/s**, suspect a **GE bottleneck** (a 1GE port yields ~945 Mbit/s of user goodput); near
**1 Gbit/s exactly**, suspect an **AMBR or policer cap**.

---

## 5.3 Four-mechanism sign-off sheet (Action P0.5)

One row per segment. An empty cell is an action, not an answer.

| Segment | 1. Capacity: p99 rate vs configured, ≤60 s | 2. Loss: per-queue drops, CRC, TWAMP | 3. Latency/jitter: measured RTT + jitter | 4. MTU: largest DF-bit size that passes | Verdict |
| --- | --- | --- | --- | --- | --- |
| Fronthaul (AAU↔BBU) | | | | n/a | |
| gNB port / configured bandwidth | | | | | |
| First mile (gNB↔CSG) | | | | | |
| Access ring segment | | | | | |
| Aggregation | | | | | |
| X2-U path (eNB↔gNB) | | | | | |
| S1-U / N3 to S-GW/UPF | | | | | |
| N6 / SGi to server | | | | | |

---

## 5.4 Huawei counter shortlist

Verified against Huawei 3900/5900-series performance-counter references. **Confirm exact names against
your own software release.**

### Transport — Ethernet port (`ETHPORT` / `Physical.FEGE`)

Use the **Max** variants. The Mean variants are what make an overloaded port look idle.

```
VS.FEGE.TxMaxSpeed        VS.FEGE.RxMaxSpeed
VS.FEGE.TxMeanSpeed       VS.FEGE.RxMeanSpeed
VS.FEGE.TxMinSpeed        VS.FEGE.RxMinSpeed
VS.FEGE.TxTotalBW         VS.FEGE.RxTotalBW        (available bandwidth on the port)
VS.FEGE.TxBytes           VS.FEGE.RxBytes
VS.FEGE.TxPackets         VS.FEGE.RxPackets
VS.FEGE.RxErrPackets
```

### Transport — IP path, resource group, IP and GTP-U drops

Non-zero drops here **with an idle physical port** means the node is throttling itself against a
configured bandwidth — the single highest-value finding in this investigation.

```
VS.IPPath.TxDropPkts      VS.IPPath.RxDropPkts
VS.IPPath.TxMaxSpeed      VS.IPPath.RxMaxSpeed
VS.IPPath.TxMeanSpeed     VS.IPPath.RxMeanSpeed
VS.RscGroup.TxDropPkts    VS.RscGroup.TxDropBytes
VS.IPRscGroup.TxDropPkts  VS.IPRscGroup.TxDropBytes
VS.IP.TxDropPkts          VS.IP.RxDropPkts
VS.IPv6.TxDropPkts        VS.IPv6.RxDropPkts
VS.Gtpu.RxDropPkts        VS.Gtpu.RxDropBytes
VS.IPSec.RxESPFailDropPkts
```

Also pull, from the resource-group **flow control** measurement set: congestion duration, and the
max/min/average DL and UL **available bandwidth**, plus the "available bandwidth increase times based
on delay" and "based on packet loss" counters. If available bandwidth has latched low, the node is
still throttling after the original transport fault cleared.

### Transport — active measurement (enable these; Action P2.1)

```
Transport.BSTWAMP :  VS.BSTWAMP.Forward.DropMeans,  VS.BSTWAMP.Backward.DropMeans,
                     VS.BSTWAMP.Forward.Peak.DropRates, VS.BSTWAMP.Backward.Peak.DropRates
DataLink.ETHDM    :  VS.ETHDM.MaxRttDelay, VS.ETHDM.MinRttDelay, VS.ETHDM.Rtt.Means,
                     VS.ETHDM.MaxRttJitter, VS.ETHDM.RttJitter.Means,
                     VS.ETHDM.RttJitterStandardDeviation
DataLink.ETHLM    :  VS.ETHLM.Forward.DropRate, VS.ETHLM.Backward.Drop*,
                     VS.ETHLM.Forward.Peak*, VS.ETHLM.Forward.MinDrop*
IP PM             :  VS.IPPM.Forword.DropMeans, VS.IPPM.Forword.Peak.DropRates
```

### Fronthaul

```
Measurement of eCPRI Port Performance (ECPRIPORT)   -> VS.ECPRIPORT.Tx*/Rx* rate and error counters
```

### NR EN-DC / X2-U user plane

```
N.PDCP.Vol.DL.X2U.TrfPDU.Tx          volume forwarded over X2-U downlink
N.PDCP.Vol.UL.X2U.TrfPDU.Rx          volume received over X2-U uplink
N.PDCP.DL.X2U.TrfPDU.TxPackets       packets forwarded over X2-U downlink
N.PDCP.DL.X2U.ReqRetransPackets      retransmission requests -> loss/delay on the split path
N.PDCP.UL.X2U.TrfPDU.RxPackets
```

### NR EN-DC accessibility and retainability

```
N.NsaDc.SgNB.Add.Att            N.NsaDc.SgNB.Add.Succ
N.NsaDc.SgNB.AbnormRel.Trans    <- transport-attributed EN-DC failures
N.NsaDc.SgNB.AbnormRel.Radio    N.NsaDc.SgNB.AbnormRel.Radio.SUL
N.NsaDc.SgNB.Rel.Coverage       N.NsaDc.SgNB.Rel.SgNBTrigger
N.NsaDc.IntraSgNB.PSCell.Change.Att / .Succ
N.NsaDc.InterSgNB.PSCell.Change.Att / .Succ
N.NsaDc.DRB.Add.Att / .Succ     N.NsaDc.DRB.AbnormRel
```

**Interpretation shortcut:** `N.NsaDc.SgNB.AbnormRel.Trans` materially above zero supports the
vendor's transport claim. At or near zero, while `...AbnormRel.Radio` dominates, points at radio or
mobility instead.

---

## 5.5 Command checklist

Verify syntax against your release; these are the *objects* to inspect, and the intent of each.

### Huawei gNodeB / eNodeB (MML)

| Intent | Command family |
| --- | --- |
| Port state, speed, duplex, errors, pause frames | `DSP ETHPORT`, `LST ETHPORT` |
| Configured MTU on the transport interface | `LST ETHPORT` / interface MTU attribute |
| Node IP addresses | `LST DEVIP` |
| IP path definition and its **carry flag** and bandwidth | `LST IPPATH` — `CARRYFLAG`: `NULL` = physical port, `IPLGCPORT` = IP logical port, `RSCGRP` = transmission resource group |
| Logical port / transmission resource group bandwidth and thresholds | logical-port and resource-group objects |
| Reachability and congestion towards the peer | `PING IP` from the node, sized at 1400/1472/1500 B with DF set |
| SCTP link state and retransmissions | `DSP SCTPLNK` |
| User-plane peer configuration (S1-U / X2-U / N3 endpoints) | user-plane host/peer objects |
| Global transport parameters (incl. DSCP mapping) | global transport parameter object |
| eCPRI / CPRI port rate and errors | eCPRI port display |
| PTP / clock state and phase error | clock status display |
| Board type and CPU load | board display / `NRBoard` counters |

### Routers / transport (generic)

| Intent | Example |
| --- | --- |
| p99 interface rate | 1-minute polling or streaming telemetry; avoid 5/15-minute SNMP means |
| Per-queue drops | per-class queue statistics (output drops, tail drops, WRED) |
| Policer/shaper audit | search running config for `policer`, `shaper`, `cir`, `rate-limit` |
| MTU per interface and per tunnel | interface MTU + tunnel/IPsec MTU |
| LAG/ECMP hash including TEID | Cisco: `ip cef load-sharing algorithm include-ports source destination gtp`; Junos: `enhanced-hash-key gtp-tunnel-endpoint-identifer`; Cumulus: `hash_config.gtp_teid = true` |
| Verify which member a flow takes | Cisco: `show ip cef exact-route … gtp-teid …` |
| DSCP trust and remarking | ingress classification / egress remarking policy per interface |
| Fragmentation counters | IP statistics: fragments created/received/reassembly failures |

### MTU test one-liners (adapt to the platform)

```bash
# Largest unfragmented payload across the path (Linux; 1472 payload = 1500 B IPv4 frame)
ping -M do -s 1472 -c 5 <peer>
ping -M do -s 1500 -c 5 <peer>
ping -M do -s 1572 -c 5 <peer>        # needs a >=1600 B transport MTU

# Binary search for the true limit
for s in 1400 1440 1472 1500 1550 1572; do
  printf '%5s: ' "$s"; ping -M do -s "$s" -c 2 -W 2 <peer> >/dev/null 2>&1 && echo OK || echo FAIL
done

# Confirm PMTUD is not black-holed: these ICMP types must traverse every hop
#   IPv4: type 3 code 4 (fragmentation needed)
#   IPv6: type 2 (packet too big)
```

---

## 5.6 Dimensioning rule to adopt (Action P3.11)

Derived from `tools/tx_budget.py`. Re-run it with your own carrier mix before publishing internally.

| Site profile | Busy-hour requirement | Single-UE peak requirement | Minimum port |
| --- | --- | --- | --- |
| 1 × NR 100 MHz TDD 32T, no LTE sharing | ~1.2 Gbit/s | **~2.1 Gbit/s** | **10GE** (GE is not viable) |
| 3 × NR 100 MHz TDD 32T, no LTE sharing | ~3.2 Gbit/s | ~2.1 Gbit/s | 10GE |
| 3 × NR 100 MHz + 3 × LTE FDD 4T + 3 × LTE TDD, IPsec | **~5.2 Gbit/s** | ~2.2 Gbit/s | **10GE, with 25GE where growth is expected** (all-cells-full-buffer is ~9.4 Gbit/s ≈ 94 % of 10GE) |

Two rules worth writing into the standard:

1. **The single-UE peak requirement, not the busy-hour figure, sets the minimum port speed at a small
   site.** A site can be quiet and still need >2 Gbit/s of instantaneous capacity to pass a speed
   test — which is exactly the KPI being measured against baseline.
2. **Never dimension a 5G site on GE.** One NR cell alone exceeds what a GE port can deliver, by
   roughly a factor of two.

---

## 5.7 Standing monitoring set (Action P3.12)

| Metric | Source | Threshold to alarm on |
| --- | --- | --- |
| p99 port utilisation, ≤60 s | Tx + `VS.FEGE.TxMaxSpeed` | >70 % sustained |
| Per-queue output drops | Router per-class stats | any non-zero on the user-plane class |
| RAN transport drops | `VS.RscGroup.TxDropPkts`, `VS.IPPath.TxDropPkts`, `VS.IP.TxDropPkts` | any non-zero |
| Resource-group available bandwidth | flow-control counters | latched below port capacity |
| X2-U retransmission requests | `N.PDCP.DL.X2U.ReqRetransPackets` | rising trend |
| Transport-caused EN-DC releases | `N.NsaDc.SgNB.AbnormRel.Trans` | any sustained non-zero |
| Transport delay / jitter / loss | `VS.BSTWAMP.*`, `VS.ETHDM.*`, `VS.ETHLM.*` | above design budget |
| Fragmentation | router IP fragment counters | any non-zero on user-plane paths |
| PTP phase error / holdover | clock status | outside ~1100 ns network budget, or any holdover |
| Port errors | `VS.FEGE.RxErrPackets`, CRC, pause frames | any non-zero |
| eCPRI port errors and negotiated rate | `ECPRIPORT` | rate < 25G on a 32T AAU, or any errors |

---

## 5.8 Sources

Standards:

* **TS 38.306 §4.1.2** — NR peak data rate formula; overhead 0.14 (FR1 DL) / 0.08 (FR1 UL)
* **TS 38.101-1 Table 5.3.2-1** — PRB count per bandwidth and SCS
* **TS 37.340** — EN-DC / multi-connectivity, bearer options and `SGNB ADDITION` procedures
* **TS 36.300 §20.1.1** and **TS 36.425 §5.4.2** — split-bearer flow control, Downlink Data Delivery Status
* **TS 28.552 §5.1.1.3.1** — average DL/UL UE throughput in gNB (`ThpVolDl` / `ThpTimeDl`)
* **TS 32.425 §4.4.7** — LTE PDCP SDU data volume and throughput measurements
* **TS 23.501 §5.7.1.8, §5.7.2.6** — AMBR definitions and enforcement points
* **TS 23.501 Annex J** — link MTU considerations; 142 B total overhead, 1358 B reference link MTU
* **TS 23.401** — APN-AMBR / UE-AMBR (EPC)
* **ITU-T G.8275.1**, **Y.1731**, **Y.1564**, **RFC 2544**, **RFC 5357** (TWAMP), **RFC 6438** (IPv6 flow label for tunnel ECMP)

Vendor and industry references:

* Huawei 3900 & 5900 Series Base Station *Node Performance Counter Reference* — `ETHPORT`/`Physical.FEGE`, `Transport.RscGroup`, flow-control measurement, `BSTWAMP`, `ETHDM`, `ETHLM`, `ECPRIPORT`
* Huawei *gNodeBFunction Performance Counter Reference* — `DC.Cell` / `N.NsaDc.*`, `N.PDCP.*.X2U.*`
* Huawei AAU technical specifications (e.g. AAU5636w / AAU5339w) — 2 × eCPRI at 10/25 Gbit/s
* Huawei BBU5900 board specifications — UMPTe/UMPTga 2×FE/GE + 2×FE/GE/10GE (~10 Gbit/s class); UMPTg 25GE; UBBPfw1/UBBPg 1×25 Gbit/s eCPRI for 32T/64T at 100 MHz
* Huawei 5G site design guidance — electrical backhaul is GE only, optical 10GE is the NR default
* Ericsson *Key Performance Indicators, NR* — EN-DC stage 2 volume measured at PDCP **PDU** level vs PDCP **SDU** level for other UEs; `pmFlexPdcpVolDlDrb*`, `pmFlexUeThpTimeDl*`, `...LastTTI` counters
* Cisco IOS XE CEF load-sharing with GTP TEID; Juniper `enhanced-hash-key gtp-tunnel-endpoint-identifer`; NVIDIA Cumulus `hash_config.gtp_teid`
* Industry xHaul dimensioning guidance — 3 × 25 Gbit/s fronthaul per S111 site; ~5 Gbit/s peak early backhaul growing toward ~20 Gbit/s
* Published commercial 32T32R 100 MHz NSA results ≈ 1.19 Gbit/s DL, as a real-world sanity reference
