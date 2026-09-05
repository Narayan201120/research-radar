"""In-memory per-IP sliding-window rate limiter (stdlib only)."""

import threading
import time


class RateLimiter:
    """Sliding 60s window. ``check`` returns retry seconds or None."""

    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> float | None:
        now = time.monotonic()
        window = 60.0
        with self._lock:
            if self.per_minute <= 0:
                return None
            hits = self._hits.setdefault(key, [])
            cutoff = now - window
            # prune entries outside the window (in place)
            # keep only timestamps newer than cutoff
            kept = [t for t in hits if t > cutoff]
            # replace list contents to keep the same list object
            del hits[:]
            hits.extend(kept)
            if len(hits) < self.per_minute:
                hits.append(now)
                return None
            oldest = hits[0]
            retry_after = (oldest + window) - now
            return max(retry_after, 0.0)

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter(60)


def clear_rate_limit() -> None:
    limiter.clear()
