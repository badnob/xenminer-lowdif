import unittest
from unittest.mock import MagicMock

from core.models import GpuSnapshot
from efficiency.gpu_power import GpuPowerBooster


class GpuPowerBoosterTests(unittest.TestCase):
    def _snap(self, temp_c: int) -> GpuSnapshot:
        return GpuSnapshot(
            index=0,
            name="Test GPU",
            total_mib=32607,
            used_mib=9000,
            free_mib=23607,
            util_pct=90,
            power_w=350.0,
            temperature_c=temp_c,
        )

    def _booster(self, **kwargs) -> GpuPowerBooster:
        monitor = MagicMock()
        monitor.get_power_limits_mw.return_value = (330_000, 200_000, 600_000)
        monitor.set_power_limit_mw.return_value = True
        defaults = dict(
            target_pct=100,
            warn_temp_c=72,
            max_temp_c=75,
            windows_performance_mode=False,
            min_pct=75,
            difficulty_power_enabled=True,
            reference_difficulty=1100,
            full_derate_ratio=2.0,
        )
        defaults.update(kwargs)
        booster = GpuPowerBooster(monitor, **defaults)
        booster._monitor = monitor
        return booster

    def test_apply_boosts_toward_target_pct(self) -> None:
        booster = self._booster()
        monitor = booster._monitor
        self.assertTrue(booster.apply())
        monitor.set_power_limit_mw.assert_called_once_with(600_000)

    def test_apply_skips_when_already_at_target(self) -> None:
        booster = self._booster()
        monitor = booster._monitor
        monitor.get_power_limits_mw.return_value = (600_000, 200_000, 600_000)
        self.assertFalse(booster.apply())
        monitor.set_power_limit_mw.assert_not_called()

    def test_adjust_steps_down_near_warn_temp(self) -> None:
        booster = self._booster()
        monitor = booster._monitor
        booster.apply()
        monitor.set_power_limit_mw.reset_mock()

        booster.adjust(self._snap(71))
        self.assertTrue(monitor.set_power_limit_mw.called)
        new_limit = monitor.set_power_limit_mw.call_args.args[0]
        self.assertLess(new_limit, 600_000)

    def test_restore_puts_back_original_limit(self) -> None:
        booster = self._booster()
        monitor = booster._monitor
        booster.apply()
        monitor.set_power_limit_mw.reset_mock()

        booster.restore()
        monitor.set_power_limit_mw.assert_called_once_with(330_000)

    def test_set_difficulty_lowers_target_within_range(self) -> None:
        booster = self._booster()
        self.assertEqual(booster.effective_target_pct, 100)
        pct = booster.set_difficulty(2200)
        self.assertEqual(pct, 75)
        self.assertEqual(booster.effective_target_pct, 75)
        # Mid difficulty stays between min and max
        pct = booster.set_difficulty(1650)
        self.assertGreaterEqual(pct, 75)
        self.assertLessEqual(pct, 100)
        self.assertEqual(pct, 88)

    def test_adjust_tracks_difficulty_target_when_cool(self) -> None:
        booster = self._booster()
        monitor = booster._monitor
        booster.apply()
        # At full power 600W; raise difficulty to min target (75% → 500W)
        booster.set_difficulty(2200)
        monitor.set_power_limit_mw.reset_mock()
        # Cool enough to allow mid-band / cool tracking toward lower target
        booster.adjust(self._snap(60))
        self.assertTrue(monitor.set_power_limit_mw.called)
        new_limit = monitor.set_power_limit_mw.call_args.args[0]
        self.assertLess(new_limit, 600_000)
        # 75% of span: 200 + 0.75*400 = 500W
        self.assertGreaterEqual(new_limit, 500_000)

    def test_adjust_never_below_min_pct_floor(self) -> None:
        booster = self._booster(min_pct=75)
        monitor = booster._monitor
        booster.apply()
        booster.set_difficulty(2200)
        # Force current high, then hammer with warn temps
        booster._current_limit_mw = 600_000
        for _ in range(40):
            booster.adjust(self._snap(74))
        floor_mw = 200_000 + int((600_000 - 200_000) * 75 / 100)
        self.assertGreaterEqual(booster._current_limit_mw, floor_mw)


if __name__ == "__main__":
    unittest.main()
