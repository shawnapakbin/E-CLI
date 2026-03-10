"""Tests for utility logging and module entrypoint."""

from e_cli.logging import buildLogRecord


def test_build_log_record_contains_event() -> None:
    """Ensures log record serialization includes event and payload fields."""

    record = buildLogRecord("test.event", {"k": "v"})
    assert "test.event" in record
    assert "\"k\": \"v\"" in record


def test_main_module_imports() -> None:
    """Ensures module entrypoint can be imported safely."""

    import e_cli.__main__ as mainModule

    assert mainModule is not None
