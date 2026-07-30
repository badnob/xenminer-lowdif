"""ctypes bindings for native xen_cuda GPU engine (.dll / .so)."""

from __future__ import annotations

import ctypes
import sys
from dataclasses import dataclass
from pathlib import Path

from mining.native_lib import (
    build_hint,
    default_cuda_lib_path,
    resolve_cuda_lib_path,
)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DLL = default_cuda_lib_path()

XEN_CUDA_MAX_MATCHES = 32
XEN_CUDA_KEY_LEN = 65
XEN_CUDA_HASH_LEN = 256
XEN_CUDA_ERR_LEN = 256


class XenCudaMatch(ctypes.Structure):
    _fields_ = [
        ("key", ctypes.c_char * XEN_CUDA_KEY_LEN),
        ("hash", ctypes.c_char * XEN_CUDA_HASH_LEN),
        ("pattern", ctypes.c_char * 32),
        ("attempt_index", ctypes.c_uint64),
    ]


class XenCudaBatchResult(ctypes.Structure):
    _fields_ = [
        ("ok", ctypes.c_int),
        ("error", ctypes.c_char * XEN_CUDA_ERR_LEN),
        ("attempts", ctypes.c_uint64),
        ("hashrate", ctypes.c_double),
        ("elapsed_ms", ctypes.c_double),
        ("batch_size", ctypes.c_uint32),
        ("match_count", ctypes.c_uint32),
        ("matches", XenCudaMatch * XEN_CUDA_MAX_MATCHES),
    ]


class XenCudaDeviceInfo(ctypes.Structure):
    _fields_ = [
        ("device_id", ctypes.c_int),
        ("name", ctypes.c_char * 128),
        ("total_vram_bytes", ctypes.c_uint64),
        ("free_vram_bytes", ctypes.c_uint64),
    ]


@dataclass
class CudaMatch:
    key: str
    hash_str: str
    pattern: str
    attempt_index: int


@dataclass
class CudaBatchResult:
    ok: bool
    error: str
    attempts: int
    hashrate: float
    elapsed_ms: float
    batch_size: int
    matches: list[CudaMatch]


class CudaEngine:
    # Keep DLL search dirs alive for the process (Windows).
    _dll_dirs: list[object] = []

    def __init__(self, dll_path: Path | None = None) -> None:
        path = resolve_cuda_lib_path(dll_path) if dll_path else resolve_cuda_lib_path()
        if not path.exists():
            raise FileNotFoundError(
                f"Native CUDA library not found at {path}. {build_hint()}"
            )
        path = path.resolve()
        # Linux often needs RTLD_GLOBAL so CUDA runtime symbols resolve.
        if sys.platform == "win32":
            self._lib = self._load_windows_dll(path)
        else:
            mode = getattr(ctypes, "RTLD_GLOBAL", 0)
            self._lib = ctypes.CDLL(str(path), mode=mode) if mode else ctypes.CDLL(str(path))
        self._lib_path = path
        self._parallel_lanes = False
        self._bind()

    @classmethod
    def _load_windows_dll(cls, path: Path) -> ctypes.CDLL:
        """
        Load a CUDA engine DLL on Windows.

        Multi-lane fallback copies live under data/cuda_lane_workers/; without
        add_dll_directory, dependent CUDA runtime DLLs often fail with
        WinError 5 (Access is denied) or missing-dependency errors.
        """
        import os

        search_dirs = [path.parent]
        # Also search the primary build bin (where cudart etc. often sit).
        try:
            primary = resolve_cuda_lib_path().resolve().parent
            if primary not in search_dirs:
                search_dirs.append(primary)
        except OSError:
            pass

        for directory in search_dirs:
            try:
                if hasattr(os, "add_dll_directory"):
                    handle = os.add_dll_directory(str(directory))
                    cls._dll_dirs.append(handle)
            except (OSError, FileNotFoundError, AttributeError):
                continue

        # Prefer WinDLL after add_dll_directory (Python 3.8+).
        try:
            return ctypes.WinDLL(str(path))  # type: ignore[attr-defined]
        except OSError as exc:
            last_err = exc
        try:
            return ctypes.CDLL(str(path))
        except OSError as exc:
            last_err = exc
        raise OSError(
            f"Failed to load CUDA library '{path}': {last_err}. "
            f"If this is a lane copy (laneN.dll), Windows often blocks multi-DLL "
            f"CUDA loads — rebuild with native multi-lane (xen_cuda_set_lane_count) "
            f"or set allow_dll_lane_copies=false for sequential multi-prefix."
        ) from last_err

    def _bind(self) -> None:
        lib = self._lib
        lib.xen_cuda_init.argtypes = [ctypes.c_int, ctypes.c_uint64]
        lib.xen_cuda_init.restype = ctypes.c_int
        lib.xen_cuda_shutdown.argtypes = []
        lib.xen_cuda_shutdown.restype = None
        if hasattr(lib, "xen_cuda_set_lane_count"):
            lib.xen_cuda_set_lane_count.argtypes = [ctypes.c_int]
            lib.xen_cuda_set_lane_count.restype = ctypes.c_int
            self._parallel_lanes = True
        lib.xen_cuda_device_info.argtypes = [ctypes.c_int, ctypes.POINTER(XenCudaDeviceInfo)]
        lib.xen_cuda_device_info.restype = ctypes.c_int
        lib.xen_cuda_select_batch_size.argtypes = [
            ctypes.c_uint64,
            ctypes.c_uint32,
            ctypes.c_uint64,
        ]
        lib.xen_cuda_select_batch_size.restype = ctypes.c_uint64
        if self._parallel_lanes:
            lib.xen_cuda_run_lane_batch.argtypes = [
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_char_p,
                ctypes.c_uint32,
                ctypes.c_uint64,
                ctypes.c_int,
                ctypes.POINTER(XenCudaBatchResult),
            ]
            lib.xen_cuda_run_lane_batch.restype = ctypes.c_int
        lib.xen_cuda_run_batch.argtypes = [
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_uint32,
            ctypes.c_uint64,
            ctypes.c_int,
            ctypes.POINTER(XenCudaBatchResult),
        ]
        lib.xen_cuda_run_batch.restype = ctypes.c_int
        lib.xen_cuda_verify_known.argtypes = [
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_uint32,
            ctypes.c_char_p,
            ctypes.c_size_t,
        ]
        lib.xen_cuda_verify_known.restype = ctypes.c_int

    def init(self, device_id: int = 0, reserve_bytes: int = 100 * 1024 * 1024) -> None:
        rc = self._lib.xen_cuda_init(device_id, reserve_bytes)
        if rc != 0:
            raise RuntimeError(f"xen_cuda_init failed ({rc})")

    def shutdown(self) -> None:
        self._lib.xen_cuda_shutdown()

    @property
    def parallel_lanes_supported(self) -> bool:
        return self._parallel_lanes

    def set_lane_count(self, lane_count: int) -> None:
        if not self._parallel_lanes:
            return
        rc = self._lib.xen_cuda_set_lane_count(int(lane_count))
        if rc != 0:
            raise RuntimeError(f"xen_cuda_set_lane_count failed ({rc})")

    def device_info(self, device_id: int = 0) -> XenCudaDeviceInfo:
        info = XenCudaDeviceInfo()
        rc = self._lib.xen_cuda_device_info(device_id, ctypes.byref(info))
        if rc != 0:
            raise RuntimeError(f"xen_cuda_device_info failed ({rc})")
        return info

    def select_batch_size(
        self,
        free_vram_bytes: int,
        difficulty: int,
        max_batch: int = 0,
    ) -> int:
        return int(
            self._lib.xen_cuda_select_batch_size(
                ctypes.c_uint64(free_vram_bytes),
                ctypes.c_uint32(difficulty),
                ctypes.c_uint64(max_batch),
            )
        )

    def run_lane_batch(
        self,
        lane_index: int,
        salt_hex: str,
        difficulty: int,
        batch_size: int,
        key_prefix: str = "",
        allow_xuni: bool = True,
    ) -> CudaBatchResult:
        out = XenCudaBatchResult()
        if self._parallel_lanes:
            rc = self._lib.xen_cuda_run_lane_batch(
                ctypes.c_int(lane_index),
                salt_hex.encode("ascii"),
                key_prefix.encode("ascii") if key_prefix else None,
                ctypes.c_uint32(difficulty),
                ctypes.c_uint64(batch_size),
                1 if allow_xuni else 0,
                ctypes.byref(out),
            )
        else:
            rc = self._lib.xen_cuda_run_batch(
                salt_hex.encode("ascii"),
                key_prefix.encode("ascii") if key_prefix else None,
                ctypes.c_uint32(difficulty),
                ctypes.c_uint64(batch_size),
                1 if allow_xuni else 0,
                ctypes.byref(out),
            )
        matches: list[CudaMatch] = []
        for i in range(out.match_count):
            m = out.matches[i]
            matches.append(
                CudaMatch(
                    key=m.key.decode("ascii", errors="replace"),
                    hash_str=m.hash.decode("ascii", errors="replace"),
                    pattern=m.pattern.decode("ascii", errors="replace"),
                    attempt_index=int(m.attempt_index),
                )
            )
        result = CudaBatchResult(
            ok=bool(out.ok),
            error=out.error.decode("ascii", errors="replace"),
            attempts=int(out.attempts),
            hashrate=float(out.hashrate),
            elapsed_ms=float(out.elapsed_ms),
            batch_size=int(out.batch_size),
            matches=matches,
        )
        if rc != 0 and not result.error:
            result.error = f"xen_cuda_run_lane_batch rc={rc}"
        return result

    def run_batch(
        self,
        salt_hex: str,
        difficulty: int,
        batch_size: int,
        key_prefix: str = "",
        allow_xuni: bool = True,
    ) -> CudaBatchResult:
        return self.run_lane_batch(
            0,
            salt_hex,
            difficulty,
            batch_size,
            key_prefix=key_prefix,
            allow_xuni=allow_xuni,
        )

    def verify_known(self, salt_hex: str, key_hex: str, difficulty: int) -> str:
        buf = ctypes.create_string_buffer(XEN_CUDA_HASH_LEN)
        rc = self._lib.xen_cuda_verify_known(
            salt_hex.encode("ascii"),
            key_hex.encode("ascii"),
            ctypes.c_uint32(difficulty),
            buf,
            XEN_CUDA_HASH_LEN,
        )
        if rc != 0:
            raise RuntimeError(f"xen_cuda_verify_known failed ({rc})")
        return buf.value.decode("ascii", errors="replace")