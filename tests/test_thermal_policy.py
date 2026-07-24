import unittest

from efficiency.thermal_policy import (
    apply_batch_scale,
    difficulty_power_target_pct,
    normalize_power_range,
    thermal_batch_scale,
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


if __name__ == "__main__":
    unittest.main()
