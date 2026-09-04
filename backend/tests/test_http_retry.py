from app.services.http_retry import (
    compute_sleep,
    is_retryable_exception,
    is_retryable_status,
    parse_retry_after,
)


def test_retryable_status_only_retryable_codes():
    assert is_retryable_status(429)
    assert is_retryable_status(503)
    assert not is_retryable_status(400)
    assert not is_retryable_status(404)
    assert not is_retryable_status(None)


def test_parse_retry_after_delta_and_invalid():
    assert parse_retry_after({"Retry-After": "2"}) == 2.0
    assert parse_retry_after({}) is None
    assert parse_retry_after({"retry-after": "not-a-date"}) is None
    assert parse_retry_after({"Retry-After": "9999"}) == 60.0


def test_compute_sleep_respects_retry_after_floor_and_cap():
    assert compute_sleep(0, 5.0) >= 5.0
    assert compute_sleep(9, None) <= 30.0


def test_retryable_exception_by_name():
    class ConnectError(Exception):
        pass

    class ValueError_(ValueError):
        pass

    assert is_retryable_exception(ConnectError("x"))
    assert not is_retryable_exception(ValueError_("x"))
