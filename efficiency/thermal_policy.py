"""Difficulty-aware power and thermal batch/lane derate — pure policy helpers.

Keeps automatic heat combat within configured ranges so high difficulty
and warm GPUs ease load without collapsing hashrate or power.

Low-difficulty multi-lane harvest runs cool and fast; when difficulty (and
board heat) climb, we soft-scale batch first, then shrink live lane count
before the hard temp stop.
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
    low_difficulty: int = 100,
) -> int:
    """
    Difficulty-aware power for max clocks at low dif, ease-off as dif rises.

    - difficulty <= low_difficulty → base_target_pct (max clocks / power)
    - low_difficulty → reference → ease toward ~mid of [min, base]
    - reference → reference * full_derate_ratio → min_pct
    - linear within each segment

    Result always within [min_pct, base_target_pct] (50–100 absolute band).
    """
    target, floor = normalize_power_range(base_target_pct, min_pct)
    if difficulty <= 0 or reference_difficulty <= 0:
        return target

    low = max(1, int(low_difficulty))
    ref = max(low, int(reference_difficulty))
    dif = max(1, int(difficulty))

    if dif <= low:
        return target

    ratio = full_derate_ratio if full_derate_ratio > 1.0 else 2.0
    high = max(ref + 1, int(round(ref * ratio)))
    # Mid power at reference: halfway from target to floor (still strong).
    mid = clamp_int(int(round(target - 0.35 * (target - floor))), floor, target)

    if dif <= ref:
        span = ref - low
        t = clamp_float((dif - low) / span, 0.0, 1.0) if span > 0 else 1.0
        eased = target - t * (target - mid)
        return clamp_int(int(round(eased)), floor, target)

    # Above reference → slope to floor by high
    span = high - ref
    t = clamp_float((dif - ref) / span, 0.0, 1.0) if span > 0 else 1.0
    eased = mid - t * (mid - floor)
    return clamp_int(int(round(eased)), floor, target)


def difficulty_batch_fill_fraction(
    difficulty: int,
    reference_difficulty: int,
    *,
    low_difficulty: int = 100,
    fill_at_low: float = 0.72,
    fill_at_ref: float = 0.95,
    fill_at_high: float = 0.85,
    full_derate_ratio: float = 1.9,
) -> float:
    """
    VRAM batch fill fraction vs difficulty (clock curve).

    Low dif Argon2 is less memory-hard per attempt — packing the entire VRAM
    cap can pin the card in a memory/power limited state and hold clocks down.
    Leaving fill headroom at dif~100 often raises SM clocks and real H/s.

    - <= low_difficulty → fill_at_low (clock headroom)
    - → reference → fill_at_ref (dense harvest)
    - → high (ref * ratio) → fill_at_high (ease memory pressure + heat)
    """
    low_f = clamp_float(float(fill_at_low), 0.40, 1.0)
    ref_f = clamp_float(float(fill_at_ref), 0.40, 1.0)
    high_f = clamp_float(float(fill_at_high), 0.40, 1.0)

    if difficulty <= 0 or reference_difficulty <= 0:
        return ref_f

    low = max(1, int(low_difficulty))
    ref = max(low, int(reference_difficulty))
    dif = max(1, int(difficulty))
    ratio = full_derate_ratio if full_derate_ratio > 1.0 else 1.9
    high = max(ref + 1, int(round(ref * ratio)))

    if dif <= low:
        return low_f
    if dif <= ref:
        span = ref - low
        t = clamp_float((dif - low) / span, 0.0, 1.0) if span > 0 else 1.0
        return clamp_float(low_f + t * (ref_f - low_f), 0.40, 1.0)

    span = high - ref
    t = clamp_float((dif - ref) / span, 0.0, 1.0) if span > 0 else 1.0
    return clamp_float(ref_f + t * (high_f - ref_f), 0.40, 1.0)


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


def vram_pressure_scale(
    used_mib: int,
    target_mib: int,
    emergency_mib: int,
    *,
    min_scale: float = 0.55,
    start_slack_mib: int = 0,
) -> float:
    """
    Soft VRAM reel-in — keep mining, shrink work as used rises past target.

    - used <= target + start_slack → 1.0 (full planned batch)
    - used >= emergency → min_scale (still hashing; hard stop is separate)
    - linear between those points

    Does NOT pause or stop. Emergency VRAM stop remains VramGuard's job.
    """
    floor = clamp_float(float(min_scale), 0.50, 1.0)
    used = max(0, int(used_mib))
    target = max(1, int(target_mib))
    emerg = max(target + 1, int(emergency_mib))
    start = target + max(0, int(start_slack_mib))

    if used <= start:
        return 1.0
    if used >= emerg:
        return floor
    span = emerg - start
    if span <= 0:
        return floor
    t = (used - start) / span
    return clamp_float(1.0 - t * (1.0 - floor), floor, 1.0)


def vram_pressure_lane_cap(
    planned_lanes: int,
    used_mib: int,
    target_mib: int,
    emergency_mib: int,
    *,
    min_lanes: int = 1,
) -> int:
    """
    Soft lane shrink under VRAM pressure (still mining).

    Full lanes at/under target; step down toward min_lanes as used approaches
    emergency. Prefer trimming lanes before starving batch to zero.
    """
    planned = max(1, int(planned_lanes))
    floor = clamp_int(int(min_lanes), 1, planned)
    if planned <= floor:
        return planned
    scale = vram_pressure_scale(used_mib, target_mib, emergency_mib, min_scale=0.50)
    if scale >= 0.999:
        return planned
    # Map scale 1→planned, 0.5→floor
    t = clamp_float((1.0 - scale) / 0.50, 0.0, 1.0)
    raw = planned - t * (planned - floor)
    return clamp_int(int(round(raw)), floor, planned)


def combine_batch_scales(*scales: float, floor: float = 0.50) -> float:
    """Most aggressive (lowest) of thermal / VRAM / other soft scales."""
    lo = clamp_float(float(floor), 0.50, 1.0)
    if not scales:
        return 1.0
    return clamp_float(min(float(s) for s in scales), lo, 1.0)


def thermal_lane_cap(
    planned_lanes: int,
    temperature_c: int,
    warn_temp_c: int,
    max_temp_c: int,
    *,
    min_lanes: int = 1,
    cool_margin_c: int = 8,
    start_derate_margin_c: int = 3,
) -> int:
    """
    Live max lanes under heat — shrink multi-lane harvest before hard stop.

    - temp <= warn - cool_margin → full planned_lanes
    - temp >= warn - start_derate_margin → begin stepping down
    - temp >= max → min_lanes
    - linear step count between start and max

    Used so difficulty spikes that heat the board drop lanes *immediately*
    instead of waiting for a full cooldown restart.
    """
    planned = max(1, int(planned_lanes))
    floor = clamp_int(int(min_lanes), 1, planned)
    if planned <= floor:
        return planned
    if temperature_c <= 0:
        return planned

    warn = int(warn_temp_c)
    hard = max(warn + 1, int(max_temp_c))
    cool_start = warn - max(0, int(cool_margin_c))
    # Begin shrinking a few degrees before warn so we don't ride the edge.
    derate_start = warn - max(0, int(start_derate_margin_c))
    derate_start = max(cool_start, derate_start)

    if temperature_c <= derate_start:
        return planned
    if temperature_c >= hard:
        return floor

    span = hard - derate_start
    if span <= 0:
        return floor
    t = clamp_float((temperature_c - derate_start) / span, 0.0, 1.0)
    # Continuous shrink, then ceil-ish via round so we step cleanly.
    raw = planned - t * (planned - floor)
    return clamp_int(int(round(raw)), floor, planned)


def high_diff_temp_tighten_c(
    difficulty: int,
    reference_difficulty: int,
    *,
    start_ratio: float = 1.5,
    full_ratio: float = 2.0,
    max_tighten_c: int = 10,
) -> int:
    """
    Degrees to subtract from warn/max (or add to effective temp) at high difficulty.

    Argon2id at 2× reference runs much hotter on the *board* even when die NVML
    still looks modest. Tightening thresholds as difficulty climbs catches that
    earlier — especially if board/hotspot sensors are missing.

    - difficulty <= ref * start_ratio → 0
    - difficulty >= ref * full_ratio → max_tighten_c
    - linear in between
    """
    if difficulty <= 0 or reference_difficulty <= 0 or max_tighten_c <= 0:
        return 0
    start = reference_difficulty * max(1.0, float(start_ratio))
    full = reference_difficulty * max(start_ratio + 0.01, float(full_ratio))
    if difficulty <= start:
        return 0
    if difficulty >= full:
        return int(max_tighten_c)
    t = (difficulty - start) / (full - start)
    return int(round(clamp_float(t, 0.0, 1.0) * max_tighten_c))


def effective_control_temp_c(
    measured_temp_c: int,
    difficulty: int,
    reference_difficulty: int,
    *,
    start_ratio: float = 1.5,
    full_ratio: float = 2.0,
    max_tighten_c: int = 10,
) -> int:
    """Measured control temp plus high-diff heat proxy."""
    if measured_temp_c <= 0:
        return 0
    add = high_diff_temp_tighten_c(
        difficulty,
        reference_difficulty,
        start_ratio=start_ratio,
        full_ratio=full_ratio,
        max_tighten_c=max_tighten_c,
    )
    return int(measured_temp_c) + int(add)


def difficulty_lane_bias(
    planned_lanes: int,
    difficulty: int,
    reference_difficulty: int,
    *,
    # Below this fraction of reference, keep full pack.
    full_pack_ratio: float = 0.35,
    # At/above reference → 1 lane (caller already does this via plan).
) -> int:
    """
    Extra safety: as difficulty climbs toward reference, bias lanes down
    even if VRAM could still pack more. Reduces heat before reference.

    - difficulty <= ref * full_pack_ratio → full planned
    - difficulty >= ref → 1
    - linear in between
    """
    planned = max(1, int(planned_lanes))
    if planned <= 1 or reference_difficulty <= 0 or difficulty <= 0:
        return planned
    if difficulty >= reference_difficulty:
        return 1

    full_at = max(1, int(reference_difficulty * max(0.05, min(0.95, full_pack_ratio))))
    if difficulty <= full_at:
        return planned

    span = reference_difficulty - full_at
    if span <= 0:
        return 1
    t = clamp_float((difficulty - full_at) / span, 0.0, 1.0)
    raw = planned - t * (planned - 1)
    return clamp_int(int(round(raw)), 1, planned)
