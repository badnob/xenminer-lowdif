from __future__ import annotations

import json
import time
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from core.models import GpuSnapshot, MiningStats

_SPARK = "▁▂▃▄▅▆▇█"
_HOUR_S = 3600.0


@dataclass
class TimelapseSample:
    elapsed_s: int
    hps: float
    vram_mib: int
    temp_c: int
    pending: int
    accepted: int
    network_ok: bool
    wall_ts: float = 0.0


@dataclass
class TimelapseEvent:
    elapsed_s: int
    clock: str
    label: str


class SessionTimelapse:
    """Rolling session timeline: elapsed time, H/s sparkline, milestones."""

    def __init__(
        self,
        log_path: Path,
        *,
        sample_interval_s: float = 30.0,
        max_samples: int | None = None,
        max_events: int = 10,
        window_s: float = _HOUR_S,
    ) -> None:
        self.log_path = log_path
        self.sample_interval_s = max(1.0, float(sample_interval_s))
        self.window_s = max(self.sample_interval_s, float(window_s))
        if max_samples is None:
            max_samples = int(self.window_s / self.sample_interval_s) + 8
        self._started = time.time()
        self._last_sample_at = 0.0
        self._last_network_ok: bool | None = None
        self._online_s = 0.0
        self._offline_s = 0.0
        self._last_state_at = self._started
        self._samples: deque[TimelapseSample] = deque(maxlen=max(16, max_samples))
        self._events: deque[TimelapseEvent] = deque(maxlen=max_events)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._append_log(
            {
                "type": "session_start",
                "at": datetime.now().isoformat(timespec="seconds"),
            }
        )

    def elapsed_s(self) -> int:
        return max(0, int(time.time() - self._started))

    def format_elapsed(self) -> str:
        total = self.elapsed_s()
        hours, rem = divmod(total, 3600)
        minutes, seconds = divmod(rem, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def _append_log(self, record: dict) -> None:
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    def _track_network(self, network_ok: bool) -> None:
        now = time.time()
        elapsed = now - self._last_state_at
        if self._last_network_ok is not None:
            if self._last_network_ok:
                self._online_s += elapsed
            else:
                self._offline_s += elapsed
            if self._last_network_ok != network_ok:
                label = "NET online" if network_ok else "NET offline"
                self.record_event(label)
        self._last_network_ok = network_ok
        self._last_state_at = now

    def record_event(self, label: str) -> None:
        event = TimelapseEvent(
            elapsed_s=self.elapsed_s(),
            clock=datetime.now().strftime("%H:%M:%S"),
            label=label,
        )
        self._events.appendleft(event)
        self._append_log({"type": "event", **asdict(event)})

    def maybe_sample(
        self,
        stats: MiningStats,
        gpu: GpuSnapshot | None,
        *,
        pending: int,
        network_ok: bool,
    ) -> None:
        self._track_network(network_ok)
        now = time.time()
        if now - self._last_sample_at < self.sample_interval_s:
            return
        self._last_sample_at = now
        sample = TimelapseSample(
            elapsed_s=self.elapsed_s(),
            hps=max(0.0, float(stats.hps_ema)),
            vram_mib=gpu.used_mib if gpu else 0,
            temp_c=gpu.temperature_c if gpu else 0,
            pending=pending,
            accepted=stats.accepted_total,
            network_ok=network_ok,
            wall_ts=now,
        )
        self._samples.append(sample)
        self._append_log({"type": "sample", **asdict(sample)})

    def _sample_wall_ts(self, sample: TimelapseSample) -> float:
        if sample.wall_ts > 0:
            return sample.wall_ts
        return self._started + float(sample.elapsed_s)

    def _window_samples(self, *, now: float | None = None) -> list[TimelapseSample]:
        now = now if now is not None else time.time()
        cutoff = now - self.window_s
        # Keep zero H/s samples so gaps stay honest (warmup / pause).
        return [
            sample
            for sample in self._samples
            if self._sample_wall_ts(sample) >= cutoff
        ]

    def _effective_window_s(self, *, now: float) -> float:
        """Grow with the session until a full hour of history exists."""
        age = max(self.sample_interval_s, now - self._started)
        return min(self.window_s, age)

    def _bucket_values(
        self,
        samples: list[TimelapseSample],
        *,
        width: int,
        now: float,
    ) -> list[float | None]:
        """
        Map samples onto fixed-width timeline (left=oldest, right=now).

        Empty buckets stay empty (no long carry-forward plateaus — that made
        the chart look like a solid block or a weird step).
        """
        if width <= 0:
            return []
        eff_window = self._effective_window_s(now=now)
        window_start = now - eff_window
        buckets: list[list[float]] = [[] for _ in range(width)]
        for sample in samples:
            ts = self._sample_wall_ts(sample)
            if ts < window_start - 1e-6:
                continue
            rel = (ts - window_start) / eff_window if eff_window > 0 else 1.0
            idx = min(width - 1, max(0, int(rel * width)))
            buckets[idx].append(max(0.0, float(sample.hps)))

        values: list[float | None] = [None] * width
        for i, bucket in enumerate(buckets):
            if bucket:
                values[i] = sum(bucket) / len(bucket)
        return values

    def sparkline(self, width: int = 48, *, now: float | None = None) -> str:
        now = now if now is not None else time.time()
        samples = self._window_samples(now=now)
        if not samples:
            return "·" * max(1, width)

        values = self._bucket_values(samples, width=width, now=now)
        present = [v for v in values if v is not None]
        if not present:
            return "·" * width

        # Absolute scale from 0 → peak so the shape matches real H/s, not
        # min–max stretch that turns noise into a full-height mess.
        hi = max(present)
        if hi <= 0:
            return "".join("▁" if v is not None else "·" for v in values)

        out: list[str] = []
        n = len(_SPARK) - 1
        for value in values:
            if value is None:
                out.append("·")
                continue
            # Map 0..hi onto spark glyphs; tiny rates still show ▁.
            idx = int(round((value / hi) * n))
            idx = max(0, min(n, idx))
            if value > 0 and idx == 0:
                idx = 1
            out.append(_SPARK[idx])
        return "".join(out)

    def average_hps(self, *, now: float | None = None) -> float:
        samples = self._window_samples(now=now)
        live = [s.hps for s in samples if s.hps > 0]
        if not live:
            return 0.0
        return sum(live) / len(live)

    def format_uptime_split(self, network_ok: bool) -> str:
        self._track_network(network_ok)
        online = int(self._online_s)
        offline = int(self._offline_s)
        return f"online {self._fmt_duration(online)}  offline {self._fmt_duration(offline)}"

    def _fmt_duration(self, seconds: int) -> str:
        hours, rem = divmod(seconds, 3600)
        minutes, secs = divmod(rem, 60)
        if hours:
            return f"{hours}h{minutes:02d}m"
        if minutes:
            return f"{minutes}m{secs:02d}s"
        return f"{secs}s"

    def event_line(self, max_items: int = 4) -> str:
        if not self._events:
            return "No milestones yet"
        parts = [
            f"{ev.clock} {ev.label}"
            for ev in list(self._events)[:max_items]
        ]
        return " · ".join(parts)

    def finalize(self) -> None:
        if self._last_network_ok is not None:
            now = time.time()
            elapsed = now - self._last_state_at
            if self._last_network_ok:
                self._online_s += elapsed
            else:
                self._offline_s += elapsed
            self._last_state_at = now
        self._append_log(
            {
                "type": "session_end",
                "at": datetime.now().isoformat(timespec="seconds"),
                "elapsed_s": self.elapsed_s(),
                "online_s": int(self._online_s),
                "offline_s": int(self._offline_s),
                "accepted": self._samples[-1].accepted if self._samples else 0,
            }
        )
