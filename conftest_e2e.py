"""
conftest_e2e.py — session-scoped fixture that starts/stops the Django dev server
for Phase 6 E2E tests (Playwright).

Usage: .venv/bin/pytest tests/test_phase6_e2e.py -v -c pytest_e2e.ini --co=conftest_e2e.py
       OR set confcutdir / conftest_dirs in pytest_e2e.ini
"""
import os
import subprocess
import sys
import time
import socket
import pytest

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = os.path.join(PROJECT_DIR, ".venv", "bin", "python")
E2E_PORT = 8099


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except (ConnectionRefusedError, OSError):
            return False


@pytest.fixture(scope="session", autouse=True)
def django_server():
    """Start Django dev server once per test session, then tear it down."""
    if _port_open(E2E_PORT):
        # Already running (e.g. manually started)
        yield
        return

    env = os.environ.copy()
    env["DJANGO_SETTINGS_MODULE"] = "config.settings"

    proc = subprocess.Popen(
        [PYTHON, "manage.py", "runserver", str(E2E_PORT), "--noreload"],
        cwd=PROJECT_DIR,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait up to 20s for server to become ready
    deadline = time.time() + 20
    while time.time() < deadline:
        if _port_open(E2E_PORT):
            break
        time.sleep(0.5)
    else:
        proc.terminate()
        raise RuntimeError(f"Django dev server did not start on port {E2E_PORT} within 20s")

    yield

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
