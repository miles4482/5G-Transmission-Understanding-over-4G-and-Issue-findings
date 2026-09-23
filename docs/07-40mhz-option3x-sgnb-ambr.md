# 7. Your case: 40 MHz, NSA Option 3x, 100 Mbit/s vs 250 Mbit/s

This chapter is the working procedure for the network as it actually is:

* NR carrier **40 MHz**, TDD, 2.6 GHz, 32T
* NSA **Option 3x** (user plane anchors on the gNodeB, S1-U terminates on the gNodeB)
* Measured 5G DL user throughput about **100 Mbit/s**
* Expected **250 Mbit/s** on average, or higher

The 100 MHz budgets in Chapters 1–2 do not apply to this carrier. The numbers below do.

---

## 7.1 What 40 MHz can actually deliver

TS 38.306 §4.1.2, 40 MHz, 30 kHz SCS, 106 PRBs, DDDSU (74.3 % downlink). Reproduced with:

```bash
python3 tools/tx_budget.py --nr 40:30:4:2:256qam --tdd DDDSU
```

| Radio state during the test | Air-interface DL peak | What a single-user test can realistically land |
| --- | --- | --- |
| 4 layers, 256QAM | **674 Mbit/s** | 300–500 Mbit/s in strong RF |
| 4 layers, 64QAM | 506 Mbit/s | 200–350 Mbit/s |
| 2 layers, 64QAM | **253 Mbit/s** | 120–200 Mbit/s |
| 1 layer, 256QAM | 169 Mbit/s | 80–140 Mbit/s |

Two consequences:

* **250 Mbit/s average is a real target only when the UE is scheduled with 4 layers and 256QAM.** It is about 37 % of the 674 Mbit/s peak, which is a normal result for a good-coverage sample. It is essentially the *peak* of a 2-layer 64QAM cell, so a network stuck at rank 2 and 64QAM will never average 250.
* **A flat 100 Mbit/s is not the radio ceiling of this carrier**, and it is not a GE-port ceiling either. One 40 MHz cell needs about **820 Mbit/s** on the wire at peak, which a GE port can still pass. A transport team that says "the 1G/10G tail is not full" is describing this site correctly. The missing 150 Mbit/s is somewhere that stops the scheduler before the port fills up.

So the first job is to separate three different "100 Mbit/s"s. They have different owners.

| What you measured | What it means | Who fixes it |
| --- | --- | --- |
| Phone speed test ≈ 100, and it stays ≈ 100 from −80 dBm to −100 dBm | A rate cap. AMBR, a policer, or a licence. Radio and transport utilisation will both look idle. | Core profile, or the eNodeB split, or a CIR |
| Phone speed test ≈ 100, and it climbs when you walk closer to the site | Radio. Rank, MCS, interference, TDD pattern. | RAN RF |
| Phone speed test ≈ 250, while the **NR cell KPI** says ≈ 100 | The user is fine. The KPI is only counting the NR leg, and Option 3x is sending part of the download over LTE. | Split policy (`DlDataPdcpSplitMode`), or the KPI formula |

Do the phone test and the KPI at the same minute, on a known spot, before anyone changes a parameter.

---

## 7.2 What SgNB UE Aggregate Maximum Bit Rate actually is

Three different rates get called "AMBR". Only the third one is the 5G cap, and only the LTE eNodeB chooses it.

```
HSS / PCRF                         MME                              LTE eNodeB (MeNB)
APN-AMBR  (per APN)        -->     UE-AMBR = min(subscribed UE-AMBR,
                                                   sum of active APN-AMBRs)
                                   sent on S1 in
                                   INITIAL CONTEXT SETUP REQUEST
                                                                        |
                                                                        | the eNodeB keeps a share
                                                                        | for itself and gives the rest
                                                                        | to 5G
                                                                        v
                                                              X2: SGNB ADDITION REQUEST
                                                              SgNB UE Aggregate Maximum Bit Rate
                                                              (downlink and uplink, separately)
                                                                        |
                                                                        v
                                                              gNodeB MAC scheduler will not
                                                              exceed this number, ever
```

The standard text is TS 36.423 §9.1.4.1. The IE is **mandatory**. Its definition (§9.2.12) says the UE-AMBR "is split into MeNB UE Aggregate Maximum Bit Rate and SgNB UE Aggregate Maximum Bit Rate which are enforced by MeNB and en-gNB respectively."

Option 3x does not remove this. Option 3x only moves the user-plane anchor to the gNodeB. The eNodeB is still the master, it still sends this IE, and the gNodeB still enforces whatever number it receives. A 100,000,000 bit/s value here produces a download that sits on 100 Mbit/s with a perfectly idle S1-U port.

### Why a transport probe cannot see it

The cap is applied in the scheduler, **before** packets are offered to the port.

In Option 3x the download path is S-GW → S1-U → gNodeB PDCP → air interface. The gNodeB is told "do not deliver more than X bit/s for this UE". It schedules X bit/s. The S1-U port therefore carries X bit/s and has spare capacity. TWAMP is clean. Queue drops are zero. Interface utilisation is low. Every transmission check passes, because the packets that would have proved congestion were never sent.

That is the whole meaning of "invisible to every transport probe". The probe measures what was transmitted. This parameter decides what is allowed to be transmitted. The only place the number exists is inside the X2 **signalling** message that created the 5G leg, and in the subscriber profile that fed it.

A useful cross-check: during the 100 Mbit/s test, record NR MCS, rank, and PRB allocation.

* MCS high, rank 3 or 4, PRBs only partly used, throughput glued to 100: the scheduler is rate-limiting. This is AMBR, a policer, or a licence.
* MCS low or rank 1, PRBs full, throughput 100: the radio ran out of bits. AMBR is not the cause.

---

## 7.3 Where to read the value

Read it on **one test UE**, in **one session**, in this order. The smallest of the three numbers is the cap. Units on the wire are **bit/s**: 100 Mbit/s is `100000000`, 250 Mbit/s is `250000000`.

### 1. S1, on the eNodeB — what the core allowed in total

Trace interface **S1**, message **INITIAL CONTEXT SETUP REQUEST** (also the UE CONTEXT MODIFICATION REQUEST if the session was updated later).

IE path:

```
uEaggregateMaximumBitRate
    uEaggregateMaximumBitRateDL
    uEaggregateMaximumBitRateUL
```

This is the total for LTE + NR. If this downlink value is already 100 Mbit/s, stop looking at the gNodeB. The eNodeB cannot give 5G more than the MME gave it. Fix the profile (step 7.4).

### 2. X2, on the eNodeB — what 5G was actually given

Trace interface **X2**, message **SGNB ADDITION REQUEST**. Repeat on **SGNB MODIFICATION REQUEST**, because a later modification can lower the value without a new addition.

IE path, from TS 36.423:

```
SgNB UE Aggregate Maximum Bit Rate
    UE Aggregate Maximum Bit Rate Downlink
    UE Aggregate Maximum Bit Rate Uplink
    Extended UE Aggregate Maximum Bit Rate Downlink     (optional)
    Extended UE Aggregate Maximum Bit Rate Uplink       (optional)
```

**If an Extended IE is present, use it and ignore the non-extended IE.** The standard says the non-extended value shall be ignored in that case. Wireshark shows the same names under `SgNBAdditionRequest`.

In U2020 / MAE, create a signalling trace on the **eNodeB** (the master), interface X2, and start it before the UE enables 5G. Filter the output for `SgNBAdditionRequest`. The gNodeB trace shows the same message arriving; either end is valid, the eNodeB end is the one that chose the number.

### 3. HSS — why the core sent that number

For the same MSISDN, read:

* APN-AMBR downlink and uplink, per APN
* Subscribed UE-AMBR downlink and uplink
* Any PCRF/PCF rule that overrides APN-AMBR (fair-usage, roaming, time-of-day, location)

The MME sets UE-AMBR to the sum of active APN-AMBRs, capped by the subscribed UE-AMBR (TS 23.401). A leftover LTE package of 100 Mbit/s, or a PCRF rule, fully explains a network-wide 100 Mbit/s result after a swap: the radio got faster and the subscription did not.

### 4. The eNodeB parameter that divides the uplink

On the eNodeB:

```
LST NSADCMGMTCONFIG:;
```

Huawei's NSA feature description (EPC-based NSA, SRAN15.1) states that at initial SCG setup the MeNB and SgNB AMBRs are allocated by proportion, and names one parameter for that proportion:

| Parameter | MO | What it does |
| --- | --- | --- |
| `NsaDcUeMcgUlAmbrRatio` | `NsaDcMgmtConfig` | Percent of the **uplink** UE-AMBR kept on LTE. The gNodeB receives the rest. Recommended value in that document is **49** (LTE 49 %, NR 51 %). |

This parameter is documented for the **uplink**. It will not, by itself, explain a downlink gap. It does explain an uplink gap, and a value near 100 starves NR uplink (the feature also forbids 100 when uplink data is allowed on NR, and forbids 0 when uplink data is allowed on LTE).

Downlink uses the same X2 IE, but the parameter that computes the downlink share has moved between releases. On the version you run, open the parameter help for `NsaDcMgmtConfig` and search for `Ambr`. Record every AMBR-related parameter and its value. Do not assume a downlink parameter name from another release. The X2 trace remains the authority, because it is the number the gNodeB enforces, whatever formula produced it.

### 5. Option 3x split, because it changes which counter moves

Confirm the bearer really is Option 3x, on the eNodeB and the gNodeB:

| Node | Parameter | Value for Option 3x with NR carrying the download |
| --- | --- | --- |
| eNodeB | `CellQciPara.NsaDcDefaultBearerMode` | `SCG_SPLIT_BEARER` |
| gNodeB | `gNBPdcpParamGroup.DlDataPdcpSplitMode` | `SCG_ONLY` (all DL on NR) or `SCG_AND_MCG` (dynamic) |

`DlDataPdcpSplitMode = MCG_ONLY` sends the whole download to LTE. The phone may still be fast, and the 5G cell throughput counter stays low. `SCG_AND_MCG` splits using X2 delay and buffer status; a slow X2 pushes more onto LTE and the NR counter falls. Compare the phone result with the NR counter before treating 100 Mbit/s as a capacity problem.

---

## 7.4 How to decide, then what to change

Run this on one commercial SIM and one lab SIM, same phone, same spot, RSRP better than −85 dBm.

| SgNB AMBR DL from the X2 trace | S1 UE-AMBR DL | Phone result | Conclusion and action |
| --- | --- | --- | --- |
| ≤ 150 Mbit/s | ≤ 150 Mbit/s | ~100 Mbit/s | The **subscription** is the cap. Raise HSS APN-AMBR DL and subscribed UE-AMBR DL to at least **1 Gbit/s** for the 5G package. The 40 MHz 4-layer peak is 674 Mbit/s; a 1 Gbit/s profile leaves the radio as the limit. Check PCRF is not writing 100 Mbit/s back over the top. |
| ≤ 150 Mbit/s | ≥ 500 Mbit/s | ~100 Mbit/s | The core allowed enough. The **eNodeB gave 5G too little**. Find the AMBR parameter under `NsaDcMgmtConfig` on your release and raise the SgNB downlink share so the X2 IE is at least 500 Mbit/s. |
| ≥ 500 Mbit/s | ≥ 500 Mbit/s | ~100 Mbit/s, MCS high, rank ≥ 3 | AMBR is cleared. Look for a **100 Mbit/s policer** on the S1-U / N3 service (CIR left from LTE) or a gNodeB throughput licence. A UDP test at 300 Mbit/s from the site to the S-GW settles it the same day. |
| ≥ 500 Mbit/s | ≥ 500 Mbit/s | ~100 Mbit/s, rank 1–2 or 64QAM | Radio. 2-layer 64QAM peaks at 253 Mbit/s, so an average near 100 is ordinary. Turn on the 256QAM MCS table and check why rank stays at 1 or 2 (SRS, CSI-RS, UE capability). 250 Mbit/s average needs rank 4. |
| ≥ 500 Mbit/s | ≥ 500 Mbit/s | phone ~250, NR KPI ~100 | Split or KPI. Read `DlDataPdcpSplitMode`. If the user is the KPI, count NR + LTE legs, or set the download path to `SCG_ONLY` and re-measure. |

After any AMBR change the UE has to drop the 5G leg and add it again. Airplane mode on the test phone is enough. An already-connected UE keeps the old IE until the next SgNB addition or modification.

### Uplink, while you are in the same MO

```
MOD NSADCMGMTCONFIG: NsaDcUeMcgUlAmbrRatio=49;
```

49 is the value Huawei's own NSA feature description recommends. NR then receives 51 % of the uplink UE-AMBR. Move it only after you have read the current value, and only if the uplink complaint matches a high LTE share. Confirm the new value in the next `SGNB ADDITION REQUEST` uplink IE, not from the command echo.

### What "fixed" looks like

On the same spot, same phone, after a fresh 5G addition:

* X2 SgNB AMBR downlink ≥ 500 Mbit/s
* S1 UE-AMBR downlink ≥ the X2 value
* Phone DL speed test moves off 100 Mbit/s and follows RSRP, instead of sitting on a round number
* NR MCS and rank recorded beside the speed, so a remaining gap is classified as radio or as transport in one pass

If the speed test then reaches 250 Mbit/s in strong RF and the cell-average KPI is still lower, the remaining gap is sample mix (cell edge and busy hour inside the average), which is a reporting question, not a cap.
