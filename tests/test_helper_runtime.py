"""Tests for bundled helper runtime CLI commands (status/start/stop)."""

import pytest
from e_cli.cli import helper_status, helper_start, helper_stop

def test_helper_status(monkeypatch):
    class FakeRuntime:
        def status(self):
            return "running"
    monkeypatch.setattr("e_cli.cli.BundledRuntime", lambda: FakeRuntime())
    results = []
    monkeypatch.setattr("e_cli.cli.printInfo", lambda m: results.append(m))
    helper_status()
    assert any("running" in m for m in results)

def test_helper_start(monkeypatch):
    class FakeRuntime:
        def start(self):
            return True
    monkeypatch.setattr("e_cli.cli.BundledRuntime", lambda: FakeRuntime())
    results = []
    monkeypatch.setattr("e_cli.cli.printInfo", lambda m: results.append(m))
    monkeypatch.setattr("e_cli.cli.printError", lambda m: results.append(m))
    helper_start()
    assert any("started" in m for m in results)

def test_helper_stop(monkeypatch):
    class FakeRuntime:
        def stop(self):
            return True
    monkeypatch.setattr("e_cli.cli.BundledRuntime", lambda: FakeRuntime())
    results = []
    monkeypatch.setattr("e_cli.cli.printInfo", lambda m: results.append(m))
    monkeypatch.setattr("e_cli.cli.printError", lambda m: results.append(m))
    helper_stop()
    assert any("stopped" in m for m in results)
