"""Cross-platform native CUDA library path helpers."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def cuda_lib_basename() -> str:
    """Default filename produced by native/build for this OS."""
    if sys.platform == "win32":
        return "xen_cuda.dll"
    # CMake SHARED target "xen_cuda" → libxen_cuda.so on Linux/macOS
    return "libxen_cuda.so"


def default_cuda_lib_relative() -> str:
    return f"native/build/bin/{cuda_lib_basename()}"


def default_cuda_lib_path() -> Path:
    return ROOT / default_cuda_lib_relative()


def lane_lib_name(lane: int) -> str:
    """Per-lane worker copy name (multi-process isolation fallback)."""
    if sys.platform == "win32":
        return f"lane{lane}.dll"
    return f"lane{lane}.so"


def resolve_cuda_lib_path(configured: str | Path | None = None) -> Path:
    """
    Resolve the native engine library path.

    Accepts miner.ini dll_path (historical name). If the configured path is
    missing, tries the platform default and common alternate names so a
    Windows-style .dll entry still works after building .so on Linux.
    """
    candidates: list[Path] = []
    if configured is not None and str(configured).strip():
        raw = Path(str(configured).strip())
        candidates.append(raw if raw.is_absolute() else ROOT / raw)

    candidates.append(default_cuda_lib_path())

    # Sibling alternates next to the first configured path (or default dir).
    base_dirs: list[Path] = []
    for c in list(candidates):
        base_dirs.append(c.parent)
    base_dirs.append(ROOT / "native" / "build" / "bin")

    names = (
        "xen_cuda.dll",
        "libxen_cuda.so",
        "xen_cuda.so",
        "libxen_cuda.dylib",
        "xen_cuda.dylib",
    )
    for directory in base_dirs:
        for name in names:
            candidates.append(directory / name)

    seen: set[Path] = set()
    for path in candidates:
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        if resolved in seen:
            continue
        seen.add(resolved)
        if path.exists():
            return path

    # Prefer configured path for error messages even if missing.
    if candidates:
        return candidates[0]
    return default_cuda_lib_path()


def build_hint() -> str:
    if sys.platform == "win32":
        return "Run: .\\native\\build.ps1"
    return "Run: ./native/build.sh"
