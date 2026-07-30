import tempfile
import time
import unittest
from pathlib import Path

from monitoring.timelapse import SessionTimelapse, TimelapseSample


class TimelapseHourWindowTests(unittest.TestCase):
    def test_sparkline_covers_full_hour_width(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tl = SessionTimelapse(
                Path(tmp) / "tl.jsonl",
                sample_interval_s=1.0,
                max_samples=200,
                window_s=3600.0,
            )
            now = time.time()
            tl._started = now - 3600
            # Samples across the hour: low early, high late.
            for minutes, hps in ((50, 100_000), (30, 200_000), (10, 400_000), (0, 500_000)):
                ts = now - minutes * 60
                tl._samples.append(
                    TimelapseSample(
                        elapsed_s=int(ts - tl._started),
                        hps=hps,
                        vram_mib=0,
                        temp_c=0,
                        pending=0,
                        accepted=1,
                        network_ok=True,
                        wall_ts=ts,
                    )
                )

            spark = tl.sparkline(width=48, now=now)
            self.assertEqual(len(spark), 48)
            filled = [ch for ch in spark if ch != "·"]
            self.assertGreaterEqual(len(filled), 3)
            # Glyphs should vary with H/s (absolute scale from 0 → peak).
            self.assertGreater(len(set(filled)), 1)
            avg = tl.average_hps(now=now)
            self.assertGreater(avg, 100_000)
            self.assertLess(avg, 500_000)

    def test_sparkline_no_false_plateau_from_carry(self) -> None:
        """One sample must not paint the whole hour as a solid bar."""
        with tempfile.TemporaryDirectory() as tmp:
            tl = SessionTimelapse(
                Path(tmp) / "tl.jsonl",
                sample_interval_s=1.0,
                window_s=3600.0,
            )
            now = time.time()
            tl._started = now - 120
            tl._samples.append(
                TimelapseSample(
                    elapsed_s=100,
                    hps=300_000,
                    vram_mib=0,
                    temp_c=0,
                    pending=0,
                    accepted=0,
                    network_ok=True,
                    wall_ts=now - 5,
                )
            )
            spark = tl.sparkline(width=40, now=now)
            self.assertEqual(len(spark), 40)
            # Most of the line should be empty markers, not a solid wall.
            filled = sum(1 for ch in spark if ch not in ("·", " "))
            self.assertLess(filled, 12)

    def test_average_ignores_samples_older_than_hour(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tl = SessionTimelapse(
                Path(tmp) / "tl.jsonl",
                sample_interval_s=1.0,
                window_s=3600.0,
            )
            now = time.time()
            tl._samples.append(
                TimelapseSample(
                    elapsed_s=0,
                    hps=10_000,
                    vram_mib=0,
                    temp_c=0,
                    pending=0,
                    accepted=0,
                    network_ok=True,
                    wall_ts=now - 7200,
                )
            )
            tl._samples.append(
                TimelapseSample(
                    elapsed_s=0,
                    hps=200_000,
                    vram_mib=0,
                    temp_c=0,
                    pending=0,
                    accepted=0,
                    network_ok=True,
                    wall_ts=now - 60,
                )
            )
            self.assertAlmostEqual(tl.average_hps(now=now), 200_000.0)


if __name__ == "__main__":
    unittest.main()
