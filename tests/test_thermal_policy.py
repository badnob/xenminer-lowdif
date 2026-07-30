import unittest

from efficiency.thermal_policy import (
    apply_batch_scale,
    difficulty_lane_bias,
    difficulty_power_target_pct,
    normalize_power_range,
    thermal_batch_scale,
    thermal_lane_cap,
)


class ThermalPolicyTests(unittest.TestCase):
    def test_normalize_power_range_keeps_min_le_target(self) -> None:
        target, floor = normalize_power_range(100, 75)
        self.assertEqual(target, 100)
        self.assertEqual(floor, 75)
        target, floor = normalize_power_range(70, 90)
        self.assertEqual(target, 70)
        self.assertEqual(floor, 70)
        target, floor = normalize_power_range(120, 40)
        self.assertEqual(target, 100)
        self.assertEqual(floor, 50)

    def test_difficulty_power_at_and_below_reference(self) -> None:
        self.assertEqual(
            difficulty_power_target_pct(100, 1100, 1100, min_pct=75),
            100,
        )
        self.assertEqual(
            difficulty_power_target_pct(100, 500, 1100, min_pct=75),
            100,
        )

    def test_difficulty_power_full_derate_at_ratio(self) -> None:
        # 2× reference → min_pct
        self.assertEqual(
            difficulty_power_target_pct(100, 2200, 1100, min_pct=75, full_derate_ratio=2.0),
            75,
        )
        # Beyond 2× stays at min
        self.assertEqual(
            difficulty_power_target_pct(100, 3000, 1100, min_pct=75, full_derate_ratio=2.0),
            75,
        )

    def test_difficulty_power_midpoint(self) -> None:
        # Halfway from ref to 2× → midpoint of 100 and 75
        mid = difficulty_power_target_pct(
            100, 1650, 1100, min_pct=75, full_derate_ratio=2.0
        )
        self.assertEqual(mid, 88)

    def test_difficulty_power_stays_in_band(self) -> None:
        for diff in (800, 1100, 1400, 1800, 2200, 4000):
            pct = difficulty_power_target_pct(100, diff, 1100, min_pct=75)
            self.assertGreaterEqual(pct, 75)
            self.assertLessEqual(pct, 100)

    def test_thermal_batch_cool_is_full(self) -> None:
        self.assertEqual(thermal_batch_scale(60, 72, 75, min_scale=0.70), 1.0)
        # warn - 5 = 67; at or below → full
        self.assertEqual(thermal_batch_scale(67, 72, 75, min_scale=0.70), 1.0)

    def test_thermal_batch_at_max_is_floor(self) -> None:
        self.assertEqual(thermal_batch_scale(75, 72, 75, min_scale=0.70), 0.70)
        self.assertEqual(thermal_batch_scale(90, 72, 75, min_scale=0.70), 0.70)

    def test_thermal_batch_in_range(self) -> None:
        for temp in range(60, 80):
            scale = thermal_batch_scale(temp, 72, 75, min_scale=0.70)
            self.assertGreaterEqual(scale, 0.70)
            self.assertLessEqual(scale, 1.0)

    def test_thermal_batch_min_scale_clamped(self) -> None:
        # min_scale below 0.50 is raised to 0.50
        self.assertEqual(thermal_batch_scale(75, 72, 75, min_scale=0.2), 0.50)

    def test_apply_batch_scale(self) -> None:
        self.assertEqual(apply_batch_scale(1000, 0.70), 700)
        self.assertEqual(apply_batch_scale(1, 0.70), 1)
        self.assertEqual(apply_batch_scale(0, 0.70), 0)

    def test_thermal_lane_cap_cool_keeps_all(self) -> None:
        self.assertEqual(thermal_lane_cap(12, 55, 68, 72), 12)
        self.assertEqual(thermal_lane_cap(12, 60, 68, 72), 12)

    def test_thermal_lane_cap_at_max_is_min(self) -> None:
        self.assertEqual(thermal_lane_cap(12, 72, 68, 72, min_lanes=1), 1)
        self.assertEqual(thermal_lane_cap(12, 80, 68, 72, min_lanes=2), 2)

    def test_thermal_lane_cap_shrinks_near_warn(self) -> None:
        cool = thermal_lane_cap(12, 60, 68, 72)
        warm = thermal_lane_cap(12, 67, 68, 72)
        hot = thermal_lane_cap(12, 70, 68, 72)
        self.assertEqual(cool, 12)
        self.assertLessEqual(warm, cool)
        self.assertLessEqual(hot, warm)
        self.assertGreaterEqual(hot, 1)

    def test_difficulty_lane_bias_full_pack_at_low_dif(self) -> None:
        self.assertEqual(
            difficulty_lane_bias(12, 100, 1100, full_pack_ratio=0.35),
            12,
        )

    def test_difficulty_lane_bias_collapses_near_reference(self) -> None:
        mid = difficulty_lane_bias(12, 700, 1100, full_pack_ratio=0.35)
        near = difficulty_lane_bias(12, 1000, 1100, full_pack_ratio=0.35)
        self.assertLess(mid, 12)
        self.assertLessEqual(near, mid)
        self.assertEqual(difficulty_lane_bias(12, 1100, 1100), 1)

    def test_high_diff_temp_tighten_at_2100(self) -> None:
        from efficiency.thermal_policy import (
            effective_control_temp_c,
            high_diff_temp_tighten_c,
            vram_pressure_lane_cap,
            vram_pressure_scale,
            combine_batch_scales,
        )

        # Below 1.5× ref → no tighten
        self.assertEqual(
            high_diff_temp_tighten_c(1100, 1100, start_ratio=1.5, full_ratio=1.9, max_tighten_c=12),
            0,
        )
        self.assertEqual(
            high_diff_temp_tighten_c(1650, 1100, start_ratio=1.5, full_ratio=1.9, max_tighten_c=12),
            0,
        )
        # At/above ~1.9× (2090) → full +12C proxy (board heat)
        self.assertEqual(
            high_diff_temp_tighten_c(2100, 1100, start_ratio=1.5, full_ratio=1.9, max_tighten_c=12),
            12,
        )
        # Die 68C at dif 2100 → policy 80C → trips max 72
        self.assertEqual(
            effective_control_temp_c(
                68, 2100, 1100, start_ratio=1.5, full_ratio=1.9, max_tighten_c=12
            ),
            80,
        )

    def test_vram_pressure_keeps_mining_scale(self) -> None:
        from efficiency.thermal_policy import (
            combine_batch_scales,
            vram_pressure_lane_cap,
            vram_pressure_scale,
        )

        self.assertEqual(vram_pressure_scale(20000, 24576, 30000), 1.0)
        mid = vram_pressure_scale(27000, 24576, 30000, min_scale=0.55)
        self.assertGreater(mid, 0.55)
        self.assertLess(mid, 1.0)
        self.assertEqual(
            vram_pressure_scale(30000, 24576, 30000, min_scale=0.55),
            0.55,
        )
        # Soft floor still mining — scale never 0
        self.assertGreaterEqual(
            vram_pressure_scale(40000, 24576, 30000, min_scale=0.55),
            0.55,
        )
        self.assertEqual(
            vram_pressure_lane_cap(4, 20000, 24576, 30000),
            4,
        )
        self.assertLessEqual(
            vram_pressure_lane_cap(4, 28000, 24576, 30000),
            4,
        )
        self.assertEqual(combine_batch_scales(1.0, 0.7, 0.9), 0.7)


if __name__ == "__main__":
    unittest.main()
