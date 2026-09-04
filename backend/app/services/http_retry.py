"""Shared HTTP retry helper with Retry-After + jitter.

Hermetic-safe: stdlib only, no httpx import at module level.
Callers pass in status codes / headers (not response objects).
"""

from __future__ import annotations

import random
import time  # noqa: F401  (re-exported for callers; keeps stdlib-only surface)
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

# Retryable status codes (429 + gateway/server 502/503/504).
# Note: 500 is handled explicitly by callers for legacy compat
# (existing openalex 500x3 test + crossref/publisher 5xx retry).
RETRYABLE: set[int] = {429, 502, 503, 504}

# Alias for readability at call sites.
RETRYABLE_STATUS_CODES: set[int] = RETRYABLE

# Caps per spec.
RETRY_AFTER_MAX = 60.0
SLEEP_CAP = 30.0


def is_retryable_status(code: int | None) -> bool:
    """Return True iff an HTTP status code is retryable."""
    try:
        return int(code) in RETRYABLE  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False


def _get_header(headers, name: str) -> str | None:
    """Case-insensitive header lookup for dict / httpx.Headers / None."""
    if headers is None:
        return None
    try:
        # httpx.Headers.get is case-insensitive; plain dict.get is not.
        if hasattr(headers, "get"):
            val = headers.get(name)
            if val is not None:
                return val  # type: ignore[no-any-return]
            # Fall back for plain dicts with different casing.
            lower = name.lower()
            try:
                items = headers.items()  # type: ignore[union-attr]
            except Exception:
                return None
            for k, v in items:
                try:
                    if str(k).lower() == lower:
                        return v
                except Exception:
                    continue
            return None
    except Exception:
        return None
    return None


def parse_retry_after(headers) -> float | None:
    """Parse a Retry-After header value into seconds (capped at 60).

    Supports delta-seconds (int) and HTTP-date (via email.utils).
    Returns None when missing / invalid. Clamps to [0, 60].
    """
    raw = _get_header(headers, "retry-after")
    if raw is None:
        return None
    try:
        s = str(raw).strip()
    except Exception:
        return None
    if not s:
        return None
    # delta-seconds
    try:
        secs = int(s)
        if secs < 0:
            return 0.0
        return min(float(secs), RETRY_AFTER_MAX)
    except (ValueError, TypeError):
        pass
    # HTTP-date
    try:
        dt = parsedate_to_datetime(s)
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = (dt - now).total_seconds()
        if delta < 0:
            return 0.0
        return min(float(delta), RETRY_AFTER_MAX)
    except Exception:
        return None


def compute_sleep(
    attempt: int,
    retry_after: float | None,
    base: float = 1.0,
    cap: float = 30.0,
) -> float:
    """Exponential backoff with Retry-After floor and jitter.

    sleep = min(cap, max(base * 2**attempt, retry_after or 0) + uniform(0, 1))
    """
    try:
        exp = base * (2**int(attempt))
    except Exception:
        exp = base
    try:
        ra = float(retry_after) if retry_after is not None else 0.0
    except (TypeError, ValueError):
        ra = 0.0
    if ra < 0:
        ra = 0.0
    floor = exp if exp > ra else ra
    return min(float(cap), floor + random.uniform(0, 1))


def is_retryable_exception(exc: BaseException) -> bool:
    """Return True for retryable network errors (timeouts / disconnects).

    Hermetic-safe: stdlib only, name-based check so no client
    library import is needed at module level.
    """
    # Match by class/MRO name (covers hermetic / stub contexts).
    try:
        names = {c.__name__ for c in type(exc).__mro__}
    except Exception:
        return False
    retryable_names = {
        "TimeoutException",
        "ConnectTimeout",
        "ReadTimeout",
        "WriteTimeout",
        "PoolTimeout",
        "ConnectError",
    }
    return not names.isdisjoint(retryable_names)
