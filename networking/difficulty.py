from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request

from core.models import NetworkStatus

_DIFF_KEYS = (
    "difficulty",
    "diff",
    "memory_cost",
    "memoryCost",
    "network_difficulty",
    "networkDifficulty",
    "m",
)


def accept_network_difficulty(diff: int, *, fallback: int) -> int:
    """Use the live server value; memory_cost is only a fallback when RPC is invalid."""
    if diff <= 0:
        return fallback
    return diff


def parse_difficulty_payload(body: str) -> int | None:
    """
    Parse pool difficulty from JSON object, bare JSON number, or plain text.

    Official jacklevin-style miners use GET /difficulty → {"difficulty": N}.
    Some gateways return a bare integer. Returns None if unusable.
    """
    text = (body or "").strip()
    if not text:
        return None

    # Bare integer body
    if re.fullmatch(r"-?\d+", text):
        value = int(text)
        return value if value > 0 else None

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Last chance: first integer in the blob
        match = re.search(r"\b(\d{2,6})\b", text)
        if match:
            value = int(match.group(1))
            return value if value > 0 else None
        return None

    if isinstance(data, bool):
        return None
    if isinstance(data, (int, float)):
        value = int(data)
        return value if value > 0 else None
    if isinstance(data, dict):
        for key in _DIFF_KEYS:
            if key not in data:
                continue
            try:
                value = int(data[key])
            except (TypeError, ValueError):
                continue
            if value > 0:
                return value
        # Nested common shapes
        for nest_key in ("data", "result", "network", "status"):
            nested = data.get(nest_key)
            if isinstance(nested, dict):
                for key in _DIFF_KEYS:
                    if key not in nested:
                        continue
                    try:
                        value = int(nested[key])
                    except (TypeError, ValueError):
                        continue
                    if value > 0:
                        return value
    return None


def _candidate_urls(url: str) -> list[str]:
    """Prefer configured URL, then https/http twin if scheme differs."""
    out: list[str] = []
    primary = (url or "").strip()
    if primary:
        out.append(primary)
    if primary.startswith("http://"):
        out.append("https://" + primary[len("http://") :])
    elif primary.startswith("https://"):
        out.append("http://" + primary[len("https://") :])
    # de-dupe preserve order
    seen: set[str] = set()
    uniq: list[str] = []
    for item in out:
        if item not in seen:
            seen.add(item)
            uniq.append(item)
    return uniq


def fetch_difficulty(url: str, timeout_s: int = 20) -> NetworkStatus:
    """
    GET network difficulty (Argon2 memory cost m=).

    Important: this is NOT a cosmetic number. Submitted hashes must embed the
    same m= the pool expects or verify rejects (difficulty mismatch).
    """
    last_error = "no url"
    saw_http = False
    t0 = time.perf_counter()
    for candidate in _candidate_urls(url):
        try:
            req = urllib.request.Request(
                candidate,
                method="GET",
                headers={
                    "User-Agent": "xnminer/lowdif",
                    "Accept": "application/json,text/plain,*/*",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                latency = (time.perf_counter() - t0) * 1000
                saw_http = True
                diff = parse_difficulty_payload(body)
                if diff is None:
                    last_error = f"unparsed body from {candidate}: {body[:80]!r}"
                    continue
                return NetworkStatus(
                    port80_up=True,
                    difficulty=diff,
                    latency_ms=latency,
                )
        except urllib.error.HTTPError as exc:
            saw_http = True
            last_error = f"HTTP {exc.code} {candidate}"
            continue
        except Exception as exc:
            last_error = f"{candidate}: {exc}"
            continue

    return NetworkStatus(
        port80_up=saw_http,
        difficulty=None,
        latency_ms=None,
        error=last_error,
    )
