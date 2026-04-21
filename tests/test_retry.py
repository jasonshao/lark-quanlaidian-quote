import time

import pytest

from scripts.flow.retry import retry, RetryExhausted


def test_retry_succeeds_on_second_attempt():
    calls = {"n": 0}

    @retry(attempts=3, backoff=(0, 0, 0))
    def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("boom")
        return "ok"

    assert flaky() == "ok"
    assert calls["n"] == 2


def test_retry_raises_retry_exhausted_after_max():
    @retry(attempts=3, backoff=(0, 0, 0))
    def always_fails():
        raise RuntimeError("boom")

    with pytest.raises(RetryExhausted) as exc:
        always_fails()
    assert exc.value.attempts == 3
    assert "boom" in str(exc.value.last_error)


def test_retry_honors_backoff_sequence(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda s: sleeps.append(s))

    @retry(attempts=3, backoff=(1, 4, 15))
    def always_fails():
        raise RuntimeError("boom")

    with pytest.raises(RetryExhausted):
        always_fails()
    assert sleeps == [1, 4]
