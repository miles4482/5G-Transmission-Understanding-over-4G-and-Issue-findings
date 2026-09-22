# 2. Baseline, Budget, and the Measurement Contract

Before any root-cause hunting, three things must be nailed down, in this order. Skipping them is why
these disputes run for months.

1. **Step 0 — Is the degradation real, or a KPI-definition artefact?**
2. **Step 1 — What is the *physically possible* ceiling, and what does transport have to carry?**
3. **Step 2 — What evidence will both the vendor and the Tx team accept?**

---

## 2.1 Step 0: prove the degradation is real (do this first, it is cheap)

You are comparing an Ericsson-measured baseline against a Huawei-measured result. Those are **not the
same measurement**, even when both claim to follow 3GPP.

The 3GPP definition (TS 28.552 §5.1.1.3.1 for NR, TS 32.425 §4.4.7 for LTE) is:

```
Average DL UE throughput = sum(ThpVolDl) / sum(ThpTimeDl) x 1000   [kbit/s]
```

where **both** the volume and the time **exclude the slot/TTI in which the buffer is emptied**, and the
measurement is only meaningful for bursts large enough to span multiple slots.

Now the traps, all of which are real and all of which produce double-digit percentage deltas:

| Trap | Why it changes the number |
| --- | --- |
| **PDCP SDU vs PDCP PDU level** | Ericsson's EN-DC counters measure volume **on PDCP PDU level for UEs in EN-DC stage 2, and on PDCP SDU level for other UEs**. PDU level includes PDCP headers; SDU level does not. Mixing the two shifts the result. |
| **Last-TTI exclusion handling** | Ericsson exposes explicit `...LastTTI` counters that must be subtracted. If your Ericsson baseline formula did that and your Huawei formula does not (or vice versa), the numbers diverge — small bursts drag the average down hard. |
| **Where the split-bearer volume is counted** | In EN-DC, is the NR-leg volume attributed to the NR cell, the LTE cell, or both? Vendors differ. A "5G user throughput" KPI that previously included the LTE leg and now excludes it will drop without anything breaking. |
| **Scope: cell vs UE vs DRB** | `L.Thrp.bits.DL` / cell-volume counters measure PDCP SDUs handed to RLC for a whole cell — that is **cell capacity**, not user experience. Do not compare it to a UE-throughput KPI. |
| **Aggregation** | An average-of-averages across cells is not the same as a volume-weighted average. Weight by `ThpVol`, always. |
| **Filters** | QCI/5QI filter, UE-type filter, EN-DC stage filter, PLMN filter. One mismatched filter invalidates the comparison. |
| **Sample floor** | New Huawei sites carrying little traffic produce tiny bursts, `ThpTime = 0` samples, and unstable averages. Exclude cells below a minimum volume threshold. |

### Step 0 action points

| # | Action | Owner | Evidence that closes it |
| --- | --- | --- | --- |
| 0.1 | Write down the **exact** Ericsson KPI formula used for the baseline (counter names + arithmetic) and the exact Huawei formula now in use | Performance / OSS | Two formulas side by side in one document |
| 0.2 | Confirm both measure the same layer (SDU vs PDU), the same last-TTI rule, the same EN-DC attribution, and the same filters | Performance + both vendors | Signed-off mapping table |
| 0.3 | Re-baseline using a **vendor-neutral** measurement as referee: drive-test / UE-side logs (e.g. per-second app throughput) or scripted speed tests on a fixed route with a fixed server | RF / Drive test | Before/after on the same clusters, same route, same UE model, same time of day |
| 0.4 | Split the site population into **swapped sites** (have a baseline) and **new sites** (no baseline). Never mix them in one KPI trend | Performance | Two separate trend lines |
| 0.5 | Segment by band/carrier and by EN-DC stage, so an NSA anchoring problem cannot hide inside an aggregate | Performance | Per-carrier, per-stage breakdown |

**If Step 0 shows the drop is 5–15 % and concentrated in the KPI formula, stop.** You have saved
months. Experience across swap projects says a meaningful fraction of "post-swap degradation" is
measurement change. The rest of this document assumes some real degradation survives Step 0.

---

## 2.2 Step 1: the physical ceiling and the transport budget

Use `tools/tx_budget.py` in this repository. It implements the TS 38.306 §4.1.2 peak-rate formula,
applies the TDD time share, then adds protocol expansion and the EN-DC X2-U allowance.

### One NR cell, 100 MHz, 30 kHz SCS, 4 DL layers, 256QAM, DDDSU

```
$ python3 tools/tx_budget.py --preset single-cell
```

| Quantity | Value |
| --- | --- |
| Air-interface peak, no TDD split | 2337 Mbit/s |
| **After DDDSU (74.3 % DL)** | **1736 Mbit/s DL** |
| UL, 2 layers, 256QAM, 22.9 % UL share | 286 Mbit/s |
| **Transport needed for a single-UE DL peak test (no IPsec)** | **~2116 Mbit/s on the wire** |
| Max user goodput a **1GE** port can ever deliver | **~945 Mbit/s** |

**Read that last pair again.** A single 100 MHz 32T32R NR cell at full 4-layer 256QAM can schedule
more than **1.7 Gbit/s**, which needs **over 2 Gbit/s of wire capacity** once GTP-U/UDP/IP/VLAN/Ethernet
expansion is counted. A **GE backhaul port physically cannot deliver more than ~945 Mbit/s of user
goodput**, and that is before LTE takes its share. So:

> If any swapped 5G site is backhauled over a GE electrical (RJ45) port, a 1G SFP, a 1G-limited
> microwave hop, or a GE-limited ring segment, then **the vendor is right** — there is a genuine
> transmission capacity limit — and **the Tx team is also right** that nothing is faulty. It is a
> dimensioning gap, and the fix is a port/hop upgrade, not troubleshooting.

Huawei's own site-design guidance is explicit: the electrical (RJ45) backhaul option supports **GE
only**, the optical option supports **10GE**, and because "the NR backhaul bandwidth is greater than
GE", a **10GE optical module is the default** rather than GE or 2.5GE. On BBU5900, **UMPTe/UMPTga**
provide 2 × FE/GE electrical plus 2 × FE/GE/10GE optical with a **~10 Gbit/s** total transmission
capability, while **UMPTg** provides **25GE** ports.

### The full swapped site (3 × NR 100 MHz TDD 32T + 3 × LTE FDD 4T 20 MHz + 3 × LTE TDD 4L 20 MHz), IPsec on

```
$ python3 tools/tx_budget.py --preset swap-site --ipsec
```

| Quantity | Value |
| --- | --- |
| Wire expansion with IPsec + 1 VLAN | **×1.111 (11.1 % overhead)** |
| NR radio peak, 3 cells | 5208 Mbit/s DL |
| LTE radio peak, 6 carriers | 2108 Mbit/s DL |
| Site radio peak total | **7316 Mbit/s DL** |
| Single-UE peak test requirement | 2221 Mbit/s |
| **Busy-hour requirement (55 % concurrency)** | **5227 Mbit/s** |
| All cells full buffer simultaneously | **9432 Mbit/s** |
| Max user goodput on 10GE | ~9003 Mbit/s |

Two conclusions that matter for the vendor discussion:

1. **10GE is the right answer, GE is not, and 10GE is not comfortable.** The all-cells-full-buffer
   figure (9.43 Gbit/s) is ~94 % of a 10GE port. Under a synchronised load test across all sectors,
   a 10GE-backhauled site **will** hit its port ceiling. That is expected behaviour, not a fault —
   but it must be excluded from single-user throughput testing, because a saturated port is exactly
   where a single user's TCP flow gets its packets dropped.
2. **IPsec costs you ~5 points of overhead** (5.9 % → 11.1 % at a 1400 B payload). If IPsec was
   introduced or moved as part of the swap, that alone shaves throughput, and it also shrinks the
   usable MTU, which is the far bigger risk (see §2.3).

### Adjust the model to your reality

```bash
# Option 3 (not 3x): X2-U carries the whole NR share, so set the allowance to 100%
python3 tools/tx_budget.py --preset swap-site --ipsec --x2u-share 1.0

# A different TDD pattern
python3 tools/tx_budget.py --nr 100:30:4:2:256qam --nr-cells 3 --tdd DDDDDDDSUU

# Your actual LTE mix, e.g. FDD 20 MHz 4T + FDD 10 MHz + TDD 20 MHz (UL/DL config 2)
python3 tools/tx_budget.py --nr 100:30:4:2:256qam --nr-cells 3 \
    --lte 20:4:1:256qam --lte 10:4:1:64qam --lte 20:4:1:256qam:LTE_C2 --ipsec

# Small packets are much more expensive: gaming/VoIP-style 256 B payloads
python3 tools/tx_budget.py --preset swap-site --ipsec --payload 256
```

The last one is worth running: at a 256-byte payload with IPsec the expansion factor jumps from
**×1.11 to ×1.61 (60.6 % overhead)**, and the usable goodput on a GE port falls from ~900 to
**~623 Mbit/s**. That is why **packet rate (pps), not just bit rate, can be the real limit** on a
policer, a firewall, an IPsec engine, or a microwave modem.

Running the same site as **Option 3** (`--x2u-share 1.0`, i.e. the whole NR share crossing X2-U) pushes
the driving requirement to **~9.0 Gbit/s** — technically inside a 10GE port but with no headroom at all.
If any cluster is on Option 3 rather than 3x, that alone can explain the degradation.

### Step 1 action points

| # | Action | Owner | Evidence that closes it |
| --- | --- | --- | --- |
| 1.1 | Produce a per-site inventory: BBU type, main control board (UMPTe/UMPTg/…), **backhaul port type and negotiated speed**, optical module rate, VLAN/IPsec status | RAN + Tx | Spreadsheet, all swapped + new 5G sites |
| 1.2 | Flag every 5G site whose backhaul negotiated rate is **< 10 Gbit/s**, or whose first-mile hop (microwave, GPON, leased line, ring segment) is < 10 Gbit/s | Tx | Exception list with count and % of sites |
| 1.3 | For each flagged site, compute the required capacity with `tx_budget.py` and attach it to the upgrade request | RAN planning | Per-site required vs available |
| 1.4 | Verify **fronthaul** rate per 32T AAU is negotiated at **25 Gbit/s**, not 10 Gbit/s, and check eCPRI port error counters | RAN | `DSP` output / eCPRI port statistics per AAU |
| 1.5 | Confirm the theoretical ceiling matches what you are demanding: if the baseline target was set on a different TDD pattern, layer count or UE category, the target itself may be wrong | RF planning | Target vs TS 38.306 calculation |

---

## 2.3 Step 2: the measurement contract (this is what ends the argument)

The vendor and the Tx team are using incompatible evidence. Force a shared standard. Every item below
is a deliberate counter to a specific way this dispute usually stalls.

### Rule 1 — Averaging window: p99 at 1 minute or finer, never 15-minute means

A 1.7 Gbit/s NR burst into a 1 Gbit/s port for 200 ms destroys a speed test and registers as roughly
**2 % utilisation on a 15-minute average**. Any capacity claim based on 5- or 15-minute averages is
inadmissible. Require:

* Interface counters at **≤ 60 s granularity**, reported as **p95 and p99**, not mean.
* **Queue-level statistics**: per-class output drops, tail drops, WRED drops, and queue depth/latency
  on every hop. **Output drops with low average utilisation is the signature of a microburst
  bottleneck** and is the single most useful piece of evidence in this entire investigation.
* On the Huawei gNodeB side, the Ethernet-port measurement (`ETHPORT` / `Physical.FEGE`) exposes
  max/mean/min rate and available bandwidth — for example `VS.FEGE.TxMaxSpeed`,
  `VS.FEGE.RxMaxSpeed`, `VS.FEGE.TxMeanSpeed`, `VS.FEGE.TxTotalBW`, `VS.FEGE.RxErrPackets`. Use the
  **Max** variants; the Mean variants are what make an overloaded port look idle. Confirm exact
  counter names against your release's *Node Performance Counter Reference*.

### Rule 2 — Measure per segment, not end to end

An end-to-end test that fails tells you nothing about *where*. Decompose:

| Test | Isolates | Method |
| --- | --- | --- |
| gNB → first-hop router (CSG) | Last mile / port / MTU | On-net iperf or Y.1564/Y.1731 to the CSG; RFC 2544/Y.1564 service activation test on the EVC |
| gNB → S-GW/UPF (S1-U / N3 path) | Backhaul + aggregation + core edge | Node-to-node loopback test, TWAMP, or a probe at the UPF site |
| eNB ↔ gNB (X2-U path) | EN-DC split path, incl. latency/jitter | Bidirectional TWAMP/Y.1731 between the two node IPs on the **X2-U VLAN/DSCP** |
| UPF/PGW → internet server (N6/SGi) | Peering, CGNAT, TCP proxy, server capacity | Test from a host on the SGi LAN to the same server the speed test uses |
| UE → server, full path | End-user experience | Scripted speed test, fixed server, fixed UE, fixed location |

Run the *same* test with the *same* tool at the *same* time so the results are comparable. Record RTT
and jitter on every one, not just throughput.

### Rule 3 — Test with the traffic profile that actually matters

* **Single TCP stream is the strictest test** and the one that exposes latency, loss, and MTU issues.
  A single flow is capped at `receive_window / RTT`; 1 % loss can cut a long-RTT TCP flow by an order
  of magnitude.
* **Multi-stream (8–16 parallel TCP)** is what commercial speed-test apps use and what your baseline
  was probably measured with. If multi-stream is fine and single-stream is broken, the cause is
  **latency, loss, or MTU** — not capacity.
* **UDP at a fixed rate** separates capacity from TCP dynamics. Ramp it: 100 Mbit/s → 500 → 1 G →
  1.5 G → 2 G, and record the exact rate at which loss begins. That rate **is** your transport
  ceiling, stated as a number both teams can see.
* **Record the MTU/MSS in use.** Capture on the SGi/N6 side and confirm the negotiated MSS.

### Rule 4 — Every claim carries the evidence that proves it

Ban unqualified statements. "Transmission capacity issue" is only admissible with: node, interface,
timestamp, granularity, p99 rate, configured capacity, and drop counters. "No Tx issue" is only
admissible with the same fields, plus explicit confirmation on the four mechanisms below.

### Rule 5 — The four-mechanism checklist

Transport degrades throughput four independent ways. The Tx team has usually only disproven the first
two. Require a yes/no with evidence on **all four**, per segment:

| # | Mechanism | Disproven by | Typical blind spot |
| --- | --- | --- | --- |
| 1 | **Insufficient capacity** | p99 rate vs configured/licensed capacity, per segment | 15-minute averaging |
| 2 | **Packet loss** | Per-queue output drops, CRC/error counters, TWAMP loss | Loss only during microbursts; loss only in one DSCP class |
| 3 | **Added latency / jitter** | Before-vs-after RTT to a fixed reference; TWAMP delay + jitter on X2-U and N3 | Not measured at all. Kills EN-DC flow control and single-flow TCP with zero loss. |
| 4 | **MTU / fragmentation** | DF-bit ping sweep hop by hop; fragment counters; PMTUD ICMP reachability | Never checked. Produces the exact "no errors anywhere but throughput is broken" pattern. |

If the answer to #3 or #4 is "we did not measure it", that is your next action, and it is cheap.

---

## 2.4 The joint test drill — one day, one site, ends most disputes

Pick **one** swapped site with clear degradation and **one** new Huawei site performing well. Put RAN,
Tx, core, and IP in the same room or call, and execute in order. Stop at the first step that fails —
that is your bottleneck class.

| Step | Action | Pass criterion | If it fails |
| --- | --- | --- | --- |
| 1 | Read the backhaul port: type, negotiated speed, duplex, errors, MTU | 10GE optical, no errors, MTU ≥ 1600 | Capacity/port finding → §3.1, §3.2 |
| 2 | DF-bit ping sweep gNB → S-GW/UPF at 1400/1472/1500/1600 B | 1500 B with DF passes | MTU finding → §3.4 |
| 3 | TWAMP/Y.1731 on the S1-U/N3 DSCP: RTT, jitter, loss for 15 min | Loss 0 %, jitter within design | Loss/latency finding → §3.2, §3.4 |
| 4 | Same on the X2-U path between eNB and gNB | Loss 0 %, low jitter | EN-DC flow-control finding → §3.1, §3.3 |
| 5 | UDP ramp gNB-side host → UPF-side host: 0.5/1/1.5/2 Gbit/s | 2 Gbit/s clean | Capacity ceiling identified numerically |
| 6 | Decode one `SGNB ADDITION REQUEST`: read `SgNB UE Aggregate Maximum Bit Rate` | Matches intended UE-AMBR share | Hidden RAN/policy cap → §3.1, §3.3 |
| 7 | Single-UE test: NR-only (LTE leg blocked), then EN-DC, then multi-stream | NR-only ≈ theoretical × 0.7–0.8 | Compare the three to localise the leg |
| 8 | Repeat steps 1–7 on the good new site and diff every value | — | The diff is your root cause |

Record everything in the template in [Chapter 5](05-evidence-templates.md).

Continue to [Chapter 3: Domain-by-domain checks and action points](03-domain-by-domain-checks.md).
