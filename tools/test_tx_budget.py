"""Checks for the transport budget calculator.

Locks the numbers quoted in docs/02 and docs/06 so a formula change cannot
silently drift away from the action plan.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import tx_budget as tb  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "tx_budget.py"


class FormulaTest(unittest.TestCase):
    def test_dddsu_downlink_share(self):
        dl, ul = tb.TDD_PATTERNS["DDDSU"]
        self.assertAlmostEqual(dl, (3 + 10 / 14) / 5, places=6)
        self.assertAlmostEqual(ul, (1 + 2 / 14) / 5, places=6)
        # Two symbols of the special slot are guard and carry neither direction.
        guard = (2 / 14) / 5
        self.assertAlmostEqual(dl + ul + guard, 1.0, places=6)

    def test_single_cell_matches_ts38306_then_tdd(self):
        dl, ul = tb.NrCarrier().peak_mbps()
        # 100 MHz, 30 kHz, 273 PRB, 4 layers, 256QAM, OH 0.14, no TDD split.
        mu = 1
        symbol = 1e-3 / (14 * 2**mu)
        full = 273 * 12 / symbol * 8 * tb.R_MAX * 4 * (1 - tb.OH_FR1_DL) / 1e6
        self.assertAlmostEqual(full, 2337.0, delta=1.0)
        self.assertAlmostEqual(dl, full * tb.TDD_PATTERNS["DDDSU"][0], delta=0.5)
        # Quoted figure in the docs.
        self.assertAlmostEqual(dl, 1736.1, delta=1.0)
        self.assertGreater(ul, 250)
        self.assertLess(ul, 320)

    def test_fdd_pattern_returns_the_unsplit_peak(self):
        split = tb.NrCarrier(tdd_pattern="DDDSU").peak_mbps()[0]
        full = tb.NrCarrier(tdd_pattern="FDD").peak_mbps()[0]
        self.assertGreater(full, split)
        self.assertAlmostEqual(full, 2337.0, delta=1.0)

    def test_encapsulation_expansion(self):
        plain = tb.Encapsulation()
        self.assertEqual(plain.bytes_total, 38 + 4 + 20 + 8 + 12)
        self.assertAlmostEqual(plain.expansion(1400), (1400 + 82) / 1400, places=4)

        ipsec = tb.Encapsulation(ipsec=73)
        self.assertGreater(ipsec.expansion(1400), plain.expansion(1400))
        # Small payloads cost far more, which is the point of the --payload flag.
        self.assertGreater(ipsec.expansion(256), ipsec.expansion(1400) * 1.3)

    def test_ge_port_cannot_carry_one_nr_cell(self):
        result = tb.preset_single_cell(ipsec=False).compute()
        verdict = result["verdict"]
        self.assertFalse(verdict["ge_port_sufficient"])
        self.assertTrue(verdict["ten_ge_port_sufficient"])
        self.assertLess(verdict["goodput_ceiling_on_ge_mbps"], 1000)
        self.assertGreater(result["transport_required_mbps"]["single_user_peak_dl"], 2000)

    def test_ipsec_raises_the_swapped_site_budget(self):
        off = tb.preset_swap_site(ipsec=False).compute()
        on = tb.preset_swap_site(ipsec=True).compute()
        self.assertGreater(
            on["transport_required_mbps"]["busy_hour_dl"],
            off["transport_required_mbps"]["busy_hour_dl"],
        )
        self.assertTrue(on["assumptions"]["ipsec_enabled"])
        self.assertGreater(on["radio_peak_mbps"]["nr_dl"], on["radio_peak_mbps"]["lte_dl"])

    def test_option3_x2_allowance_increases_requirement(self):
        site = tb.preset_single_cell(ipsec=False)
        base = site.compute()["verdict"]["driving_requirement_mbps"]
        site.x2u_share = 1.0
        option3 = site.compute()["verdict"]["driving_requirement_mbps"]
        self.assertGreater(option3, base)

    def test_unknown_pattern_and_bandwidth_are_rejected(self):
        with self.assertRaises(SystemExit):
            tb.NrCarrier(tdd_pattern="NO-SUCH").peak_mbps()
        with self.assertRaises(SystemExit):
            tb.NrCarrier(bandwidth_mhz=33).peak_mbps()

    def test_lte_estimate_is_in_a_sane_range(self):
        # 20 MHz, 2 layers, 64QAM FDD is the well-known ~150 Mbit/s LTE cell.
        dl, ul = tb.LteCarrier(modulation="64qam", ul_modulation="64qam").peak_mbps()
        self.assertAlmostEqual(dl, 150, delta=15)
        self.assertGreater(ul, 40)
        self.assertLess(ul, 90)


class CliTest(unittest.TestCase):
    def run_tool(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(TOOL), *args],
            check=False, capture_output=True, text=True,
        )

    def test_json_preset(self):
        done = self.run_tool("--preset", "single-cell", "--json")
        self.assertEqual(done.returncode, 0, done.stderr)
        payload = json.loads(done.stdout)
        self.assertIn("transport_required_mbps", payload)
        self.assertEqual(payload["verdict"]["recommended_port_mbps"], 10000)

    def test_custom_carriers(self):
        done = self.run_tool(
            "--nr", "100:30:4:2:256qam", "--nr-cells", "3",
            "--lte", "20:4:1:256qam", "--tdd", "DDDSU", "--ipsec",
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("TRANSPORT REQUIRED", done.stdout)

    def test_missing_input_fails(self):
        done = self.run_tool()
        self.assertNotEqual(done.returncode, 0)

    def test_bad_nr_spec_fails(self):
        done = self.run_tool("--nr", "100:30:4")
        self.assertNotEqual(done.returncode, 0)


if __name__ == "__main__":
    unittest.main()
