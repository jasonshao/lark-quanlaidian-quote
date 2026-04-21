"""Shared fixtures: spin up mock server for the duration of the session."""

import os
import subprocess
import sys
import time

import pytest
import requests


@pytest.fixture(scope="session")
def mock_server():
    """Start examples/mock_server.py on port 8765 for the test session."""
    env = os.environ.copy()
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn",
         "examples.mock_server:app",
         "--host", "127.0.0.1", "--port", "8765"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # Wait for readiness
    for _ in range(50):
        try:
            if requests.get("http://127.0.0.1:8765/health", timeout=1).status_code == 200:
                break
        except requests.RequestException:
            time.sleep(0.1)
    else:
        proc.kill()
        raise RuntimeError("mock server did not start in 5s")
    yield "http://127.0.0.1:8765"
    proc.kill()
    proc.wait(timeout=5)
