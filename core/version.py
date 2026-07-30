"""Single source of truth for xenminer-lowdif version strings."""

from __future__ import annotations

# Semver: MAJOR.MINOR.PATCH
# - MINOR: user-visible features (lowdif pack, dual temps, VRAM soft derate, …)
# - PATCH: fixes / polish
__version__ = "3.2.3"

# Display name for logs / dashboard
APP_NAME = "XenBlocks Miner by Tony.x1"
APP_CODENAME = "lowdif"

# Leaderboard / HTTP identity
USER_AGENT = f"xenblocksMiner/{__version__}-lowdif"


def version_string(*, short: bool = False) -> str:
    """Human version for UI and logs."""
    if short:
        return __version__
    return f"{__version__} ({APP_CODENAME})"


def banner_line() -> str:
    return f"{APP_NAME} v{version_string()}"
