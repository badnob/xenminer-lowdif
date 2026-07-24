"""Difficulty-aware power and thermal batch derate — pure policy helpers.

Keeps automatic heat combat within configured ranges so high difficulty
and warm GPUs ease load without collapsing hashrate or power.
"""

from __future__ import annotations


def clamp_int(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def clamp_float(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def normalize_power_range(
    target_pct: int,
    min_pct: int,
    *,
    absolute_floor: int = 50,
    absolute_ceiling: int = 100,
) -> tuple[int, int]:
    """
    Ensure min/target sit inside [absolute_floor, absolute_ceiling]
    and min_pct <= target_pct.
    """
    target = clamp_int(int(target_pct), absolute_floor, absolute_ceiling)
    floor = clamp_int(int(min_pct), absolute_floor, absolute_ceiling)
    if floor > target:
        floor = target
    return target, floor


def difficulty_power_target_pct(
    base_target_pct: int,
    difficulty: int,
    reference_difficulty: int,
    *,
    min_pct: int = 75,
    full_derate_ratio: float = 2.0,
) -> int:
    """
    Ease GPU power target as difficulty rises above the reference.

    - difficulty <= reference → base_target_pct
    - difficulty >= reference * full_derate_ratio → min_pct
    - linear in between

    Result is always within [min_pct, base_target_pct] after normalization
    to the absolute 50–100 band.
    """
    target, floor = normalize_power_range(base_target_pct, min_pct)
    if difficulty <= 0 or reference_difficulty <= 0:
        return target
    if difficulty <= reference_difficulty:
        return target

    ratio = full_derate_ratio if full_derate_ratio > 1.0 else 2.0
    span = reference_difficulty * (ratio - 1.0)
    if span <= 0:
        return target

    over = difficulty - reference_difficulty
    t = clamp_float(over / span, 0.0, 1.0)
    eased = target - t * (target - floor)
    return clamp_int(int(round(eased)), floor, target)


def thermal_batch_scale(
    temperature_c: int,
    warn_temp_c: int,
    max_temp_c: int,
    *,
    min_scale: float = 0.70,
    cool_margin_c: int = 5,
) -> float:
    """
    Scale batch size down as GPU temp approaches warn/max.

    - temp <= warn - cool_margin → 1.0 (full planned batch)
    - temp >= max → min_scale (soft floor; emergency stop still owns hard stop)
    - linear between those points

    Scale is always within [min_scale, 1.0], with min_scale clamped to [0.50, 1.0].
    """
    floor = clamp_float(float(min_scale), 0.50, 1.0)
    if temperature_c <= 0:
        return 1.0

    warn = int(warn_temp_c)
    hard = max(warn + 1, int(max_temp_c))
    cool_start = warn - max(0, int(cool_margin_c))

    if temperature_c <= cool_start:
        return 1.0
    if temperature_c >= hard:
        return floor

    span = hard - cool_start
    if span <= 0:
        return floor
    t = (temperature_c - cool_start) / span
    return clamp_float(1.0 - t * (1.0 - floor), floor, 1.0)


def apply_batch_scale(batch_size: int, scale: float) -> int:
    """Apply thermal scale to a planned batch; never below 1 when batch > 0."""
    if batch_size <= 0:
        return 0
    s = clamp_float(float(scale), 0.50, 1.0)
    return max(1, int(batch_size * s))
