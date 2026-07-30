"""NVIDIA driver access via NVML (pynvml / nvidia-ml-py).

Reads multiple temperature sensors when the driver exposes them. Control
temperature is the hottest reading so board/hotspot heat is not ignored
when GPU die still looks cool (common at high Argon2 difficulty).
"""

from __future__ import annotations

from monitoring.logger import SessionLogger
from core.models import GpuSnapshot

try:
    import pynvml
except ImportError:
    pynvml = None  # type: ignore


def _as_str(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _field_uint(handle: object, field_id: int) -> int | None:
    """Best-effort NVML field read (hotspot / memory / board on newer drivers)."""
    if pynvml is None:
        return None
    try:
        values = pynvml.nvmlDeviceGetFieldValues(handle, [int(field_id)])
    except Exception:
        return None
    if not values:
        return None
    entry = values[0]
    try:
        status = int(getattr(entry, "nvmlReturn", 0))
        if status != 0:
            return None
        raw = getattr(entry, "value", None)
        if raw is None:
            return None
        # c_nvmlValue_t union — uiVal is the usual path for temps
        for attr in ("uiVal", "ullVal", "dVal", "siVal"):
            if hasattr(raw, attr):
                val = getattr(raw, attr)
                try:
                    iv = int(val)
                except (TypeError, ValueError):
                    continue
                if 0 < iv < 150:
                    return iv
    except Exception:
        return None
    return None


def _discover_temp_field_ids() -> dict[str, int]:
    """Map friendly names → NVML field IDs present in this pynvml build."""
    if pynvml is None:
        return {}
    wanted = {
        "hotspot": (
            "NVML_FI_DEV_TEMPERATURE_HOT_SPOT",
            "NVML_FI_DEV_HOT_SPOT_TEMP",
            "NVML_FI_DEV_TEMPERATURE_HOTSPOT",
        ),
        "memory": (
            "NVML_FI_DEV_TEMPERATURE_MEMORY",
            "NVML_FI_DEV_MEMORY_TEMP",
            "NVML_FI_DEV_MEMORY_TEMPERATURE",
        ),
        "board": (
            "NVML_FI_DEV_TEMPERATURE_BOARD",
            "NVML_FI_DEV_BOARD_TEMP",
            "NVML_FI_DEV_BOARD_TEMPERATURE",
        ),
    }
    found: dict[str, int] = {}
    for key, names in wanted.items():
        for name in names:
            if hasattr(pynvml, name):
                try:
                    found[key] = int(getattr(pynvml, name))
                    break
                except (TypeError, ValueError):
                    continue
    return found


class NvidiaMonitor:
    def __init__(self, device_index: int = 0, logger: SessionLogger | None = None) -> None:
        self.device_index = device_index
        self.logger = logger
        self._ready = False
        self._temp_fields = _discover_temp_field_ids()
        self._logged_sensors = False
        if pynvml is None:
            if logger:
                logger.warn("pynvml not installed — GPU monitoring disabled")
            return
        try:
            pynvml.nvmlInit()
            self._handle = pynvml.nvmlDeviceGetHandleByIndex(device_index)
            self._ready = True
            name = _as_str(pynvml.nvmlDeviceGetName(self._handle))
            if logger:
                extra = (
                    f" temp_fields={sorted(self._temp_fields)}"
                    if self._temp_fields
                    else " temp_fields=die-only"
                )
                logger.info(f"NVML ready: GPU{device_index} {name}{extra}")
        except Exception as exc:
            if logger:
                logger.warn(f"NVML init failed: {exc}")

    @property
    def available(self) -> bool:
        return self._ready

    def _read_die_temp(self) -> int:
        assert pynvml is not None
        temp = pynvml.nvmlDeviceGetTemperature(
            self._handle, pynvml.NVML_TEMPERATURE_GPU
        )
        return int(temp)

    def _read_all_temps(self) -> tuple[int, int, int, int, int, str]:
        """
        Returns (control, die, board, hotspot, memory, source_label).

        control = max of available sensors so board heat triggers derate.
        """
        die = self._read_die_temp()
        board = 0
        hotspot = 0
        memory = 0
        if "board" in self._temp_fields:
            board = _field_uint(self._handle, self._temp_fields["board"]) or 0
        if "hotspot" in self._temp_fields:
            hotspot = _field_uint(self._handle, self._temp_fields["hotspot"]) or 0
        if "memory" in self._temp_fields:
            memory = _field_uint(self._handle, self._temp_fields["memory"]) or 0

        candidates: list[tuple[str, int]] = [("gpu", die)]
        if board > 0:
            candidates.append(("board", board))
        if hotspot > 0:
            candidates.append(("hotspot", hotspot))
        if memory > 0:
            candidates.append(("memory", memory))
        source, control = max(candidates, key=lambda item: item[1])
        return control, die, board, hotspot, memory, source

    def snapshot(self) -> GpuSnapshot | None:
        if not self._ready or pynvml is None:
            return None
        try:
            mem = pynvml.nvmlDeviceGetMemoryInfo(self._handle)
            util = pynvml.nvmlDeviceGetUtilizationRates(self._handle)
            power_mw = pynvml.nvmlDeviceGetPowerUsage(self._handle)
            control, die, board, hotspot, memory, source = self._read_all_temps()
            name = _as_str(pynvml.nvmlDeviceGetName(self._handle))
            if self.logger and not self._logged_sensors:
                self._logged_sensors = True
                self.logger.info(
                    f"Temp sensors: die={die}C board={board or 'n/a'} "
                    f"hotspot={hotspot or 'n/a'} mem={memory or 'n/a'} "
                    f"control={control}C({source})"
                )
            return GpuSnapshot(
                index=self.device_index,
                name=name,
                total_mib=mem.total // (1024 * 1024),
                used_mib=mem.used // (1024 * 1024),
                free_mib=mem.free // (1024 * 1024),
                util_pct=int(util.gpu),
                power_w=power_mw / 1000.0,
                temperature_c=int(control),
                gpu_temp_c=int(die),
                board_temp_c=int(board),
                hotspot_temp_c=int(hotspot),
                memory_temp_c=int(memory),
                temp_source=source,
            )
        except Exception as exc:
            if self.logger:
                self.logger.warn(f"NVML snapshot failed: {exc}")
            return None

    def within_budget(self, target_used_mib: int) -> bool:
        snap = self.snapshot()
        return snap is not None and snap.used_mib <= target_used_mib

    def get_power_limits_mw(self) -> tuple[int, int, int] | None:
        """Return (current_mw, min_mw, max_mw) or None if unavailable."""
        if not self._ready or pynvml is None:
            return None
        try:
            current = int(pynvml.nvmlDeviceGetPowerManagementLimit(self._handle))
            min_mw, max_mw = pynvml.nvmlDeviceGetPowerManagementLimitConstraints(
                self._handle
            )
            return current, int(min_mw), int(max_mw)
        except Exception as exc:
            if self.logger:
                self.logger.warn(f"NVML power limits read failed: {exc}")
            return None

    def set_power_limit_mw(self, limit_mw: int) -> bool:
        if not self._ready or pynvml is None:
            return False
        try:
            pynvml.nvmlDeviceSetPowerManagementLimit(self._handle, int(limit_mw))
            return True
        except Exception as exc:
            if self.logger:
                self.logger.warn(f"NVML set power limit failed: {exc}")
            return False

    def shutdown(self) -> None:
        if self._ready and pynvml is not None:
            try:
                pynvml.nvmlShutdown()
            except Exception:
                pass
            self._ready = False
