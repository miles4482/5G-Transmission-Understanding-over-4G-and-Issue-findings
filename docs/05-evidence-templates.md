# 5. Evidence Templates

Copy these into the investigation workbook. A row without the evidence column filled in does not
count as a finding and does not count as a clearance.

---

## 5.1 Site record (one per reference site)

```
Site ID:
Population:            swapped / new
BBU / main board:      (UMPTe / UMPTg / ...)
Backhaul port:         electrical | optical
Negotiated speed:      1G / 10G / 25G        duplex: full / half
SFP rate:              ...
eCPRI per AAU:         AAU1 __ G   AAU2 __ G   AAU3 __ G
IP path TX bandwidth:  NR ___ Mbit/s    LTE ___ Mbit/s
Resource group cap:    ___ Mbit/s / none
Interface MTU (BBU):   ___
IPsec:                 off / on, peer ___
EN-DC option:          3 / 3a / 3x
PDCP SN size DL:       12 / 18
Sync source:           GNSS / PTP     lock: yes / no
TDD pattern:           DDDSU / other ___
RAN throughput licence:___
Baseline UE Tput DL/UL (Phase 0 method):  ___ / ___
Current UE Tput DL/UL:                    ___ / ___
```

## 5.2 AMBR trace (one UE, three values, same session)

```
MSISDN / test SIM:
HSS APN-AMBR DL/UL:
HSS UE-AMBR DL/UL:
S1AP UE-AMBR DL/UL:                 (Initial Context Setup)
NAS APN-AMBR DL/UL:                 (Attach/TAU Accept)
X2AP SgNB UE Aggregate Max BR DL/UL:
restrictDCNR / NR restriction:
Smallest of the three:
Target (from Ch.2):
Match: yes / no
```

## 5.3 Hop table (one row per hop, reference site)

| Hop | Device | Physical rate | CIR / PIR / CBS | p99 Tx during UDP ramp | Class drops during ramp | RTT contribution | MTU | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BBU port | | | | | | | | |
| CSG egress | | | | | | | | |
| Access hop (MW/PON/EVC) | | | | | | | | |
| Aggregation egress | | | | | | | | |
| Core edge | | | | | | | | |
| S-GW/UPF N3/S1-U | | | | | | | | |
| N6 / SGi | | | | | | | | |
| X2-U path (separate) | | | | | | | | |

Verdict is one of: `meets budget`, `short of budget`, `drops at low utilisation`, `not measured`.

## 5.4 Segment test log (Chapter 2 drill)

```
Date / site / tester:
1. Port read:            speed ___  errors ___  MTU ___     pass/fail
2. DF ping gNB->UPF:     1400 ___ 1472 ___ 1500 ___ 1600 ___
   DF ping eNB<->gNB:    1400 ___ 1472 ___ 1500 ___ 1600 ___
3. TWAMP S1-U/N3:        loss ___%  RTT mean ___ ms  max ___ ms  jitter ___ ms
   TWAMP X2-U:           loss ___%  RTT mean ___ ms  max ___ ms  jitter ___ ms
4. UDP ramp loss starts: ___ Mbit/s     hop that dropped first: ___
5. SgNB AMBR from trace: DL ___ UL ___
6. UE test (RSRP ___ SINR ___ rank ___ MCS ___):
      NR-only 1 stream:  DL ___ UL ___
      EN-DC 1 stream:    DL ___ UL ___
      EN-DC 8 stream:    DL ___ UL ___
7. Classification:       transport / policy / radio / test-method
```

## 5.5 Four-mechanism clearance (required before anyone says "no Tx issue")

| Mechanism | Segment | Evidence | Cleared (yes/no) | By |
| --- | --- | --- | --- | --- |
| Capacity | BBU port | p99 vs negotiated rate | | |
| Capacity | first mile | UDP ramp vs CIR | | |
| Capacity | X2-U | path bandwidth + ramp | | |
| Capacity | N3/S1-U | gateway p99 vs licence | | |
| Loss | per class | output-drop counters ≤ 60 s | | |
| Loss | X2-U | TWAMP peak drop, PDCP retx | | |
| Latency | end to end | RTT now vs pre-swap | | |
| Latency | X2-U | TWAMP jitter | | |
| MTU | gNB → UPF | DF ping 1500 | | |
| MTU | eNB ↔ gNB | DF ping 1500 | | |

## 5.6 Counter set to extract for the reference window

Confirm names against your software version. All of these were taken from published Huawei
performance references; the release you run may use a successor name.

**Base-station transport (Node)**

* `VS.FEGE.TxMaxSpeed`, `VS.FEGE.RxMaxSpeed`, `VS.FEGE.TxMeanSpeed`, `VS.FEGE.RxMeanSpeed`
* `VS.FEGE.TxTotalBW`, `VS.FEGE.RxTotalBW`, `VS.FEGE.RxErrPackets`
* `VS.IPPath.TxMaxSpeed`, `VS.IPPath.RxMaxSpeed`, `VS.IPPath.TxMeanSpeed`, `VS.IPPath.TxDropPkts`, `VS.IPPath.RxDropPkts`
* `VS.RscGroup.TxDropPkts`, `VS.RscGroup.TxDropBytes`
* `VS.Gtpu.RxDropPkts`, `VS.Gtpu.RxDropBytes`
* `VS.IP.TxDropPkts`, `VS.IP.RxDropPkts`
* `VS.BSTWAMP.Rtt.Means`, `VS.BSTWAMP.MaxRttDelay`, `VS.BSTWAMP.Forward.DropMeans`, `VS.BSTWAMP.Forward.Peak.DropRates`
* `VS.ETHDM.Rtt.Means`, `VS.ETHDM.MaxRttDelay`
* eCPRI port Rx/Tx and error counters (`VS.ECPRIPORT.*`)

**gNodeB function**

* `N.NsaDc.SgNB.Add.Att`, `N.NsaDc.SgNB.Add.Succ`, `N.NsaDc.SgNB.AbnormRel.Trans`
* `N.PDCP.DL.X2U.TrfPDU.TxPackets`, `N.PDCP.DL.X2U.ReqRetransPackets`
* `N.PDCP.Vol.DL.X2U.TrfPDU.Tx`, `N.PDCP.Vol.UL.X2U.TrfPDU.Rx`

**From the routers, per class, ≤ 60 s:** offered rate, drop count, queue depth, and the p95/p99 of
each. A mean without a peak is not accepted (Chapter 2, Rule 1).

## 5.7 Finding record

```
ID:
Sites affected (count and %):
Segment:        RAN port / RAN shaper / fronthaul / X2-U / first mile /
                aggregation / core policy / core path / IP (MTU|ECMP|firewall) /
                sync / radio / KPI-method
Mechanism:      capacity / loss / latency / MTU / policy / radio / measurement
Evidence:       <counter or trace, timestamp, granularity>
Effect:         estimated Mbit/s returned per site if fixed
Fix:
Owner:
Verified by re-measurement on (date, site):
Delta after fix (Phase 0 method):
```

## 5.8 Command checklist

Confirm syntax on your release. These are the objects to inspect and why.

### Base station

| Intent | Where to look |
| --- | --- |
| Port state, negotiated speed, duplex, errors, pause | `DSP ETHPORT` / `LST ETHPORT` |
| Interface MTU | Ethernet port / interface attribute |
| Node IP addresses | `LST DEVIP` |
| IP path bandwidth and what it is bound to | `LST IPPATH`. `CARRYFLAG`: `NULL` = physical port, `IPLGCPORT` = logical port, `RSCGRP` = transmission resource group |
| Resource-group bandwidth | resource-group object named by the IP path |
| Reachability with DF set | `PING IP` from the node at 1400 / 1472 / 1500 bytes |
| SCTP state and retransmits | `DSP SCTPLNK` |
| S1-U / X2-U / N3 peers | user-plane host and peer objects |
| DSCP map | global transport / DSCP mapping object |
| eCPRI rate and errors | eCPRI port display |
| PTP / GNSS lock and time error | clock status |
| Board type and CPU | board inventory, `NRBoard` counters |

### Routers

| Intent | Where to look |
| --- | --- |
| p99 interface rate | 1-minute polling or streaming telemetry |
| Per-queue drops | per-class output, tail, and WRED drop counters |
| Hidden policers | running config: policer, shaper, cir, rate-limit |
| MTU | interface MTU and tunnel / IPsec MTU |
| LAG / ECMP hash includes the GTP TEID | platform load-sharing or enhanced-hash-key configuration |
| Which member one flow uses | exact-route / hash lookup with the TEID |
| DSCP trust and remark | ingress class-map and egress remarking policy |
| Fragmentation | IP fragment created / failed-reassembly counters |

### MTU sweep from a Linux host on the path

```bash
# 1472 bytes of payload = a 1500-byte IPv4 packet. 1572 needs a 1600-byte transport MTU.
for s in 1400 1440 1472 1500 1550 1572; do
  printf '%5s: ' "$s"
  ping -M do -s "$s" -c 2 -W 2 <peer> >/dev/null 2>&1 && echo OK || echo FAIL
done
```

PMTUD stays alive only if these ICMP types pass every firewall on the path: IPv4 type 3 code 4 (fragmentation needed), IPv6 type 2 (packet too big).

## 5.9 Dimensioning rule

From `tools/tx_budget.py` with the default DDDSU pattern, 15 % X2-U allowance, and a 1400-byte payload. Re-run with your own carrier mix before publishing the numbers internally.

| Site | Busy hour | Single-UE peak | Minimum port |
| --- | --- | --- | --- |
| 1 × NR 100 MHz TDD | ~1.2 Gbit/s | **~2.1 Gbit/s** | **10GE**. GE tops out near 0.95 Gbit/s of goodput |
| 3 × NR 100 MHz TDD, no LTE on the port | ~3.6 Gbit/s | ~2.1 Gbit/s | 10GE |
| 3 × NR 100 MHz + 3 × LTE FDD 4T + 3 × LTE TDD, IPsec | **~5.2 Gbit/s** | ~2.2 Gbit/s | 10GE, and 25GE wherever a second carrier or a busy-hour growth is planned. All cells full-buffer at once is ~9.4 Gbit/s |

Two rules:

1. **The single-UE peak sets the minimum port on a small site.** A quiet site still needs more than 2 Gbit/s instantaneously to pass the speed test that the KPI is judged on.
2. **Dimension every 5G site at 10GE or above.** One NR cell needs about twice what a GE port can deliver.

## 5.10 Standing alarms

| Metric | Source | Alarm when |
| --- | --- | --- |
| Negotiated backhaul rate | port status | below 10GE on a 5G site |
| eCPRI rate | `ECPRIPORT` | below 25G on a 32T AAU, or any error growth |
| p99 port utilisation | `VS.FEGE.TxMaxSpeed` and router telemetry, ≤ 60 s | above 70 % |
| RAN transport drops | `VS.RscGroup.TxDropPkts`, `VS.IPPath.TxDropPkts` | any increase during user traffic |
| X2-U retransmission | `N.PDCP.DL.X2U.ReqRetransPackets` | rising trend |
| Transport-cause EN-DC release | `N.NsaDc.SgNB.AbnormRel.Trans` | sustained above zero. If `AbnormRel.Radio` dominates instead, the cause is radio, not transport |
| Delay, jitter, loss | `VS.BSTWAMP.*`, `VS.ETHDM.*` | above the design budget, or peak loss above zero |
| Fragmentation | router IP statistics | any fragments on the user-plane path |
| PTP / GNSS | clock status | unlocked, in holdover, or outside the G.8275.1 time-error budget |
| Port errors | `VS.FEGE.RxErrPackets`, CRC, pause | any growth |
| LAG member | bundle status | any member down, not only the bundle down |
