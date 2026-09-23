#!/usr/bin/env python3
"""Transport (Tx) budget calculator for a mixed LTE/NR cell site.

Answers the question the RAN vendor and the transmission team keep arguing about:
given the radio configuration actually deployed, how much *transport* capacity does
the site need, on the wire, including protocol expansion?

Two numbers matter and they are different:

  single-user peak   what one speed-testing UE can pull from one cell. This is the
                     number a "throughput vs baseline" KPI is compared against, so
                     the transport must carry it as an instantaneous burst.
  site busy hour     the aggregate across all cells after applying a concurrency
                     factor. This is what dimensioning reports normally quote, and
                     it is why an under-dimensioned site can look fine on average.

NR peak follows 3GPP TS 38.306 section 4.1.2, then the TDD time share is applied
(the spec formula deliberately leaves duplexing to the deployment). LTE peak uses a
resource-element model calibrated to the well-known 150 Mbit/s per 20 MHz 2-layer
64QAM figure, and is an estimate rather than a spec formula.

Usage:
    python3 tools/tx_budget.py --preset swap-site
    python3 tools/tx_budget.py --nr 100:30:4:2:256 --nr-cells 3 --tdd DDDSU --ipsec
    python3 tools/tx_budget.py --preset swap-site --json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field

# --- 3GPP constants -------------------------------------------------------------

R_MAX = 948 / 1024  # TS 38.214 max code rate

# TS 38.306 Table 4.1.2-2 overhead
OH_FR1_DL = 0.14
OH_FR1_UL = 0.08

# TS 38.101-1 Table 5.3.2-1, transmission bandwidth configuration N_RB (FR1)
PRB_TABLE: dict[int, dict[int, int]] = {
    15: {5: 25, 10: 52, 15: 79, 20: 106, 25: 133, 30: 160, 40: 216, 50: 270},
    30: {10: 24, 15: 38, 20: 51, 25: 65, 30: 78, 40: 106, 50: 133,
         60: 162, 70: 189, 80: 217, 90: 245, 100: 273},
    60: {10: 11, 15: 18, 20: 24, 25: 31, 30: 38, 40: 51, 50: 65,
         60: 79, 70: 93, 80: 107, 90: 121, 100: 135},
}

MOD_ORDER = {"qpsk": 2, "16qam": 4, "64qam": 6, "256qam": 8, "1024qam": 10}

# Duplex patterns: (downlink time share, uplink time share).
# A special slot/subframe is counted as 10 DL + 2 guard + 2 UL symbols out of 14.
# NR patterns are named by slot sequence; LTE TDD by its 3GPP UL/DL configuration.
TDD_PATTERNS: dict[str, tuple[float, float]] = {
    # NR (TS 38.213 / operator slot formats)
    "DDDSU": ((3 + 10 / 14) / 5, (1 + 2 / 14) / 5),
    "DDDSUDDSUU": ((5 + 20 / 14) / 10, (3 + 4 / 14) / 10),
    "DDDDDDDSUU": ((7 + 10 / 14) / 10, (2 + 2 / 14) / 10),
    "DSUUD": ((2 + 10 / 14) / 5, (2 + 2 / 14) / 5),
    # LTE TDD UL/DL configurations (TS 36.211 Table 4.2-2), special subframe 10:2:2
    "LTE_C1": ((4 + 20 / 14) / 10, (4 + 4 / 14) / 10),
    "LTE_C2": ((6 + 20 / 14) / 10, (2 + 4 / 14) / 10),
    "FDD": (1.0, 1.0),
}


# --- protocol overhead ----------------------------------------------------------


@dataclass
class Encapsulation:
    """Per-packet transport overhead added to a user-plane payload byte count."""

    ethernet: int = 38          # 14 header + 4 FCS + 7 preamble + 1 SFD + 12 IFG
    vlan_tags: int = 1          # 4 bytes each
    outer_ip: int = 20          # 40 for IPv6
    udp: int = 8
    gtpu: int = 12              # 8 minimum, 12 with sequence number / extensions
    ipsec: int = 0              # ~73 for ESP tunnel mode (AES-CBC + SHA, incl. padding)

    @property
    def bytes_total(self) -> int:
        return (self.ethernet + 4 * self.vlan_tags + self.outer_ip
                + self.udp + self.gtpu + self.ipsec)

    def expansion(self, payload: int) -> float:
        """Wire bytes per payload byte."""
        return (payload + self.bytes_total) / payload


# --- radio carriers -------------------------------------------------------------


@dataclass
class NrCarrier:
    bandwidth_mhz: int = 100
    scs_khz: int = 30
    dl_layers: int = 4
    ul_layers: int = 2
    modulation: str = "256qam"
    ul_modulation: str | None = None
    tdd_pattern: str = "DDDSU"

    def _prb(self) -> int:
        try:
            return PRB_TABLE[self.scs_khz][self.bandwidth_mhz]
        except KeyError as exc:
            raise SystemExit(
                f"No PRB entry for {self.bandwidth_mhz} MHz at {self.scs_khz} kHz SCS. "
                f"Supported: {sorted(PRB_TABLE[self.scs_khz]) if self.scs_khz in PRB_TABLE else sorted(PRB_TABLE)}"
            ) from exc

    def _re_per_second_per_layer(self) -> float:
        mu = {15: 0, 30: 1, 60: 2}[self.scs_khz]
        symbol_seconds = 1e-3 / (14 * 2**mu)
        return self._prb() * 12 / symbol_seconds

    def peak_mbps(self) -> tuple[float, float]:
        """(dl, ul) peak in Mbit/s, TDD time share applied."""
        if self.tdd_pattern not in TDD_PATTERNS:
            raise SystemExit(
                f"Unknown TDD pattern {self.tdd_pattern!r}. "
                f"Supported: {', '.join(TDD_PATTERNS)}"
            )
        dl_share, ul_share = TDD_PATTERNS[self.tdd_pattern]
        re_rate = self._re_per_second_per_layer()
        qm_dl = MOD_ORDER[self.modulation]
        qm_ul = MOD_ORDER[self.ul_modulation or self.modulation]

        dl = re_rate * qm_dl * R_MAX * self.dl_layers * (1 - OH_FR1_DL) * dl_share / 1e6
        ul = re_rate * qm_ul * R_MAX * self.ul_layers * (1 - OH_FR1_UL) * ul_share / 1e6
        return dl, ul

    def label(self) -> str:
        return (f"NR {self.bandwidth_mhz}MHz/{self.scs_khz}kHz {self.dl_layers}L DL "
                f"{self.ul_layers}L UL {self.modulation} {self.tdd_pattern}")


@dataclass
class LteCarrier:
    """Estimated LTE peak. Calibrated so 20 MHz / 2 layers / 64QAM = ~150 Mbit/s DL."""

    bandwidth_mhz: int = 20
    dl_layers: int = 2
    ul_layers: int = 1
    modulation: str = "256qam"
    ul_modulation: str = "64qam"
    tdd_pattern: str = "FDD"
    overhead: float = 0.19

    _PRB = {1.4: 6, 3: 15, 5: 25, 10: 50, 15: 75, 20: 100}

    def _re_per_second_per_layer(self) -> float:
        prb = self._PRB.get(self.bandwidth_mhz, int(self.bandwidth_mhz * 5))
        return prb * 12 * 14 * 1000  # 14 symbols per 1 ms subframe

    def peak_mbps(self) -> tuple[float, float]:
        dl_share, ul_share = TDD_PATTERNS[self.tdd_pattern]
        re_rate = self._re_per_second_per_layer()
        base = re_rate * R_MAX * (1 - self.overhead) / 1e6
        dl = base * MOD_ORDER[self.modulation] * self.dl_layers * dl_share
        ul = base * MOD_ORDER[self.ul_modulation] * self.ul_layers * ul_share
        return dl, ul

    def label(self) -> str:
        return (f"LTE {self.bandwidth_mhz}MHz {self.dl_layers}L DL {self.ul_layers}L UL "
                f"{self.modulation} {self.tdd_pattern}")


# --- site budget ----------------------------------------------------------------


@dataclass
class SiteBudget:
    nr_carriers: list[NrCarrier] = field(default_factory=list)
    lte_carriers: list[LteCarrier] = field(default_factory=list)
    encapsulation: Encapsulation = field(default_factory=Encapsulation)
    payload_bytes: int = 1400
    concurrency: float = 0.55      # share of aggregate radio peak assumed simultaneous
    x2u_share: float = 0.15        # extra X2-U load as a share of NR peak (EN-DC)
    oam_mbps: float = 2.0
    sync_mbps: float = 1.0
    control_plane_ratio: float = 0.01

    PORT_LADDER = [1000, 2500, 10000, 25000, 40000, 100000]

    def compute(self) -> dict:
        expansion = self.encapsulation.expansion(self.payload_bytes)

        nr = [(c.label(), *c.peak_mbps()) for c in self.nr_carriers]
        lte = [(c.label(), *c.peak_mbps()) for c in self.lte_carriers]

        nr_dl = sum(d for _, d, _ in nr)
        nr_ul = sum(u for _, _, u in nr)
        lte_dl = sum(d for _, d, _ in lte)
        lte_ul = sum(u for _, _, u in lte)

        # Worst single-user burst the transport must absorb: the largest single cell.
        best_nr_dl = max((d for _, d, _ in nr), default=0.0)
        best_nr_ul = max((u for _, _, u in nr), default=0.0)

        radio_dl = nr_dl + lte_dl
        radio_ul = nr_ul + lte_ul

        def to_wire(mbps: float) -> float:
            return mbps * expansion

        overhead_fixed = self.oam_mbps + self.sync_mbps
        cp = (radio_dl + radio_ul) * self.control_plane_ratio

        single_user_dl = to_wire(best_nr_dl) * (1 + self.x2u_share) + overhead_fixed
        single_user_ul = to_wire(best_nr_ul) * (1 + self.x2u_share) + overhead_fixed

        busy_dl = to_wire(radio_dl * self.concurrency) * (1 + self.x2u_share) + overhead_fixed + cp
        busy_ul = to_wire(radio_ul * self.concurrency) * (1 + self.x2u_share) + overhead_fixed + cp

        full_dl = to_wire(radio_dl) * (1 + self.x2u_share) + overhead_fixed + cp
        full_ul = to_wire(radio_ul) * (1 + self.x2u_share) + overhead_fixed + cp

        required = max(single_user_dl, busy_dl, single_user_ul, busy_ul)
        recommended = next((p for p in self.PORT_LADDER if p >= required * 1.3), None)

        return {
            "assumptions": {
                "payload_bytes": self.payload_bytes,
                "encapsulation_bytes": self.encapsulation.bytes_total,
                "wire_expansion_factor": round(expansion, 4),
                "wire_overhead_percent": round((expansion - 1) * 100, 2),
                "concurrency": self.concurrency,
                "x2u_share_of_nr_peak": self.x2u_share,
                "oam_mbps": self.oam_mbps,
                "sync_mbps": self.sync_mbps,
                "control_plane_ratio": self.control_plane_ratio,
                "ipsec_enabled": self.encapsulation.ipsec > 0,
            },
            "carriers": {
                "nr": [{"carrier": n, "dl_mbps": round(d, 1), "ul_mbps": round(u, 1)}
                       for n, d, u in nr],
                "lte": [{"carrier": n, "dl_mbps": round(d, 1), "ul_mbps": round(u, 1)}
                        for n, d, u in lte],
            },
            "radio_peak_mbps": {
                "nr_dl": round(nr_dl, 1), "nr_ul": round(nr_ul, 1),
                "lte_dl": round(lte_dl, 1), "lte_ul": round(lte_ul, 1),
                "total_dl": round(radio_dl, 1), "total_ul": round(radio_ul, 1),
                "best_single_nr_cell_dl": round(best_nr_dl, 1),
                "best_single_nr_cell_ul": round(best_nr_ul, 1),
            },
            "transport_required_mbps": {
                "single_user_peak_dl": round(single_user_dl, 1),
                "single_user_peak_ul": round(single_user_ul, 1),
                "busy_hour_dl": round(busy_dl, 1),
                "busy_hour_ul": round(busy_ul, 1),
                "all_cells_full_buffer_dl": round(full_dl, 1),
                "all_cells_full_buffer_ul": round(full_ul, 1),
            },
            "verdict": {
                "driving_requirement_mbps": round(required, 1),
                "recommended_port_mbps": recommended,
                "ge_port_sufficient": required <= 1000 * 0.95,
                "ten_ge_port_sufficient": required <= 10000 * 0.95,
                "goodput_ceiling_on_ge_mbps": round(1000 / expansion, 1),
                "goodput_ceiling_on_10ge_mbps": round(10000 / expansion, 1),
            },
        }


# --- presets --------------------------------------------------------------------


def preset_swap_site(ipsec: bool) -> SiteBudget:
    """3-sector 2.6 GHz TDD 32T NR + LTE FDD 4T + LTE TDD 32T, i.e. the swapped site."""
    enc = Encapsulation(ipsec=73 if ipsec else 0)
    return SiteBudget(
        nr_carriers=[NrCarrier() for _ in range(3)],
        lte_carriers=(
            [LteCarrier(bandwidth_mhz=20, dl_layers=4, ul_layers=1) for _ in range(3)]
            + [LteCarrier(bandwidth_mhz=20, dl_layers=4, ul_layers=1,
                          tdd_pattern="LTE_C2") for _ in range(3)]
        ),
        encapsulation=enc,
    )


def preset_nr_only(ipsec: bool) -> SiteBudget:
    """3-sector NR 100 MHz TDD only, no LTE on the same transport."""
    return SiteBudget(
        nr_carriers=[NrCarrier() for _ in range(3)],
        encapsulation=Encapsulation(ipsec=73 if ipsec else 0),
    )


def preset_single_cell(ipsec: bool) -> SiteBudget:
    """One NR 100 MHz TDD cell: the minimum to pass a single-UE peak test."""
    return SiteBudget(
        nr_carriers=[NrCarrier()],
        encapsulation=Encapsulation(ipsec=73 if ipsec else 0),
    )


PRESETS = {
    "swap-site": preset_swap_site,
    "nr-only": preset_nr_only,
    "single-cell": preset_single_cell,
}


# --- CLI ------------------------------------------------------------------------


def parse_nr(spec: str, tdd: str) -> NrCarrier:
    """bandwidth:scs:dl_layers:ul_layers:modulation, e.g. 100:30:4:2:256qam"""
    parts = spec.split(":")
    if len(parts) != 5:
        raise SystemExit(f"--nr expects bw:scs:dl_layers:ul_layers:modulation, got {spec!r}")
    bw, scs, dl, ul, mod = parts
    mod = mod.lower()
    if not mod.endswith("qam") and mod != "qpsk":
        mod += "qam"
    if mod not in MOD_ORDER:
        raise SystemExit(f"Unknown modulation {mod!r}. Supported: {', '.join(MOD_ORDER)}")
    return NrCarrier(int(bw), int(scs), int(dl), int(ul), mod, tdd_pattern=tdd)


def render(result: dict) -> str:
    out: list[str] = []
    a = result["assumptions"]
    out.append("=" * 78)
    out.append("TRANSPORT BUDGET FOR ONE CELL SITE")
    out.append("=" * 78)
    out.append("")
    out.append(f"Payload modelled           : {a['payload_bytes']} B user packet")
    out.append(f"Encapsulation overhead     : {a['encapsulation_bytes']} B/packet "
               f"(IPsec {'ON' if a['ipsec_enabled'] else 'OFF'})")
    out.append(f"Wire expansion             : x{a['wire_expansion_factor']} "
               f"({a['wire_overhead_percent']}% overhead)")
    out.append(f"Concurrency factor         : {a['concurrency']}")
    out.append(f"X2-U allowance (EN-DC)     : +{int(a['x2u_share_of_nr_peak'] * 100)}% of NR peak")
    out.append("")
    out.append("-" * 78)
    out.append("RADIO PEAK (air interface, PDCP level)")
    out.append("-" * 78)
    for group in ("nr", "lte"):
        for c in result["carriers"][group]:
            out.append(f"  {c['carrier']:<52} DL {c['dl_mbps']:>8.1f}  UL {c['ul_mbps']:>7.1f}")
    r = result["radio_peak_mbps"]
    out.append("")
    out.append(f"  {'NR total':<52} DL {r['nr_dl']:>8.1f}  UL {r['nr_ul']:>7.1f}")
    out.append(f"  {'LTE total':<52} DL {r['lte_dl']:>8.1f}  UL {r['lte_ul']:>7.1f}")
    out.append(f"  {'SITE total':<52} DL {r['total_dl']:>8.1f}  UL {r['total_ul']:>7.1f}")
    out.append(f"  {'Largest single NR cell (speed-test burst)':<52} "
               f"DL {r['best_single_nr_cell_dl']:>8.1f}  UL {r['best_single_nr_cell_ul']:>7.1f}")
    out.append("")
    out.append("-" * 78)
    out.append("TRANSPORT REQUIRED (on the wire, Mbit/s)")
    out.append("-" * 78)
    t = result["transport_required_mbps"]
    out.append(f"  Single-UE peak test        DL {t['single_user_peak_dl']:>9.1f}   "
               f"UL {t['single_user_peak_ul']:>8.1f}")
    out.append(f"  Busy hour (concurrency)    DL {t['busy_hour_dl']:>9.1f}   "
               f"UL {t['busy_hour_ul']:>8.1f}")
    out.append(f"  All cells full buffer      DL {t['all_cells_full_buffer_dl']:>9.1f}   "
               f"UL {t['all_cells_full_buffer_ul']:>8.1f}")
    out.append("")
    out.append("-" * 78)
    out.append("VERDICT")
    out.append("-" * 78)
    v = result["verdict"]
    out.append(f"  Driving requirement        : {v['driving_requirement_mbps']} Mbit/s")
    out.append(f"  Recommended port           : {v['recommended_port_mbps']} Mbit/s "
               f"(30% headroom)")
    out.append(f"  1GE port sufficient?       : {'YES' if v['ge_port_sufficient'] else 'NO'}")
    out.append(f"  10GE port sufficient?      : {'YES' if v['ten_ge_port_sufficient'] else 'NO'}")
    out.append(f"  Max user goodput on 1GE    : {v['goodput_ceiling_on_ge_mbps']} Mbit/s")
    out.append(f"  Max user goodput on 10GE   : {v['goodput_ceiling_on_10ge_mbps']} Mbit/s")
    out.append("")
    out.append("Note: NR peak per TS 38.306 s4.1.2 with the TDD time share applied. LTE peak is an")
    out.append("estimate. Compare these against measured p99 interface rates, never against 15-minute")
    out.append("averages -- a burst that saturates a port for 200 ms is invisible in a 15-minute mean.")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Transport budget calculator for a mixed LTE/NR cell site.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--preset", choices=sorted(PRESETS),
                   help="Use a predefined site configuration.")
    p.add_argument("--nr", action="append", default=[], metavar="BW:SCS:DLL:ULL:MOD",
                   help="Add an NR carrier, e.g. 100:30:4:2:256qam. Repeatable.")
    p.add_argument("--nr-cells", type=int, default=1,
                   help="Replicate each --nr carrier N times (sectors). Default 1.")
    p.add_argument("--lte", action="append", default=[], metavar="BW:DLL:ULL:MOD[:PATTERN]",
                   help="Add an LTE carrier, e.g. 20:4:1:256qam or 20:4:2:256qam:DDDSU.")
    p.add_argument("--tdd", default="DDDSU", choices=sorted(TDD_PATTERNS),
                   help="NR TDD pattern. Default DDDSU.")
    p.add_argument("--ipsec", action="store_true", help="Include ~73 B IPsec ESP overhead.")
    p.add_argument("--payload", type=int, default=1400, help="User payload bytes. Default 1400.")
    p.add_argument("--vlan-tags", type=int, default=1, help="Number of VLAN tags. Default 1.")
    p.add_argument("--concurrency", type=float, default=0.55,
                   help="Share of aggregate radio peak assumed simultaneous. Default 0.55.")
    p.add_argument("--x2u-share", type=float, default=0.15,
                   help="X2-U allowance as a share of NR peak. Default 0.15. Use 1.0 for Option 3.")
    p.add_argument("--json", action="store_true", help="Emit JSON instead of a report.")
    args = p.parse_args(argv)

    if args.preset:
        budget = PRESETS[args.preset](args.ipsec)
        budget.payload_bytes = args.payload
        budget.encapsulation.vlan_tags = args.vlan_tags
        budget.concurrency = args.concurrency
        budget.x2u_share = args.x2u_share
    else:
        if not args.nr and not args.lte:
            p.error("supply --preset, or at least one --nr / --lte carrier")
        enc = Encapsulation(vlan_tags=args.vlan_tags, ipsec=73 if args.ipsec else 0)
        nr: list[NrCarrier] = []
        for spec in args.nr:
            nr.extend(parse_nr(spec, args.tdd) for _ in range(max(1, args.nr_cells)))
        lte: list[LteCarrier] = []
        for spec in args.lte:
            f = spec.split(":")
            if len(f) not in (4, 5):
                raise SystemExit(f"--lte expects bw:dll:ull:mod[:pattern], got {spec!r}")
            mod = f[3].lower()
            mod = mod if mod in MOD_ORDER else mod + "qam"
            lte.append(LteCarrier(bandwidth_mhz=int(f[0]), dl_layers=int(f[1]),
                                  ul_layers=int(f[2]), modulation=mod,
                                  tdd_pattern=f[4] if len(f) == 5 else "FDD"))
        budget = SiteBudget(nr_carriers=nr, lte_carriers=lte, encapsulation=enc,
                            payload_bytes=args.payload, concurrency=args.concurrency,
                            x2u_share=args.x2u_share)

    result = budget.compute()
    print(json.dumps(result, indent=2) if args.json else render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
