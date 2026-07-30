"""VRAM ↔ CUDA batch sizing — mirrors native HashApiTuning.cpp.

Low-difficulty harvest: pack as many parallel lanes as the VRAM budget
allows (subject to max_lanes + min_batch_per_lane), then collapse toward
1 lane as difficulty rises back to the reference.
"""

from __future__ import annotations

from dataclasses import dataclass

# xen_cuda / HashApiTuning.cpp subtracts this from free memory before sizing.
CUDA_ENGINE_RESERVE_BYTES = 100 * 1024 * 1024
BYTES_PER_ATTEMPT_FACTOR = 1.001
# Driver + context memory not included in batch×difficulty estimate (see session logs).
DEFAULT_CUDA_RUNTIME_OVERHEAD_MIB = 2048
# Floor so each lane still does meaningful work (Argon2id batch efficiency).
DEFAULT_MIN_BATCH_PER_LANE = 2048
# Hard ceiling even if VRAM could pack more (DLL-copy / thread overhead).
DEFAULT_ABSOLUTE_MAX_LANES = 32


@dataclass(frozen=True)
class CudaVramPlan:
    """Batch choice tied to configured VRAM limits."""

    batch_size: int
    lanes: int
    batch_per_lane: int
    lane_reserve: int
    budget_bytes: int
    budget_mib: int
    batch_vram_bytes: int
    batch_vram_mib: int
    used_before_mib: int
    projected_used_mib: int
    projected_headroom_mib: int
    runtime_overhead_mib: int
    target_mib: int
    effective_target_mib: int
    vram_scale: float
    desktop_headroom_mib: int
    difficulty: int
    # Non-miner VRAM (Windows desktop / other apps) baked into projected_used.
    foreign_used_mib: int = 0

    def summary(self) -> str:
        lane_part = (
            f"lanes={self.lanes}×{self.batch_per_lane:,}"
            if self.lanes > 1
            else f"batch={self.batch_size:,}"
        )
        reserve = (
            f" reserve={self.lane_reserve}"
            if self.lane_reserve > 0 and self.lanes >= self.lane_reserve
            else ""
        )
        foreign = (
            f" desktop/other={self.foreign_used_mib:,}MiB"
            if self.foreign_used_mib > 0
            else ""
        )
        return (
            f"{lane_part}{reserve} "
            f"budget={self.budget_mib:,}MiB "
            f"batch_vram≈{self.batch_vram_mib:,}MiB "
            f"cuda_overhead={self.runtime_overhead_mib:,}MiB "
            f"{foreign} "
            f"projected_used={self.projected_used_mib:,}MiB "
            f"projected_free={self.projected_headroom_mib:,}MiB "
            f"(target≤{self.target_mib:,}MiB desktop≥{self.desktop_headroom_mib:,}MiB free)"
        )

    def within_limits(self) -> bool:
        return (
            self.projected_used_mib <= self.target_mib
            and self.projected_headroom_mib >= self.desktop_headroom_mib
        )

    def fills_budget(self, *, tolerance_mib: int = 2) -> bool:
        """True when batch VRAM uses the full configured cap (harvest push)."""
        return abs(self.batch_vram_mib - self.budget_mib) <= tolerance_mib


def bytes_per_attempt(difficulty: int) -> float:
    return float(difficulty) * 1024.0 * BYTES_PER_ATTEMPT_FACTOR


def vram_budget_bytes(
    total_bytes: int,
    free_bytes: int,
    *,
    target_mib: int,
    desktop_headroom_mib: int,
) -> int:
    """
    Bytes the next CUDA batch may consume while respecting:
    - total GPU usage stays at or below target_mib
    - at least desktop_headroom_mib remains free for the OS/console
    """
    used = max(0, total_bytes - free_bytes)
    target_b = target_mib * 1024 * 1024
    headroom_b = desktop_headroom_mib * 1024 * 1024
    under_target = max(0, target_b - used)
    under_headroom = max(0, free_bytes - headroom_b)
    return min(under_target, under_headroom)


def cuda_lane_count(
    difficulty: int,
    *,
    reference_difficulty: int,
    max_lanes: int,
    budget_bytes: int = 0,
    min_batch_per_lane: int = DEFAULT_MIN_BATCH_PER_LANE,
    pack_mode: str = "fill",
) -> int:
    """
    Spin up more lanes when difficulty drops below the reference.

    pack_mode:
      - \"boost\" — legacy: reference // difficulty (capped by max_lanes)
      - \"fill\"  — pack as many lanes as VRAM allows while each lane keeps
                  at least min_batch_per_lane attempts (better low-dif harvest)

    At reference_difficulty one lane fills the VRAM cap. Lower difficulty uses
    lighter per-attempt memory, so we split the same cap across more lanes
    (distinct key prefixes) instead of leaving VRAM idle.
    """
    if max_lanes <= 1 or reference_difficulty <= 0 or difficulty <= 0:
        return 1
    if difficulty >= reference_difficulty:
        return 1

    cap = max(1, min(int(max_lanes), DEFAULT_ABSOLUTE_MAX_LANES))
    mode = (pack_mode or "fill").strip().lower()
    min_bpl = max(1, int(min_batch_per_lane))

    # Legacy integer boost (still used as a floor in fill mode).
    boost = max(1, reference_difficulty // difficulty)

    if mode == "boost" or budget_bytes <= 0:
        return max(1, min(cap, boost))

    # How many attempts fit in the whole batch budget at this difficulty?
    dll_free_arg = int(budget_bytes) + CUDA_ENGINE_RESERVE_BYTES
    total_attempts = memory_limited_batch_size(dll_free_arg, difficulty)
    if total_attempts <= 0:
        return 1

    max_by_min_batch = max(1, total_attempts // min_bpl)
    # Prefer the denser pack, but never below the classic boost (keeps
    # mid-difficulty behaviour familiar) and never above cap.
    packed = max(boost, max_by_min_batch)
    return max(1, min(cap, packed))


def vram_cap_batch_budget_bytes(
    total_bytes: int,
    *,
    target_mib: int,
    desktop_headroom_mib: int,
    runtime_overhead_mib: int,
    foreign_used_mib: int = 0,
    safety_margin_mib: int = 0,
) -> tuple[int, int]:
    """
    Full batch-buffer budget from miner.ini caps + non-miner VRAM.

    ``foreign_used_mib`` is VRAM already used by Windows desktop, browsers,
    and other apps (display GPU daily-driver). Batch is sized so:

        foreign + runtime_overhead + batch  ≤  target
        free after                          ≥  desktop_headroom

    Live free is not required for the steady formula; foreign baseline is.
    """
    total_mib = total_bytes // (1024 * 1024)
    effective_target_mib = target_mib
    foreign = max(0, int(foreign_used_mib))
    margin = max(0, int(safety_margin_mib))
    overhead = max(0, int(runtime_overhead_mib)) + margin

    # Room under the TOTAL used target after desktop/other + CUDA overhead.
    cap_batch_mib = max(0, effective_target_mib - foreign - overhead)
    # Room while keeping configured free headroom for compositor/UI.
    headroom_limited_mib = max(
        0, total_mib - desktop_headroom_mib - foreign - overhead
    )
    allowed_mib = min(cap_batch_mib, headroom_limited_mib)
    return allowed_mib * 1024 * 1024, effective_target_mib


def estimate_foreign_vram_mib(
    *,
    used_mib: int,
    batch_vram_mib: int = 0,
    runtime_overhead_mib: int = 0,
    desktop_baseline_mib: int = 0,
) -> int:
    """
    Estimate non-miner VRAM from a live used reading.

    Prefer the higher of:
    - cold desktop baseline (captured before mining), and
    - used − (current batch + overhead) when a plan is active
    so Chrome/DWM growth during the session is not ignored.
    """
    used = max(0, int(used_mib))
    minerish = max(0, int(batch_vram_mib)) + max(0, int(runtime_overhead_mib))
    inferred = max(0, used - minerish)
    baseline = max(0, int(desktop_baseline_mib))
    return max(baseline, inferred)


def memory_limited_batch_size(
    free_vram_bytes: int,
    difficulty: int,
    *,
    reserve_bytes: int = CUDA_ENGINE_RESERVE_BYTES,
) -> int:
    """Same formula as hashapi::estimateCudaMemoryBatchLimit."""
    if difficulty <= 0 or free_vram_bytes <= reserve_bytes:
        return 0
    available = float(free_vram_bytes - reserve_bytes)
    per_attempt = bytes_per_attempt(difficulty)
    if per_attempt <= 0:
        return 0
    return int(available / per_attempt)


def recommended_batch_size(difficulty: int) -> int:
    """Same tiers as hashapi::recommendedCudaBatchSize."""
    if difficulty <= 1:
        return 2048
    if difficulty <= 8:
        return 4096
    if difficulty <= 64:
        return 3072
    return 0


def select_batch_size(
    budget_bytes: int,
    difficulty: int,
    *,
    explicit_max_batch: int = 0,
    fill_vram_cap: bool = True,
) -> int:
    """
    Pick batch size from a VRAM budget byte allowance.

    Pass budget_bytes + CUDA_ENGINE_RESERVE_BYTES to the native DLL if calling
    xen_cuda_select_batch_size directly — the DLL subtracts the reserve itself.

    When fill_vram_cap is True (default), use the full difficulty-scaled budget.
    """
    # Native code treats the argument as free_vram_bytes.
    dll_free_arg = budget_bytes + CUDA_ENGINE_RESERVE_BYTES
    memory_limit = memory_limited_batch_size(dll_free_arg, difficulty)
    if memory_limit <= 0:
        return 0

    if explicit_max_batch > 0:
        return min(memory_limit, explicit_max_batch)

    if not fill_vram_cap:
        tuned = recommended_batch_size(difficulty)
        if tuned > 0:
            return min(memory_limit, tuned)
    return memory_limit


def estimate_batch_vram_bytes(batch_size: int, difficulty: int) -> int:
    """Approximate batch footprint (matches MineUnit.cpp usedMemory estimate)."""
    if batch_size <= 0 or difficulty <= 0:
        return 0
    return int(batch_size * bytes_per_attempt(difficulty))


def _plan_projection(
    *,
    total_mib: int,
    lanes: int,
    batch_per_lane: int,
    difficulty: int,
    runtime_overhead_mib: int,
    foreign_used_mib: int = 0,
) -> tuple[int, int, int, int]:
    batch_vram_bytes = estimate_batch_vram_bytes(batch_per_lane, difficulty) * lanes
    batch_vram_mib = batch_vram_bytes // (1024 * 1024)
    projected_used_mib = (
        max(0, int(foreign_used_mib)) + batch_vram_mib + runtime_overhead_mib
    )
    projected_headroom_mib = max(0, total_mib - projected_used_mib)
    return batch_vram_bytes, batch_vram_mib, projected_used_mib, projected_headroom_mib


def clamp_plan_to_caps(plan: CudaVramPlan) -> CudaVramPlan:
    """
    Shrink batch/lanes until projected VRAM fits miner.ini caps.

    Prefers keeping lane count during harvest (lower difficulty) so parallel
    key-prefix search stays wide; trims per-lane batch first, then lanes.
    """
    if plan.within_limits():
        return plan

    total_mib = plan.projected_used_mib + plan.projected_headroom_mib
    lanes = plan.lanes
    batch_per_lane = plan.batch_per_lane

    for _ in range(10_000):
        batch_vram_bytes, batch_vram_mib, projected_used_mib, projected_headroom_mib = (
            _plan_projection(
                total_mib=total_mib,
                lanes=lanes,
                batch_per_lane=batch_per_lane,
                difficulty=plan.difficulty,
                runtime_overhead_mib=plan.runtime_overhead_mib,
                foreign_used_mib=plan.foreign_used_mib,
            )
        )
        if (
            projected_used_mib <= plan.target_mib
            and projected_headroom_mib >= plan.desktop_headroom_mib
        ):
            return CudaVramPlan(
                batch_size=batch_per_lane,
                lanes=lanes,
                batch_per_lane=batch_per_lane,
                lane_reserve=plan.lane_reserve,
                budget_bytes=plan.budget_bytes,
                budget_mib=plan.budget_mib,
                batch_vram_bytes=batch_vram_bytes,
                batch_vram_mib=batch_vram_mib,
                used_before_mib=plan.used_before_mib,
                projected_used_mib=projected_used_mib,
                projected_headroom_mib=projected_headroom_mib,
                runtime_overhead_mib=plan.runtime_overhead_mib,
                target_mib=plan.target_mib,
                effective_target_mib=plan.effective_target_mib,
                vram_scale=plan.vram_scale,
                desktop_headroom_mib=plan.desktop_headroom_mib,
                difficulty=plan.difficulty,
                foreign_used_mib=plan.foreign_used_mib,
            )

        if batch_per_lane > 1:
            batch_per_lane = max(1, int(batch_per_lane * 0.98))
            continue

        if lanes > 1:
            lanes -= 1
            per_lane_budget = max(1, plan.budget_bytes // lanes)
            batch_per_lane = select_batch_size(
                per_lane_budget,
                plan.difficulty,
                explicit_max_batch=0,
                fill_vram_cap=True,
            )
            continue

        break

    return plan


def apply_lane_cap(plan: CudaVramPlan, max_lanes: int) -> CudaVramPlan:
    """
    Force a plan down to at most max_lanes, redistributing batch into fewer lanes.

    Used for live thermal lane derate without discarding the VRAM budget.
    """
    cap = max(1, int(max_lanes))
    if plan.lanes <= cap or plan.lanes <= 1:
        return plan

    total_mib = plan.projected_used_mib + plan.projected_headroom_mib
    lanes = cap
    per_lane_budget = max(1, plan.budget_bytes // lanes)
    batch_per_lane = select_batch_size(
        per_lane_budget,
        plan.difficulty,
        explicit_max_batch=0,
        fill_vram_cap=True,
    )
    batch_vram_bytes, batch_vram_mib, projected_used_mib, projected_headroom_mib = (
        _plan_projection(
            total_mib=total_mib,
            lanes=lanes,
            batch_per_lane=batch_per_lane,
            difficulty=plan.difficulty,
            runtime_overhead_mib=plan.runtime_overhead_mib,
            foreign_used_mib=plan.foreign_used_mib,
        )
    )
    reduced = CudaVramPlan(
        batch_size=batch_per_lane,
        lanes=lanes,
        batch_per_lane=batch_per_lane,
        lane_reserve=plan.lane_reserve,
        budget_bytes=plan.budget_bytes,
        budget_mib=plan.budget_mib,
        batch_vram_bytes=batch_vram_bytes,
        batch_vram_mib=batch_vram_mib,
        used_before_mib=plan.used_before_mib,
        projected_used_mib=projected_used_mib,
        projected_headroom_mib=projected_headroom_mib,
        runtime_overhead_mib=plan.runtime_overhead_mib,
        target_mib=plan.target_mib,
        effective_target_mib=plan.effective_target_mib,
        vram_scale=plan.vram_scale,
        desktop_headroom_mib=plan.desktop_headroom_mib,
        difficulty=plan.difficulty,
        foreign_used_mib=plan.foreign_used_mib,
    )
    return clamp_plan_to_caps(reduced)


def plan_cuda_batch(
    total_bytes: int,
    free_bytes: int,
    *,
    target_mib: int,
    desktop_headroom_mib: int,
    difficulty: int,
    reference_difficulty: int,
    max_lanes: int = 4,
    lane_reserve: int = 1,
    explicit_batch: int = 0,
    explicit_max_batch: int = 0,
    runtime_overhead_mib: int = DEFAULT_CUDA_RUNTIME_OVERHEAD_MIB,
    min_batch_per_lane: int = DEFAULT_MIN_BATCH_PER_LANE,
    pack_mode: str = "fill",
    foreign_used_mib: int = 0,
    safety_margin_mib: int = 0,
) -> CudaVramPlan:
    """
    Size CUDA batch/lanes from miner.ini VRAM caps.

    When ``foreign_used_mib`` > 0 (desktop / background on a display GPU),
    projected total used = foreign + batch + overhead and is kept ≤ target.
    """
    total_mib = total_bytes // (1024 * 1024)
    used_before_mib = max(0, (total_bytes - free_bytes) // (1024 * 1024))
    foreign = max(0, int(foreign_used_mib))
    margin = max(0, int(safety_margin_mib))
    overhead = max(0, int(runtime_overhead_mib))
    budget_bytes, effective_target_mib = vram_cap_batch_budget_bytes(
        total_bytes,
        target_mib=target_mib,
        desktop_headroom_mib=desktop_headroom_mib,
        runtime_overhead_mib=overhead,
        foreign_used_mib=foreign,
        safety_margin_mib=margin,
    )
    budget_mib = budget_bytes // (1024 * 1024)
    lanes = cuda_lane_count(
        difficulty,
        reference_difficulty=reference_difficulty,
        max_lanes=max(1, max_lanes),
        budget_bytes=budget_bytes,
        min_batch_per_lane=min_batch_per_lane,
        pack_mode=pack_mode,
    )
    reserve = max(0, lane_reserve)
    per_lane_budget = max(1, budget_bytes // max(1, lanes))

    max_batch_per_lane = select_batch_size(
        per_lane_budget,
        difficulty,
        explicit_max_batch=explicit_max_batch,
        fill_vram_cap=True,
    )
    if max_batch_per_lane <= 0:
        batch_per_lane = 0
    elif explicit_batch > 0:
        batch_per_lane = min(explicit_batch, max_batch_per_lane)
    else:
        batch_per_lane = max_batch_per_lane

    batch_size = batch_per_lane
    batch_vram_bytes = estimate_batch_vram_bytes(batch_per_lane, difficulty) * max(1, lanes)
    batch_vram_mib = batch_vram_bytes // (1024 * 1024)
    # Integer lane split can leave a few MiB unused — grow per-lane batch
    # while staying inside the total budget (keeps harvest fill honest).
    if batch_per_lane > 0 and lanes > 0 and budget_bytes > 0:
        per_attempt = bytes_per_attempt(difficulty)
        if per_attempt > 0:
            max_total_attempts = int(budget_bytes / per_attempt)
            max_bpl = max_total_attempts // lanes
            if explicit_max_batch > 0:
                max_bpl = min(max_bpl, explicit_max_batch)
            if explicit_batch > 0:
                max_bpl = min(max_bpl, explicit_batch)
            if max_bpl > batch_per_lane:
                batch_per_lane = max_bpl
                batch_size = batch_per_lane
                batch_vram_bytes = estimate_batch_vram_bytes(batch_per_lane, difficulty) * lanes
                batch_vram_mib = batch_vram_bytes // (1024 * 1024)

    # Total card used once mining: desktop/other + CUDA overhead + batch.
    projected_used_mib = foreign + batch_vram_mib + overhead + margin
    projected_headroom_mib = max(0, total_mib - projected_used_mib)

    plan = CudaVramPlan(
        batch_size=batch_size,
        lanes=lanes,
        batch_per_lane=batch_per_lane,
        lane_reserve=reserve,
        budget_bytes=budget_bytes,
        budget_mib=budget_mib,
        batch_vram_bytes=batch_vram_bytes,
        batch_vram_mib=batch_vram_mib,
        used_before_mib=used_before_mib,
        projected_used_mib=projected_used_mib,
        projected_headroom_mib=projected_headroom_mib,
        runtime_overhead_mib=overhead + margin,
        target_mib=target_mib,
        effective_target_mib=effective_target_mib,
        vram_scale=1.0,
        desktop_headroom_mib=desktop_headroom_mib,
        difficulty=difficulty,
        foreign_used_mib=foreign,
    )
    return clamp_plan_to_caps(plan)
