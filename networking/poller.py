"""Background difficulty poller — keeps network checks off the mining hot path."""

from __future__ import annotations

import threading
import time

from core.models import NetworkStatus
from networking.difficulty import fetch_difficulty


class NetworkPoller:
    def __init__(
        self,
        url: str,
        *,
        poll_interval_s: float = 15.0,
        down_poll_interval_s: float = 30.0,
        timeout_s: float = 3.0,
    ) -> None:
        self._url = url
        self._poll_interval_s = max(5.0, poll_interval_s)
        self._down_poll_interval_s = max(self._poll_interval_s, down_poll_interval_s)
        self._timeout_s = max(1.0, timeout_s)
        self._lock = threading.Lock()
        self._status = NetworkStatus(
            port80_up=False,
            difficulty=None,
            latency_ms=None,
            error="starting",
        )
        self._last_poll_at = 0.0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._initial_timeout_s = self._timeout_s

    def poll_once(self, *, timeout_s: float | None = None) -> NetworkStatus:
        status = fetch_difficulty(
            self._url,
            timeout_s=int(timeout_s if timeout_s is not None else self._timeout_s),
        )
        with self._lock:
            self._status = status
            self._last_poll_at = time.time()
        return status

    def get_status(self) -> NetworkStatus:
        with self._lock:
            return NetworkStatus(
                port80_up=self._status.port80_up,
                difficulty=self._status.difficulty,
                latency_ms=self._status.latency_ms,
                error=self._status.error,
            )

    @property
    def last_poll_at(self) -> float:
        with self._lock:
            return self._last_poll_at

    def start(self, *, initial_timeout_s: float | None = None) -> NetworkStatus:
        """
        Start background polling without blocking the miner UI/CUDA path.

        Returns the current (possibly empty) status immediately. The first real
        GET runs on the poller thread so a slow xenblocks.io:80 timeout cannot
        freeze the dashboard on \"Connecting...\".
        """
        if initial_timeout_s is not None:
            self._initial_timeout_s = max(1.0, float(initial_timeout_s))
        if self._thread is None or not self._thread.is_alive():
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._loop,
                name="network-poller",
                daemon=True,
            )
            self._thread.start()
        return self.get_status()

    def wait_for_difficulty(self, *, timeout_s: float = 6.0) -> NetworkStatus:
        """Briefly wait for the first background poll (does not block forever)."""
        deadline = time.time() + max(0.0, float(timeout_s))
        while time.time() < deadline:
            status = self.get_status()
            if status.difficulty is not None:
                return status
            if status.error and status.error != "starting" and self.last_poll_at > 0:
                # At least one failed attempt finished — don't stall startup.
                return status
            time.sleep(0.15)
        return self.get_status()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _loop(self) -> None:
        first = True
        while not self._stop.is_set():
            timeout = self._initial_timeout_s if first else self._timeout_s
            first = False
            status = self.poll_once(timeout_s=timeout)
            interval = (
                self._poll_interval_s
                if status.difficulty is not None
                else self._down_poll_interval_s
            )
            if self._stop.wait(interval):
                break
