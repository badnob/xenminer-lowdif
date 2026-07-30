from __future__ import annotations

from dataclasses import dataclass

from core.models import GpuSnapshot
from efficiency.thermal_policy import (
    effective_control_temp_c,
    thermal_batch_scale,
    thermal_lane_cap,
)


@dataclass
class GuardAction:
    level: str  # ok | warn | emergency
    message: str
    code: str = "ok"
    should_stop_gpu: bool = False
    graceful_stop: bool = False
    cooldown_s: int = 0


@dataclass(frozen=True)
class DualTempEval:
    """Die vs board temperature evaluation (separate caps)."""

    level: str  # ok | warn | emergency
    code: str
    message: str
    die_c: int
    board_c: int
    hotspot_c: int
    # Effective values after optional high-diff proxy (board path).
    eff_die_c: int
    eff_board_c: int
    # For soft derate: most aggressive scale / lane cap pressure.
    batch_scale: float
    lane_cap_from_temp: int | None  # None = caller keeps planned
    abort: bool

    @property
    def summary(self) -> str:
        return (
            f"die {self.die_c}C (eff {self.eff_die_c}C) · "
            f"board {self.board_c or 'n/a'}C (eff {self.eff_board_c or 'n/a'}C) · "
            f"{self.level}"
        )


def _norm_limit(warn: int, hard: int) -> tuple[int, int]:
    hard = max(1, int(hard))
    warn = min(int(warn), hard - 1) if hard > 1 else int(warn)
    warn = max(1, warn)
    return warn, hard


def evaluate_die_board_temps(
    *,
    die_c: int,
    board_c: int,
    hotspot_c: int = 0,
    die_warn_c: int,
    die_max_c: int,
    board_warn_c: int,
    board_max_c: int,
    planned_lanes: int = 1,
    min_lanes: int = 1,
    batch_min_scale: float = 0.60,
    difficulty: int = 0,
    reference_difficulty: int = 1100,
    high_diff_enabled: bool = True,
    high_diff_start_ratio: float = 1.5,
    high_diff_full_ratio: float = 1.9,
    high_diff_max_tighten_c: int = 12,
) -> DualTempEval:
    """
    Separate die and board caps. Emergency if either hits its max.

    High-diff tighten applies only when board sensor is missing (proxy for
    board heat while die still looks cool). When board is readable, trust it.
    """
    die_warn, die_max = _norm_limit(die_warn_c, die_max_c)
    board_warn, board_max = _norm_limit(board_warn_c, board_max_c)

    die = max(0, int(die_c))
    board = max(0, int(board_c))
    hotspot = max(0, int(hotspot_c))

    # Die: use raw die (or hotspot if die missing and hotspot present as die-like).
    eff_die = die if die > 0 else (hotspot if hotspot > 0 else 0)

    # Board: real board if present; else control-like proxy from die/hotspot + hidiff.
    if board > 0:
        eff_board = board
    else:
        base = max(die, hotspot)
        if high_diff_enabled and base > 0 and difficulty > 0:
            eff_board = effective_control_temp_c(
                base,
                difficulty,
                reference_difficulty,
                start_ratio=high_diff_start_ratio,
                full_ratio=high_diff_full_ratio,
                max_tighten_c=high_diff_max_tighten_c,
            )
        else:
            eff_board = base

    # Soft derate: more aggressive of die-scale and board-scale.
    die_scale = (
        thermal_batch_scale(eff_die, die_warn, die_max, min_scale=batch_min_scale)
        if eff_die > 0
        else 1.0
    )
    board_scale = (
        thermal_batch_scale(eff_board, board_warn, board_max, min_scale=batch_min_scale)
        if eff_board > 0
        else 1.0
    )
    batch_scale = min(die_scale, board_scale)

    lane_from_die = (
        thermal_lane_cap(planned_lanes, eff_die, die_warn, die_max, min_lanes=min_lanes)
        if eff_die > 0 and planned_lanes > 1
        else planned_lanes
    )
    lane_from_board = (
        thermal_lane_cap(
            planned_lanes, eff_board, board_warn, board_max, min_lanes=min_lanes
        )
        if eff_board > 0 and planned_lanes > 1
        else planned_lanes
    )
    lane_cap = min(lane_from_die, lane_from_board)

    # Hard limits
    reasons: list[str] = []
    level = "ok"
    code = "ok"
    abort = False

    if eff_die > 0 and eff_die >= die_max:
        level = "emergency"
        code = "die_temp_emergency"
        abort = True
        reasons.append(f"die {eff_die}C >= max {die_max}C")
    if eff_board > 0 and eff_board >= board_max:
        level = "emergency"
        code = "board_temp_emergency" if code == "ok" else "temp_emergency"
        abort = True
        reasons.append(f"board {eff_board}C >= max {board_max}C")

    if level != "emergency":
        if eff_die > 0 and eff_die >= die_warn:
            level = "warn"
            code = "die_temp_warn"
            reasons.append(f"die {eff_die}C >= warn {die_warn}C")
        if eff_board > 0 and eff_board >= board_warn:
            level = "warn"
            code = "board_temp_warn" if code == "ok" else code
            reasons.append(f"board {eff_board}C >= warn {board_warn}C")

    detail = (
        f"die={die or 'n/a'}C board={board or 'n/a'}C "
        f"hotspot={hotspot or 'n/a'}C"
    )
    if not reasons:
        message = f"Temps OK ({detail})"
    else:
        message = f"{'; '.join(reasons)} ({detail})"

    return DualTempEval(
        level=level,
        code=code,
        message=message,
        die_c=die,
        board_c=board,
        hotspot_c=hotspot,
        eff_die_c=eff_die,
        eff_board_c=eff_board,
        batch_scale=batch_scale,
        lane_cap_from_temp=lane_cap if planned_lanes > 1 else None,
        abort=abort,
    )


def evaluate_snapshot_temps(
    snap: GpuSnapshot | None,
    *,
    die_warn_c: int,
    die_max_c: int,
    board_warn_c: int,
    board_max_c: int,
    planned_lanes: int = 1,
    min_lanes: int = 1,
    batch_min_scale: float = 0.60,
    difficulty: int = 0,
    reference_difficulty: int = 1100,
    high_diff_enabled: bool = True,
    high_diff_start_ratio: float = 1.5,
    high_diff_full_ratio: float = 1.9,
    high_diff_max_tighten_c: int = 12,
) -> DualTempEval | None:
    if snap is None:
        return None
    die = int(getattr(snap, "gpu_temp_c", 0) or 0)
    if die <= 0:
        # Fallback: temperature_c may be die-only on old snapshots
        if (getattr(snap, "temp_source", "") or "gpu") in ("gpu", "die", ""):
            die = int(snap.temperature_c or 0)
    board = int(getattr(snap, "board_temp_c", 0) or 0)
    hotspot = int(getattr(snap, "hotspot_temp_c", 0) or 0)
    return evaluate_die_board_temps(
        die_c=die,
        board_c=board,
        hotspot_c=hotspot,
        die_warn_c=die_warn_c,
        die_max_c=die_max_c,
        board_warn_c=board_warn_c,
        board_max_c=board_max_c,
        planned_lanes=planned_lanes,
        min_lanes=min_lanes,
        batch_min_scale=batch_min_scale,
        difficulty=difficulty,
        reference_difficulty=reference_difficulty,
        high_diff_enabled=high_diff_enabled,
        high_diff_start_ratio=high_diff_start_ratio,
        high_diff_full_ratio=high_diff_full_ratio,
        high_diff_max_tighten_c=high_diff_max_tighten_c,
    )


class VramGuard:
    """Hardware safety: emergency stop before CUDA OOM + dual temp caps."""

    def __init__(
        self,
        target_vram_mib: int,
        desktop_headroom_mib: int,
        emergency_vram_mib: int,
        min_headroom_mib: int,
        max_temp_c: int,
        warn_temp_c: int,
        cooldown_s: int,
        *,
        max_board_temp_c: int | None = None,
        warn_board_temp_c: int | None = None,
    ) -> None:
        self.target_vram_mib = target_vram_mib
        self.desktop_headroom_mib = desktop_headroom_mib
        self.emergency_vram_mib = emergency_vram_mib
        self.min_headroom_mib = min_headroom_mib
        self.max_temp_c = max_temp_c
        self.warn_temp_c = min(warn_temp_c, max_temp_c - 1) if max_temp_c > 1 else warn_temp_c
        # Board defaults loftier than die (Tony: board cruise ~88, cap 90).
        bmax = int(max_board_temp_c) if max_board_temp_c is not None else max(90, max_temp_c)
        bwarn = int(warn_board_temp_c) if warn_board_temp_c is not None else min(85, bmax - 1)
        self.max_board_temp_c, self.warn_board_temp_c = bmax, min(bwarn, bmax - 1)
        self.cooldown_s = cooldown_s
        # Optional context for high-diff board proxy when board sensor missing.
        self.difficulty = 0
        self.reference_difficulty = 1100
        self.high_diff_enabled = True
        self.high_diff_start_ratio = 1.5
        self.high_diff_full_ratio = 1.9
        self.high_diff_max_tighten_c = 12

    def set_difficulty_context(
        self,
        difficulty: int,
        *,
        reference_difficulty: int = 1100,
        high_diff_enabled: bool = True,
        start_ratio: float = 1.5,
        full_ratio: float = 1.9,
        max_tighten_c: int = 12,
    ) -> None:
        self.difficulty = max(0, int(difficulty))
        self.reference_difficulty = max(1, int(reference_difficulty))
        self.high_diff_enabled = bool(high_diff_enabled)
        self.high_diff_start_ratio = float(start_ratio)
        self.high_diff_full_ratio = float(full_ratio)
        self.high_diff_max_tighten_c = int(max_tighten_c)

    def evaluate(self, snap: GpuSnapshot | None) -> GuardAction:
        if snap is None:
            return GuardAction("ok", "GPU metrics unavailable")

        emergency_limit = min(self.emergency_vram_mib, max(snap.total_mib - 256, 0))
        if snap.used_mib >= emergency_limit:
            return GuardAction(
                "emergency",
                f"VRAM emergency: {snap.used_mib}MiB >= {emergency_limit}MiB",
                code="vram_emergency",
                should_stop_gpu=True,
                cooldown_s=self.cooldown_s,
            )

        if snap.headroom_mib <= self.min_headroom_mib:
            return GuardAction(
                "emergency",
                f"Headroom critical: {snap.headroom_mib}MiB <= {self.min_headroom_mib}MiB",
                code="headroom_critical",
                should_stop_gpu=True,
                cooldown_s=self.cooldown_s,
            )

        tev = evaluate_snapshot_temps(
            snap,
            die_warn_c=self.warn_temp_c,
            die_max_c=self.max_temp_c,
            board_warn_c=self.warn_board_temp_c,
            board_max_c=self.max_board_temp_c,
            difficulty=self.difficulty,
            reference_difficulty=self.reference_difficulty,
            high_diff_enabled=self.high_diff_enabled,
            high_diff_start_ratio=self.high_diff_start_ratio,
            high_diff_full_ratio=self.high_diff_full_ratio,
            high_diff_max_tighten_c=self.high_diff_max_tighten_c,
        )
        if tev is not None and tev.level == "emergency":
            return GuardAction(
                "emergency",
                tev.message,
                code=tev.code,
                should_stop_gpu=True,
                graceful_stop=True,
                cooldown_s=self.cooldown_s,
            )
        if tev is not None and tev.level == "warn":
            return GuardAction("warn", tev.message, code=tev.code)

        if snap.headroom_mib < self.desktop_headroom_mib:
            return GuardAction(
                "warn",
                f"Desktop VRAM low: {snap.headroom_mib}MiB free "
                f"(need {self.desktop_headroom_mib}MiB for console/desktop)",
                code="desktop_vram_low",
            )

        return GuardAction(
            "ok",
            f"VRAM {snap.used_mib}MiB headroom {snap.headroom_mib}MiB",
            code="ok",
        )
