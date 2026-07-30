from __future__ import annotations

import configparser
import uuid
from dataclasses import dataclass
from pathlib import Path

from mining.native_lib import default_cuda_lib_relative, resolve_cuda_lib_path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INI = ROOT / "miner.ini"


@dataclass(frozen=True)
class Settings:
    address: str
    worker: str
    base_url: str
    connection_timeout_s: int
    network_poll_interval_s: int
    network_poll_timeout_s: int
    network_down_poll_interval_s: int
    backend: str
    strategy: str
    memory_cost: int
    time_cost: int
    parallelism: int
    hash_len: int
    # VRAM policy as % of each GPU's total (auto-scales). Absolute overrides
    # below are optional; 0 means "use percentage only".
    target_vram_pct: float
    desktop_headroom_pct: float
    emergency_vram_pct: float
    min_headroom_pct: float
    runtime_overhead_pct: float
    min_headroom_floor_mib: int
    runtime_overhead_floor_mib: int
    target_vram_mib: int
    headroom_mib: int
    emergency_vram_mib: int
    min_headroom_mib: int
    # Keep TOTAL NVML used ≤ target by subtracting desktop/background VRAM.
    vram_account_desktop: bool
    # Extra MiB pad on top of runtime overhead (fragmentation / estimate error).
    vram_safety_margin_mib: int
    # Live soft reel-in when used > target (keep mining; shrink batch/lanes).
    vram_soft_derate_enabled: bool
    vram_soft_min_scale: float
    vram_soft_lane_enabled: bool
    max_gpu_temp_c: int
    warn_gpu_temp_c: int
    # Board / PCB (often hotter than die under Argon2). Separate from die caps.
    max_board_temp_c: int
    warn_board_temp_c: int
    gpu_cooldown_s: int
    gpu_power_boost_enabled: bool
    gpu_power_target_pct: int
    # Floor for difficulty/thermal power ease (clamped ≤ target, ≥ 50).
    gpu_power_min_pct: int
    # Scale power target down as difficulty rises above vram_reference_difficulty.
    gpu_difficulty_power_enabled: bool
    # Difficulty multiple of reference where power hits min_pct (e.g. 2.0 = 2×).
    gpu_difficulty_power_full_ratio: float
    # Clock curve: max clocks at low dif, slope batch fill + power as dif rises.
    clock_curve_enabled: bool
    clock_low_difficulty: int
    clock_batch_fill_low: float
    clock_batch_fill_ref: float
    clock_batch_fill_high: float
    # Soft-shrink CUDA batch as temp approaches warn/max (scale ≥ min).
    gpu_thermal_batch_enabled: bool
    gpu_thermal_batch_min_scale: float
    gpu_windows_performance_mode: bool
    temp_watch_path: Path
    cpu_lanes: int
    lane_ramp_step: int
    sample_interval_s: int
    db_path: Path
    jsonl_path: Path
    rejected_jsonl_path: Path
    log_path: Path
    timelapse_path: Path
    stats_interval_s: int
    timelapse_sample_s: int
    dashboard_enabled: bool
    # X1 chain RPC for wallet balance panel (comma-separated OK)
    wallet_rpc_url: str
    woodyminer_enabled: bool
    woodyminer_upload_url: str
    woodyminer_upload_period_s: int
    woodyminer_custom_name: str
    # Share accepts + holdings with local/open XenBlockScan index
    xenblockscan_enabled: bool
    xenblockscan_endpoint: str
    xenblockscan_api_key: str
    xenblockscan_report_rejects: bool
    xenblockscan_holdings_interval_s: int
    xenblockscan_backfill: bool
    # Stable ID for this miner install (website fleet tracker)
    tracker_id: str
    xenblocks_exe: Path | None
    xenblocks_db: Path | None
    gpu_enabled: bool
    cuda_dll_path: Path
    cuda_batch_size: int
    cuda_max_batch_size: int
    cuda_runtime_overhead_mib: int
    vram_reference_difficulty: int
    cuda_max_lanes: int
    cuda_lane_reserve: int
    # Low-dif harvest packing: fill = pack lanes to VRAM; boost = legacy ref//diff.
    cuda_lane_pack_mode: str
    # Each lane keeps at least this many attempts when packing (fill mode).
    cuda_min_batch_per_lane: int
    # Windows: extra laneN.dll copies for parallel fallback. If false (or load
    # fails), multi-lane uses sequential key prefixes on one engine.
    cuda_allow_dll_lane_copies: bool
    # Live shrink multi-lane harvest as temp approaches warn/max.
    gpu_thermal_lane_enabled: bool
    gpu_thermal_lane_min: int
    # As difficulty climbs toward reference, bias lanes down before VRAM forces it.
    gpu_difficulty_lane_bias: bool
    gpu_difficulty_lane_full_pack_ratio: float
    # At high difficulty, raise effective control temp (board heat proxy when sensors thin).
    gpu_high_diff_temp_enabled: bool
    gpu_high_diff_temp_start_ratio: float
    gpu_high_diff_temp_full_ratio: float
    gpu_high_diff_temp_max_tighten_c: int
    submit_cpu_fraction: float

    @property
    def salt_hex(self) -> str:
        return self.address[2:]

    @property
    def difficulty_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/difficulty"

    @property
    def verify_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/verify"


def _ensure_tracker_id(ini_path: Path, mon: configparser.SectionProxy) -> str:
    """Stable fleet tracker id for this install; write once to miner.ini."""
    existing = (mon.get("tracker_id") or mon.get("xenblockscan_tracker_id") or "").strip()
    if existing:
        return existing
    tid = f"xbs-{uuid.uuid4().hex[:16]}"
    try:
        from config.wallet_setup import _set_ini_value

        _set_ini_value(ini_path, "monitoring", "tracker_id", tid)
    except Exception:
        pass
    return tid


def load_settings(ini_path: Path | None = None) -> Settings:
    path = ini_path or DEFAULT_INI
    cp = configparser.ConfigParser()
    cp.read(path, encoding="utf-8")

    acc = cp["account"]
    srv = cp["server"]
    mine = cp["mining"]
    eff = cp["efficiency"]
    que = cp["queue"]
    mon = cp["monitoring"]
    gpu = cp["gpu"]
    cuda = cp["cuda"] if "cuda" in cp else {}

    exe_raw = gpu.get("xenblocks_exe", "").strip()
    dll_raw = cuda.get("dll_path", default_cuda_lib_relative()).strip()
    cuda_lib = resolve_cuda_lib_path(dll_raw)
    return Settings(
        address=acc.get("address", "").strip(),
        worker=acc.get("worker", "").strip(),
        base_url=srv.get("base_url", "http://xenblocks.io").strip(),
        connection_timeout_s=int(srv.get("connection_timeout_s", "20")),
        network_poll_interval_s=int(srv.get("network_poll_interval_s", "15")),
        network_poll_timeout_s=int(srv.get("network_poll_timeout_s", "3")),
        network_down_poll_interval_s=int(srv.get("network_down_poll_interval_s", "30")),
        backend=mine.get("backend", "cpu").strip().lower(),
        strategy=mine.get("strategy", "random").strip().lower(),
        memory_cost=int(mine.get("memory_cost", "1100")),
        time_cost=int(mine.get("time_cost", "1")),
        parallelism=int(mine.get("parallelism", "1")),
        hash_len=int(mine.get("hash_len", "64")),
        # % of each card's total VRAM (from 5090 safety profile ≈ 69/25/93/4/6).
        target_vram_pct=float(eff.get("target_vram_pct", "69.09")),
        desktop_headroom_pct=float(eff.get("desktop_headroom_pct", "25.12")),
        emergency_vram_pct=float(eff.get("emergency_vram_pct", "92.78")),
        min_headroom_pct=float(eff.get("min_headroom_pct", "3.68")),
        runtime_overhead_pct=float(
            cuda.get(
                "runtime_overhead_pct",
                eff.get("runtime_overhead_pct", "6.28"),
            )
        ),
        min_headroom_floor_mib=int(eff.get("min_headroom_floor_mib", "512")),
        runtime_overhead_floor_mib=int(
            cuda.get(
                "runtime_overhead_floor_mib",
                eff.get("runtime_overhead_floor_mib", "256"),
            )
        ),
        # Absolute overrides (0 = derive from % of detected total VRAM).
        target_vram_mib=int(eff.get("target_vram_mib", "0")),
        headroom_mib=int(eff.get("headroom_mib", "0")),
        emergency_vram_mib=int(eff.get("emergency_vram_mib", "0")),
        min_headroom_mib=int(eff.get("min_headroom_mib", "0")),
        # Default true: Win11 display GPU + Chrome/DWM must not be ignored.
        vram_account_desktop=str(eff.get("vram_account_desktop", "true"))
        .strip()
        .lower()
        in ("1", "true", "yes", "on"),
        vram_safety_margin_mib=int(eff.get("vram_safety_margin_mib", "512")),
        vram_soft_derate_enabled=str(eff.get("vram_soft_derate_enabled", "true"))
        .strip()
        .lower()
        in ("1", "true", "yes", "on"),
        vram_soft_min_scale=float(eff.get("vram_soft_min_scale", "0.55")),
        vram_soft_lane_enabled=str(eff.get("vram_soft_lane_enabled", "true"))
        .strip()
        .lower()
        in ("1", "true", "yes", "on"),
        max_gpu_temp_c=int(eff.get("max_gpu_temp_c", "84")),
        warn_gpu_temp_c=int(eff.get("warn_gpu_temp_c", "78")),
        # Board: Tony measured ~88C sustained; hard cap 90 with warn before that.
        max_board_temp_c=int(eff.get("max_board_temp_c", "90")),
        warn_board_temp_c=int(eff.get("warn_board_temp_c", "85")),
        gpu_cooldown_s=int(eff.get("gpu_cooldown_s", "45")),
        gpu_power_boost_enabled=eff.getboolean("gpu_power_boost_enabled", fallback=True),
        gpu_power_target_pct=int(eff.get("gpu_power_target_pct", "100")),
        gpu_power_min_pct=int(eff.get("gpu_power_min_pct", "65")),
        gpu_difficulty_power_enabled=eff.getboolean(
            "gpu_difficulty_power_enabled", fallback=True
        ),
        gpu_difficulty_power_full_ratio=float(
            eff.get("gpu_difficulty_power_full_ratio", "1.9")
        ),
        clock_curve_enabled=str(eff.get("clock_curve_enabled", "true"))
        .strip()
        .lower()
        in ("1", "true", "yes", "on"),
        clock_low_difficulty=int(eff.get("clock_low_difficulty", "100")),
        clock_batch_fill_low=float(eff.get("clock_batch_fill_low", "0.72")),
        clock_batch_fill_ref=float(eff.get("clock_batch_fill_ref", "0.95")),
        clock_batch_fill_high=float(eff.get("clock_batch_fill_high", "0.85")),
        gpu_thermal_batch_enabled=eff.getboolean(
            "gpu_thermal_batch_enabled", fallback=True
        ),
        gpu_thermal_batch_min_scale=float(
            eff.get("gpu_thermal_batch_min_scale", "0.70")
        ),
        gpu_thermal_lane_enabled=eff.getboolean(
            "gpu_thermal_lane_enabled", fallback=True
        ),
        gpu_thermal_lane_min=int(eff.get("gpu_thermal_lane_min", "1")),
        gpu_difficulty_lane_bias=eff.getboolean(
            "gpu_difficulty_lane_bias", fallback=True
        ),
        gpu_difficulty_lane_full_pack_ratio=float(
            eff.get("gpu_difficulty_lane_full_pack_ratio", "0.35")
        ),
        gpu_high_diff_temp_enabled=eff.getboolean(
            "gpu_high_diff_temp_enabled", fallback=True
        ),
        gpu_high_diff_temp_start_ratio=float(
            eff.get("gpu_high_diff_temp_start_ratio", "1.5")
        ),
        gpu_high_diff_temp_full_ratio=float(
            eff.get("gpu_high_diff_temp_full_ratio", "1.9")
        ),
        gpu_high_diff_temp_max_tighten_c=int(
            eff.get("gpu_high_diff_temp_max_tighten_c", "12")
        ),
        gpu_windows_performance_mode=eff.getboolean(
            "gpu_windows_performance_mode", fallback=True
        ),
        temp_watch_path=ROOT / mon.get("temp_watch_path", "data/temp_watch.log"),
        cpu_lanes=int(eff.get("cpu_lanes", "2")),
        lane_ramp_step=int(eff.get("lane_ramp_step", "1")),
        sample_interval_s=int(eff.get("sample_interval_s", "5")),
        db_path=ROOT / que.get("db_path", "data/blocks.db"),
        jsonl_path=ROOT / que.get("jsonl_path", "data/queue.jsonl"),
        rejected_jsonl_path=ROOT / que.get("rejected_jsonl_path", "data/rejected.jsonl"),
        log_path=ROOT / mon.get("log_path", "data/session.log"),
        timelapse_path=ROOT / mon.get("timelapse_path", "data/session_timelapse.jsonl"),
        stats_interval_s=int(mon.get("stats_interval_s", "10")),
        timelapse_sample_s=int(mon.get("timelapse_sample_s", "30")),
        dashboard_enabled=mon.getboolean("dashboard_enabled", fallback=True),
        wallet_rpc_url=str(
            mon.get(
                "wallet_rpc_url",
                "https://xenblocks.io:5556,https://xenblocks.io:5555",
            )
        ).strip(),
        woodyminer_enabled=mon.getboolean("woodyminer_enabled", fallback=True),
        woodyminer_upload_url=mon.get(
            "woodyminer_upload_url", "https://woodyminer.com/api/stat/upload"
        ).strip(),
        woodyminer_upload_period_s=int(mon.get("woodyminer_upload_period_s", "60")),
        woodyminer_custom_name=mon.get("woodyminer_custom_name", "").strip()
        or acc.get("worker", "").strip(),
        xenblockscan_enabled=mon.getboolean("xenblockscan_enabled", fallback=False),
        xenblockscan_endpoint=mon.get(
            "xenblockscan_endpoint", "http://127.0.0.1:8787/api/v1/events"
        ).strip(),
        xenblockscan_api_key=mon.get("xenblockscan_api_key", "").strip(),
        xenblockscan_report_rejects=mon.getboolean(
            "xenblockscan_report_rejects", fallback=False
        ),
        # How often to push balances + live hashrate to the site (seconds)
        xenblockscan_holdings_interval_s=int(
            mon.get("xenblockscan_holdings_interval_s", "30")
        ),
        # Off by default — history bulk was hanging startup; live accepts are enough
        xenblockscan_backfill=mon.getboolean("xenblockscan_backfill", fallback=False),
        tracker_id=_ensure_tracker_id(path, mon),
        xenblocks_exe=Path(exe_raw) if exe_raw else None,
        xenblocks_db=Path(gpu.get("xenblocks_db", "").strip()) if gpu.get("xenblocks_db", "").strip() else None,
        gpu_enabled=gpu.getboolean("enabled", fallback=False),
        cuda_dll_path=cuda_lib,
        cuda_batch_size=int(cuda.get("batch_size", "0")),
        cuda_max_batch_size=int(cuda.get("max_batch_size", "0")),
        # 0 = use runtime_overhead_pct of GPU total.
        cuda_runtime_overhead_mib=int(
            cuda.get("runtime_overhead_mib", eff.get("cuda_runtime_overhead_mib", "0"))
        ),
        vram_reference_difficulty=int(
            cuda.get(
                "vram_reference_difficulty",
                mine.get("memory_cost", "1100"),
            )
        ),
        cuda_max_lanes=int(cuda.get("max_lanes", "8")),
        cuda_lane_reserve=int(cuda.get("lane_reserve", "1")),
        cuda_lane_pack_mode=str(
            cuda.get("lane_pack_mode", eff.get("lane_pack_mode", "fill"))
        )
        .strip()
        .lower()
        or "fill",
        cuda_min_batch_per_lane=int(
            cuda.get(
                "min_batch_per_lane",
                eff.get("min_batch_per_lane", "2048"),
            )
        ),
        # Default false: DLL copies often hit WinError 5 on Windows.
        # Native multi-lane DLL still parallelises; sequential prefixes otherwise.
        cuda_allow_dll_lane_copies=str(
            cuda.get("allow_dll_lane_copies", "false")
        )
        .strip()
        .lower()
        in ("1", "true", "yes", "on"),
        submit_cpu_fraction=float(que.get("submit_cpu_fraction", "0.30")),
    )