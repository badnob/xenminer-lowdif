"""Automatic GPU power-limit boost via NVML (no Afterburner required)."""

from __future__ import annotations

import re
import subprocess
import sys

from core.models import GpuSnapshot
from efficiency.thermal_policy import (
    difficulty_power_target_pct,
    normalize_power_range,
)
from monitoring.logger import SessionLogger
from monitoring.nvidia import NvidiaMonitor

_HIGH_PERFORMANCE_GUID = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"


class GpuPowerBooster:
    """
    Raise the driver power cap toward the NVML maximum while temps stay
    below warn_gpu_temp_c, and ease off as the GPU approaches the cap.

    When difficulty-aware mode is enabled, the effective power target is
    lowered (within [min_pct, target_pct]) as difficulty rises above the
    VRAM reference difficulty.
    """

    def __init__(
        self,
        monitor: NvidiaMonitor,
        *,
        target_pct: int,
        warn_temp_c: int,
        max_temp_c: int,
        logger: SessionLogger | None = None,
        windows_performance_mode: bool = True,
        device_index: int = 0,
        min_pct: int = 75,
        difficulty_power_enabled: bool = True,
        reference_difficulty: int = 1100,
        full_derate_ratio: float = 2.0,
    ) -> None:
        self._monitor = monitor
        target, floor = normalize_power_range(target_pct, min_pct)
        self._target_pct = target
        self._min_pct = floor
        self._warn_temp_c = warn_temp_c
        self._max_temp_c = max_temp_c
        self._logger = logger
        self._windows_performance_mode = windows_performance_mode
        self._device_index = device_index
        self._difficulty_power_enabled = difficulty_power_enabled
        self._reference_difficulty = max(1, int(reference_difficulty))
        self._full_derate_ratio = max(1.01, float(full_derate_ratio))
        self._difficulty = self._reference_difficulty
        self._effective_target_pct = target
        self._original_limit_mw: int | None = None
        self._min_limit_mw = 0
        self._max_limit_mw = 0
        self._current_limit_mw: int | None = None
        self._applied = False
        self._saved_power_scheme: str | None = None

    def _log(self, level: str, msg: str) -> None:
        if self._logger is not None:
            getattr(self._logger, level)(msg)

    def _compute_effective_target_pct(self) -> int:
        if not self._difficulty_power_enabled:
            return self._target_pct
        return difficulty_power_target_pct(
            self._target_pct,
            self._difficulty,
            self._reference_difficulty,
            min_pct=self._min_pct,
            full_derate_ratio=self._full_derate_ratio,
        )

    def set_difficulty(self, difficulty: int) -> int:
        """
        Update network difficulty for power scaling.

        Returns the new effective target pct (may be unchanged).
        """
        self._difficulty = max(1, int(difficulty))
        new_pct = self._compute_effective_target_pct()
        if new_pct != self._effective_target_pct:
            old = self._effective_target_pct
            self._effective_target_pct = new_pct
            self._log(
                "info",
                f"GPU power target {old}% -> {new_pct}% "
                f"(difficulty={self._difficulty}, "
                f"ref={self._reference_difficulty}, "
                f"range {self._min_pct}–{self._target_pct}%)",
            )
        return self._effective_target_pct

    @property
    def effective_target_pct(self) -> int:
        return self._effective_target_pct

    def _target_mw_for_pct(self, pct: int) -> int:
        span = self._max_limit_mw - self._min_limit_mw
        return self._min_limit_mw + int(span * pct / 100)

    def apply(self) -> bool:
        """Raise power limit on session start. Returns True if limit was changed."""
        limits = self._monitor.get_power_limits_mw()
        if limits is None:
            self._log("warn", "GPU power boost skipped — NVML power limits unavailable")
            return False

        current_mw, min_mw, max_mw = limits
        self._original_limit_mw = current_mw
        self._min_limit_mw = min_mw
        self._max_limit_mw = max_mw
        self._effective_target_pct = self._compute_effective_target_pct()

        target_mw = self._target_mw_for_pct(self._effective_target_pct)
        if target_mw <= current_mw:
            self._current_limit_mw = current_mw
            self._applied = True
            self._log(
                "info",
                f"GPU power already at {current_mw / 1000:.0f}W "
                f"(max {max_mw / 1000:.0f}W, target {self._effective_target_pct}%) "
                f"— no boost needed",
            )
            return False

        if not self._set_power_limit_mw(target_mw):
            self._log(
                "warn",
                "GPU power boost failed — run miner as Administrator or "
                "enable power control in NVIDIA driver",
            )
            return False

        self._current_limit_mw = target_mw
        self._applied = True
        self._log(
            "info",
            f"GPU power boosted {current_mw / 1000:.0f}W -> {target_mw / 1000:.0f}W "
            f"(target {self._effective_target_pct}% of {max_mw / 1000:.0f}W cap, "
            f"range {self._min_pct}–{self._target_pct}%)",
        )
        if self._windows_performance_mode and sys.platform == "win32":
            self._enable_windows_high_performance()
        return True

    def _set_power_limit_mw(self, limit_mw: int) -> bool:
        if self._monitor.set_power_limit_mw(limit_mw):
            return True
        watts = max(1, int(round(limit_mw / 1000)))
        try:
            proc = subprocess.run(
                [
                    "nvidia-smi",
                    "-i",
                    str(self._device_index),
                    "-pl",
                    str(watts),
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if proc.returncode == 0:
                return True
            if self._logger and proc.stderr.strip():
                self._logger.warn(f"nvidia-smi power limit: {proc.stderr.strip()}")
        except (OSError, subprocess.TimeoutExpired) as exc:
            if self._logger:
                self._logger.warn(f"nvidia-smi power limit failed: {exc}")
        return False

    def _enable_windows_high_performance(self) -> None:
        try:
            active = subprocess.run(
                ["powercfg", "/getactivescheme"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            match = re.search(
                r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
                active.stdout,
                re.I,
            )
            if match:
                self._saved_power_scheme = match.group(1).lower()
            subprocess.run(
                ["powercfg", "/setactive", _HIGH_PERFORMANCE_GUID],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            self._log("info", "Windows power plan set to High performance")
        except (OSError, subprocess.TimeoutExpired) as exc:
            self._log("warn", f"Windows performance mode skipped: {exc}")

    def adjust(self, snap: GpuSnapshot | None) -> None:
        """
        Step power for temperature and difficulty target.

        - Near warn temp: step down toward original floor
        - Cool: step up toward difficulty-aware target (not above base target)
        - Difficulty target change alone also steps toward the new target
        """
        if not self._applied or snap is None or self._current_limit_mw is None:
            return
        if self._max_limit_mw <= self._min_limit_mw:
            return

        self._effective_target_pct = self._compute_effective_target_pct()
        target_mw = self._target_mw_for_pct(self._effective_target_pct)
        # Stay inside configured [min_pct, effective target] of the driver range.
        floor_mw = self._target_mw_for_pct(self._min_pct)
        floor_mw = max(self._min_limit_mw, min(floor_mw, target_mw, self._max_limit_mw))
        step_mw = max(5_000, (self._max_limit_mw - self._min_limit_mw) // 20)

        temp = snap.temperature_c
        new_mw = self._current_limit_mw

        if temp >= self._warn_temp_c - 2:
            new_mw = max(floor_mw, self._current_limit_mw - step_mw)
        elif temp <= self._warn_temp_c - 12:
            new_mw = min(target_mw, self._current_limit_mw + step_mw)
        else:
            # Mid band: only track difficulty target (no thermal step up/down).
            if self._current_limit_mw > target_mw:
                new_mw = max(target_mw, self._current_limit_mw - step_mw)
            elif self._current_limit_mw < target_mw and temp <= self._warn_temp_c - 5:
                new_mw = min(target_mw, self._current_limit_mw + step_mw)

        new_mw = max(floor_mw, min(new_mw, self._max_limit_mw))
        if new_mw == self._current_limit_mw:
            return
        if not self._set_power_limit_mw(new_mw):
            return

        old_w = self._current_limit_mw / 1000
        self._current_limit_mw = new_mw
        self._log(
            "info",
            f"GPU power {old_w:.0f}W -> {new_mw / 1000:.0f}W "
            f"(temp {temp}C, target {self._effective_target_pct}%, "
            f"floor {floor_mw / 1000:.0f}W, cap {self._max_temp_c}C)",
        )

    def restore(self) -> None:
        """Restore the original driver power limit on shutdown."""
        if not self._applied or self._original_limit_mw is None:
            return
        if (
            self._current_limit_mw is not None
            and self._current_limit_mw == self._original_limit_mw
        ):
            return
        if self._set_power_limit_mw(self._original_limit_mw):
            self._log(
                "info",
                f"GPU power restored to {self._original_limit_mw / 1000:.0f}W",
            )
        if self._saved_power_scheme and sys.platform == "win32":
            try:
                subprocess.run(
                    ["powercfg", "/setactive", self._saved_power_scheme],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                pass
            self._saved_power_scheme = None
        self._applied = False
