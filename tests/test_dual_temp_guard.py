import unittest

from core.models import GpuSnapshot
from efficiency.vram_guard import VramGuard, evaluate_die_board_temps


class DualTempGuardTests(unittest.TestCase):
    def test_board_90_emergency_die_cool(self) -> None:
        ev = evaluate_die_board_temps(
            die_c=70,
            board_c=90,
            die_warn_c=78,
            die_max_c=84,
            board_warn_c=85,
            board_max_c=90,
        )
        self.assertEqual(ev.level, "emergency")
        self.assertTrue(ev.abort)
        self.assertIn("board", ev.message)

    def test_board_88_warn_not_stop(self) -> None:
        ev = evaluate_die_board_temps(
            die_c=72,
            board_c=88,
            die_warn_c=78,
            die_max_c=84,
            board_warn_c=85,
            board_max_c=90,
        )
        self.assertEqual(ev.level, "warn")
        self.assertFalse(ev.abort)

    def test_die_max_trips_even_if_board_ok(self) -> None:
        ev = evaluate_die_board_temps(
            die_c=84,
            board_c=80,
            die_warn_c=78,
            die_max_c=84,
            board_warn_c=85,
            board_max_c=90,
        )
        self.assertEqual(ev.level, "emergency")
        self.assertTrue(ev.abort)

    def test_no_board_sensor_hidiff_proxy_at_2100(self) -> None:
        # die 68 + full hidiff +12 → board proxy 80 — board max 90 → not emergency
        # but board warn 85? 80 is warn? 80 < 85 so ok for board
        # die 68 < 78 → ok overall if no other
        ev = evaluate_die_board_temps(
            die_c=68,
            board_c=0,
            die_warn_c=78,
            die_max_c=84,
            board_warn_c=85,
            board_max_c=90,
            difficulty=2100,
            reference_difficulty=1100,
            high_diff_enabled=True,
            high_diff_start_ratio=1.5,
            high_diff_full_ratio=1.9,
            high_diff_max_tighten_c=12,
        )
        self.assertEqual(ev.eff_board_c, 80)
        self.assertEqual(ev.level, "ok")

        # die 78 with hidiff → board proxy 90 → emergency on board
        ev2 = evaluate_die_board_temps(
            die_c=78,
            board_c=0,
            die_warn_c=78,
            die_max_c=84,
            board_warn_c=85,
            board_max_c=90,
            difficulty=2100,
            reference_difficulty=1100,
            high_diff_enabled=True,
            high_diff_max_tighten_c=12,
        )
        self.assertEqual(ev2.eff_board_c, 90)
        self.assertEqual(ev2.level, "emergency")

    def test_real_board_ignores_hidiff_inflate(self) -> None:
        ev = evaluate_die_board_temps(
            die_c=68,
            board_c=88,
            die_warn_c=78,
            die_max_c=84,
            board_warn_c=85,
            board_max_c=90,
            difficulty=2100,
            high_diff_enabled=True,
            high_diff_max_tighten_c=12,
        )
        # Trust real board 88, do not add +12
        self.assertEqual(ev.eff_board_c, 88)
        self.assertEqual(ev.level, "warn")

    def test_guard_board_emergency(self) -> None:
        g = VramGuard(
            24000,
            7000,
            30000,
            512,
            max_temp_c=84,
            warn_temp_c=78,
            cooldown_s=60,
            max_board_temp_c=90,
            warn_board_temp_c=85,
        )
        snap = GpuSnapshot(
            0,
            "g",
            32000,
            10000,
            22000,
            99,
            400.0,
            temperature_c=90,
            gpu_temp_c=70,
            board_temp_c=90,
            temp_source="board",
        )
        act = g.evaluate(snap)
        self.assertEqual(act.level, "emergency")
        self.assertTrue(act.graceful_stop)


if __name__ == "__main__":
    unittest.main()
