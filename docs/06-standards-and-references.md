# 6. Standards and References

What each cited document is used for. Version numbers move; the clause structure of these specs has
been stable across the releases that matter for a commercial NSA network. Check the clause against
the release your network was built to (Rel-15 for first NSA launches, Rel-16/17 for later EN-DC
additions).

## 6.1 3GPP — the behaviour is specified, so it is testable

| Document | Clause | Used for |
| --- | --- | --- |
| **TS 37.340** | EN-DC overall | Bearer options 3 / 3a / 3x, who terminates PDCP, what X2-U carries. Chapter 1. |
| **TS 36.300** | §20.1.1 | Flow control on a split bearer: the secondary node reports delivery status, the master node paces forwarding. The reason X2 latency cuts throughput with no packet loss. |
| **TS 36.425** | §5.4.2 | Downlink Data Delivery Status procedure. The actual X2-U feedback message. |
| **TS 38.323** | PDCP | SN length (12 vs 18 bit) and the reordering window. Why `len18bits` is the right choice for a high-rate split bearer. |
| **TS 38.306** | §4.1.2 | Peak data rate formula. Implemented in `tools/tx_budget.py`. |
| **TS 38.101-1** | Table 5.3.2-1 | PRB count per bandwidth and SCS (273 PRB for 100 MHz at 30 kHz). |
| **TS 38.214** | MCS tables | 256QAM requires the higher MCS table; a UE stuck on the 64QAM table will never reach the Ch.2 number. |
| **TS 38.213** / **TS 38.331** | TDD pattern | `tdd-UL-DL-ConfigurationCommon`. Pattern alignment across neighbours. |
| **TS 23.401** | §4.7.3 | APN-AMBR and UE-AMBR for NSA: where they are stored, who enforces them. |
| **TS 23.501** | §5.7.1.8, §5.7.2.6 | Session-AMBR and UE-AMBR for SA. |
| **TS 23.501** | Annex J | Link MTU with GTP-U and IPsec. The 142-byte overhead and the 1358-byte user packet on a 1500-byte transport MTU. |
| **TS 28.552** | §5.1.1.3.1 | NR average UE throughput: `ThpVol / ThpTime`, excluding the buffer-emptying slot. |
| **TS 32.425** | §4.4.7 | LTE equivalent of the same measurement. The basis of the Phase 0 formula comparison. |
| **TS 36.413** / **TS 36.423** | S1AP / X2AP | Where UE-AMBR and SgNB UE Aggregate Maximum Bit Rate are signalled. |
| **TS 29.281** | GTP-U | UDP port 2152, header length. Why a 5-tuple hash pins a bearer to one LAG member. |

## 6.2 ITU-T and IETF — the transport side

| Document | Used for |
| --- | --- |
| **ITU-T G.8275.1** | PTP profile for full timing support. Required when TDD phase sync is distributed over the packet network instead of per-site GNSS. |
| **ITU-T Y.1564** | Service activation test for an EVC: the way to prove a leased-line CIR, rather than trusting the contract. |
| **ITU-T Y.1731** | Ethernet delay and loss measurement. The `ETHDM` / `ETHLM` counters on the base station implement this. |
| **RFC 5357** (TWAMP) | Active loss/delay/jitter measurement. The `BSTWAMP` counters. |
| **RFC 2544** | Throughput benchmarking. Useful, but Y.1564 is the better acceptance test because it includes CIR, CBS, and latency together. |
| **RFC 1191 / RFC 8201** | Path MTU discovery for IPv4 and IPv6. Why ICMP fragmentation-needed and packet-too-big must pass. |
| **RFC 6438** | Flow label for ECMP/LAG in tunnels. Background for the polarisation problem; TEID hashing is the practical fix for GTP-U. |

## 6.3 Vendor and industry material used to ground the numbers

These are planning references, not standards. The numbers in Chapters 1 and 2 that come from them are
stated as such.

| Source | What it contributed |
| --- | --- |
| Huawei 3900/5900 base station product documentation (AAU5636w, AAU5339w class) | eCPRI ports at 10/25 Gbit/s, no CPRI cascading, ~20 km optical reach for the 2.6 GHz 32T/64T class. |
| Huawei site design guidance (5G site solution) | UMPTe/UMPTga: 2×FE/GE electrical + 2×FE/GE/10GE optical, ~10 Gbit/s transmission class. UMPTg: 25GE optical. Electrical backhaul is GE only; 10GE optical is the stated default for NR. |
| Huawei Node and gNodeBFunction performance counter references | Counter names in Chapters 3 and 5: `VS.FEGE.*`, `VS.IPPath.*`, `VS.RscGroup.*`, `VS.Gtpu.*`, `VS.BSTWAMP.*`, `VS.ETHDM.*`, `N.NsaDc.SgNB.*`, `N.PDCP.*.X2U.*`. Confirm against your release. |
| NGMN and operator x-haul planning summaries | Order-of-magnitude split between fronthaul (3×25 Gbit/s provisioned per 3-sector site) and backhaul (a few Gbit/s peak early, tens of Gbit/s as spectrum grows). |

## 6.4 How to reproduce the headline numbers

```bash
# 1736 Mbit/s DL / 286 Mbit/s UL air peak, ~2116 Mbit/s on the wire, for one cell
python3 tools/tx_budget.py --preset single-cell

# Full swapped site, IPsec on: busy hour ~5.2 Gbit/s, full buffer ~9.4 Gbit/s
python3 tools/tx_budget.py --preset swap-site --ipsec

# Machine-readable, for a design spreadsheet
python3 tools/tx_budget.py --preset swap-site --ipsec --json
```

The DL time share behind 1736 Mbit/s is the DDDSU pattern with the special slot counted as 10 DL
symbols out of 14:

```
DL share = (3 + 10/14) / 5 = 0.7429
1736 ≈ 2337 Mbit/s (TS 38.306, 100 MHz, 30 kHz, 4 layers, 256QAM, OH 0.14) × 0.7429
```

If your network uses a different pattern, change `--tdd` and quote that result instead. The tool
refuses an unknown pattern rather than silently guessing.
