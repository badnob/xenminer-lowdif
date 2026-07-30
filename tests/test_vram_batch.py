from __future__ import annotations

import unittest
from dataclasses import replace

from mining.vram_batch import (
    CUDA_ENGINE_RESERVE_BYTES,
    apply_lane_cap,
    clamp_plan_to_caps,
    cuda_lane_count,
    plan_cuda_batch,
    select_batch_size,
    vram_budget_bytes,
    vram_cap_batch_budget_bytes,
)

REF = 1100
MAX_LANES = 4
MAX_LANES_DENSE = 12


class VramBatchTests(unittest.TestCase):
    def test_budget_respects_target_and_desktop_headroom(self) -> None:
        total = 32607 * 1024 * 1024
        free = (32607 - 2864) * 1024 * 1024
        budget = vram_budget_bytes(
            total,
            free,
            target_mib=22528,
            desktop_headroom_mib=8192,
        )
        self.assertEqual(budget // (1024 * 1024), 19664)

    def test_plan_stays_within_configured_limits(self) -> None:
        total = 32607 * 1024 * 1024
        free = (32607 - 2864) * 1024 * 1024
        plan = plan_cuda_batch(
            total,
            free,
            target_mib=22528,
            desktop_headroom_mib=8192,
            difficulty=1100,
            reference_difficulty=REF,
            max_lanes=MAX_LANES,
            runtime_overhead_mib=2048,
        )
        self.assertGreater(plan.batch_per_lane, 0)
        self.assertEqual(plan.lanes, 1)
        self.assertLessEqual(plan.projected_used_mib, plan.target_mib)
        self.assertGreaterEqual(plan.projected_headroom_mib, plan.desktop_headroom_mib)

    def test_explicit_batch_is_clamped_to_budget(self) -> None:
        total = 32607 * 1024 * 1024
        free = (32607 - 2864) * 1024 * 1024
        plan = plan_cuda_batch(
            total,
            free,
            target_mib=22528,
            desktop_headroom_mib=8192,
            difficulty=1100,
            reference_difficulty=REF,
            max_lanes=MAX_LANES,
            explicit_batch=50000,
            runtime_overhead_mib=2048,
        )
        per_lane_budget = plan.budget_bytes
        max_batch = select_batch_size(per_lane_budget, 1100)
        self.assertEqual(plan.batch_per_lane, max_batch)
        self.assertLess(plan.batch_per_lane, 50000)

    def test_cap_budget_steady_without_foreign(self) -> None:
        total = 32607 * 1024 * 1024
        cold = vram_cap_batch_budget_bytes(
            total,
            target_mib=22528,
            desktop_headroom_mib=8192,
            runtime_overhead_mib=2048,
            foreign_used_mib=0,
        )
        hot = vram_cap_batch_budget_bytes(
            total,
            target_mib=22528,
            desktop_headroom_mib=8192,
            runtime_overhead_mib=2048,
            foreign_used_mib=0,
        )
        self.assertEqual(cold, hot)
        self.assertEqual(cold[0] // (1024 * 1024), 20480)

    def test_desktop_foreign_vram_reduces_batch_budget(self) -> None:
        total = 32607 * 1024 * 1024
        none = vram_cap_batch_budget_bytes(
            total,
            target_mib=24576,
            desktop_headroom_mib=4096,
            runtime_overhead_mib=2048,
            foreign_used_mib=0,
            safety_margin_mib=512,
        )
        desk = vram_cap_batch_budget_bytes(
            total,
            target_mib=24576,
            desktop_headroom_mib=4096,
            runtime_overhead_mib=2048,
            foreign_used_mib=4096,
            safety_margin_mib=512,
        )
        self.assertLess(desk[0], none[0])
        # foreign 4096 + oh 2048 + margin 512 = 6656 → batch ≤ 24576-6656
        self.assertEqual(desk[0] // (1024 * 1024), 24576 - 4096 - 2048 - 512)

    def test_plan_with_desktop_stays_under_total_target(self) -> None:
        total = 32607 * 1024 * 1024
        # 4 GiB already used by desktop before mining
        free = (32607 - 4096) * 1024 * 1024
        plan = plan_cuda_batch(
            total,
            free,
            target_mib=24576,
            desktop_headroom_mib=4096,
            difficulty=1100,
            reference_difficulty=REF,
            max_lanes=MAX_LANES,
            runtime_overhead_mib=2048,
            foreign_used_mib=4096,
            safety_margin_mib=512,
        )
        self.assertGreater(plan.batch_per_lane, 0)
        self.assertLessEqual(plan.projected_used_mib, plan.target_mib)
        self.assertEqual(plan.foreign_used_mib, 4096)
        # projected includes desktop
        self.assertGreaterEqual(
            plan.projected_used_mib,
            plan.batch_vram_mib + plan.foreign_used_mib,
        )

    def test_low_difficulty_spins_up_lanes_and_fills_cap(self) -> None:
        total = 32607 * 1024 * 1024
        free = (32607 - 2864) * 1024 * 1024
        plan_100 = plan_cuda_batch(
            total,
            free,
            target_mib=22528,
            desktop_headroom_mib=8192,
            difficulty=100,
            reference_difficulty=REF,
            max_lanes=MAX_LANES,
            runtime_overhead_mib=2048,
            pack_mode="boost",
        )
        plan_1100 = plan_cuda_batch(
            total,
            free,
            target_mib=22528,
            desktop_headroom_mib=8192,
            difficulty=1100,
            reference_difficulty=REF,
            max_lanes=MAX_LANES,
            runtime_overhead_mib=2048,
        )
        self.assertEqual(plan_100.lanes, 4)
        self.assertEqual(plan_1100.lanes, 1)
        self.assertGreater(plan_100.batch_per_lane, plan_1100.batch_per_lane)
        self.assertLessEqual(
            abs(plan_100.batch_vram_mib - plan_1100.batch_vram_mib),
            2,
        )
        self.assertLessEqual(plan_100.projected_used_mib, plan_100.target_mib)
        self.assertLessEqual(plan_1100.projected_used_mib, plan_1100.target_mib)

    def test_lane_count_crosses_from_one_to_max(self) -> None:
        self.assertEqual(
            cuda_lane_count(1100, reference_difficulty=REF, max_lanes=MAX_LANES),
            1,
        )
        self.assertEqual(
            cuda_lane_count(
                100, reference_difficulty=REF, max_lanes=MAX_LANES, pack_mode="boost"
            ),
            4,
        )
        self.assertEqual(
            cuda_lane_count(
                550, reference_difficulty=REF, max_lanes=MAX_LANES, pack_mode="boost"
            ),
            2,
        )

    def test_fill_mode_packs_more_lanes_at_low_difficulty(self) -> None:
        total = 32607 * 1024 * 1024
        free = (32607 - 2864) * 1024 * 1024
        plan = plan_cuda_batch(
            total,
            free,
            target_mib=22528,
            desktop_headroom_mib=8192,
            difficulty=100,
            reference_difficulty=REF,
            max_lanes=MAX_LANES_DENSE,
            runtime_overhead_mib=2048,
            min_batch_per_lane=2048,
            pack_mode="fill",
        )
        # boost would only give 11; fill packs more up to max_lanes while
        # keeping min_batch_per_lane.
        self.assertGreaterEqual(plan.lanes, 8)
        self.assertLessEqual(plan.lanes, MAX_LANES_DENSE)
        self.assertGreaterEqual(plan.batch_per_lane, 2048)
        self.assertTrue(plan.within_limits())
        self.assertTrue(plan.fills_budget())

    def test_apply_lane_cap_redistributes_batch(self) -> None:
        total = 32607 * 1024 * 1024
        free = (32607 - 2864) * 1024 * 1024
        plan = plan_cuda_batch(
            total,
            free,
            target_mib=22528,
            desktop_headroom_mib=8192,
            difficulty=100,
            reference_difficulty=REF,
            max_lanes=MAX_LANES_DENSE,
            runtime_overhead_mib=2048,
            pack_mode="fill",
        )
        self.assertGreater(plan.lanes, 2)
        reduced = apply_lane_cap(plan, 2)
        self.assertEqual(reduced.lanes, 2)
        self.assertTrue(reduced.within_limits())
        self.assertGreaterEqual(reduced.batch_per_lane, plan.batch_per_lane)

    def test_harvest_plan_fills_budget_within_caps(self) -> None:
        total = 32607 * 1024 * 1024
        free = (32607 - 2864) * 1024 * 1024
        plan = plan_cuda_batch(
            total,
            free,
            target_mib=22528,
            desktop_headroom_mib=8192,
            difficulty=100,
            reference_difficulty=REF,
            max_lanes=MAX_LANES,
            runtime_overhead_mib=2048,
            pack_mode="boost",
        )
        self.assertTrue(plan.within_limits())
        self.assertTrue(plan.fills_budget())
        self.assertEqual(plan.lanes, 4)

    def test_clamp_plan_shrinks_to_caps(self) -> None:
        total = 32607 * 1024 * 1024
        free = (32607 - 2864) * 1024 * 1024
        plan = plan_cuda_batch(
            total,
            free,
            target_mib=22528,
            desktop_headroom_mib=8192,
            difficulty=1100,
            reference_difficulty=REF,
            max_lanes=MAX_LANES,
            runtime_overhead_mib=2048,
        )
        over_batch = plan.batch_per_lane + 5000
        over_vram = plan.batch_vram_mib + 5000
        over = replace(
            plan,
            batch_per_lane=over_batch,
            batch_size=over_batch,
            batch_vram_mib=over_vram,
            batch_vram_bytes=over_vram * 1024 * 1024,
            projected_used_mib=over_vram + plan.runtime_overhead_mib,
            projected_headroom_mib=max(
                0,
                plan.projected_used_mib
                + plan.projected_headroom_mib
                - (over_vram + plan.runtime_overhead_mib),
            ),
        )
        self.assertFalse(over.within_limits())
        clamped = clamp_plan_to_caps(over)
        self.assertTrue(clamped.within_limits())
        self.assertLessEqual(clamped.batch_per_lane, over.batch_per_lane)

    def test_python_budget_matches_native_reserve_convention(self) -> None:
        budget = 19664 * 1024 * 1024
        batch = select_batch_size(budget, 1100)
        native_arg = budget + CUDA_ENGINE_RESERVE_BYTES
        from mining.vram_batch import memory_limited_batch_size

        self.assertEqual(batch, memory_limited_batch_size(native_arg, 1100))

    def test_sequential_low_dif_fills_vram_with_full_batch(self) -> None:
        """Sequential hashrate mode: 1 full-budget stream (not multi-lane overhead)."""
        total = 32607 * 1024 * 1024
        free = (32607 - 3000) * 1024 * 1024
        parallel = plan_cuda_batch(
            total,
            free,
            target_mib=24576,
            desktop_headroom_mib=4096,
            difficulty=100,
            reference_difficulty=REF,
            max_lanes=8,
            runtime_overhead_mib=2048,
            foreign_used_mib=3000,
            safety_margin_mib=512,
            pack_mode="fill",
            concurrent_vram_lanes=None,
        )
        sequential = plan_cuda_batch(
            total,
            free,
            target_mib=24576,
            desktop_headroom_mib=4096,
            difficulty=100,
            reference_difficulty=REF,
            max_lanes=8,
            runtime_overhead_mib=2048,
            foreign_used_mib=3000,
            safety_margin_mib=512,
            pack_mode="fill",
            concurrent_vram_lanes=1,
        )
        self.assertEqual(sequential.lanes, 1)
        self.assertEqual(sequential.effective_concurrent_vram_lanes(), 1)
        self.assertGreater(sequential.batch_per_lane, parallel.batch_per_lane)
        self.assertLessEqual(sequential.projected_used_mib, sequential.target_mib)
        self.assertTrue(sequential.fills_budget(tolerance_mib=64))
        self.assertGreater(sequential.batch_vram_mib, 15000)
        # Coverage mode keeps multi-prefix without concurrent VRAM.
        coverage = plan_cuda_batch(
            total,
            free,
            target_mib=24576,
            desktop_headroom_mib=4096,
            difficulty=100,
            reference_difficulty=REF,
            max_lanes=8,
            runtime_overhead_mib=2048,
            foreign_used_mib=3000,
            safety_margin_mib=512,
            pack_mode="coverage",
            concurrent_vram_lanes=1,
        )
        self.assertEqual(coverage.lanes, 8)
        self.assertEqual(coverage.effective_concurrent_vram_lanes(), 1)


if __name__ == "__main__":
    unittest.main()
