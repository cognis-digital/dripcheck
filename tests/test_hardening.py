"""Hardening tests for DRIPCHECK — edge cases, bad input, and error paths."""
from __future__ import annotations

import io
import json

import pytest

from dripcheck.core import (
    _coerce_emails,
    lint_sequence,
    load_sequence,
    loads_sequence,
)
from dripcheck.cli import main


# ---------------------------------------------------------------------------
# loads_sequence — empty / whitespace input
# ---------------------------------------------------------------------------

def test_loads_sequence_empty_string_raises():
    with pytest.raises(ValueError, match="empty"):
        loads_sequence("")


def test_loads_sequence_whitespace_only_raises():
    with pytest.raises(ValueError, match="empty"):
        loads_sequence("   \n\t  ")


def test_loads_sequence_invalid_json_raises():
    with pytest.raises(json.JSONDecodeError):
        loads_sequence("{not valid json")


# ---------------------------------------------------------------------------
# _coerce_emails — structural edge cases
# ---------------------------------------------------------------------------

def test_coerce_emails_non_list_sequence_key_raises():
    """If 'emails' key exists but is not a list, raise ValueError."""
    with pytest.raises(ValueError, match="array"):
        _coerce_emails({"emails": "not-a-list"})


def test_coerce_emails_non_dict_item_raises():
    """Items that are not dicts (e.g. strings in the array) raise ValueError."""
    with pytest.raises(ValueError, match="JSON object"):
        _coerce_emails(["string-not-a-dict"])


def test_coerce_emails_null_item_raises():
    """null items inside the array raise a clear ValueError."""
    with pytest.raises(ValueError, match="JSON object"):
        _coerce_emails([None])


def test_coerce_emails_integer_top_level_raises():
    """A bare integer (not list or dict) raises ValueError."""
    with pytest.raises(ValueError, match="Unsupported sequence format"):
        _coerce_emails(42)


# ---------------------------------------------------------------------------
# load_sequence — file system errors
# ---------------------------------------------------------------------------

def test_load_sequence_missing_file_raises(tmp_path):
    missing = tmp_path / "no_such_file.json"
    with pytest.raises(FileNotFoundError):
        load_sequence(str(missing))


def test_load_sequence_directory_raises(tmp_path):
    with pytest.raises(IsADirectoryError):
        load_sequence(str(tmp_path))


def test_load_sequence_malformed_json_raises(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{broken", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_sequence(str(bad))


# ---------------------------------------------------------------------------
# lint_sequence — edge cases
# ---------------------------------------------------------------------------

def test_lint_sequence_empty_list_produces_error():
    report = lint_sequence([])
    assert report.failed
    codes = {f.code for f in report.sequence_findings}
    assert "empty-sequence" in codes


def test_lint_sequence_single_valid_email():
    email = {
        "id": "t1",
        "subject": "Monthly update",
        "body": (
            "Here is our regular update. You can unsubscribe here. "
            "Acme Inc, 123 Main Street, Austin, TX 78701"
        ),
    }
    report = lint_sequence([email])
    assert not report.failed


# ---------------------------------------------------------------------------
# CLI — bad input paths
# ---------------------------------------------------------------------------

def test_cli_missing_file_exits_2(capsys):
    rc = main(["lint", "/no/such/path/sequence.json"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "file not found" in err.lower() or "error" in err.lower()


def test_cli_malformed_json_exits_2(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{this is not json}", encoding="utf-8")
    rc = main(["lint", str(bad)])
    assert rc == 2
    err = capsys.readouterr().err
    assert "error" in err.lower()


def test_cli_directory_as_path_exits_2(tmp_path, capsys):
    rc = main(["lint", str(tmp_path)])
    assert rc == 2
    err = capsys.readouterr().err
    assert "error" in err.lower()


def test_cli_empty_stdin_exits_2(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    rc = main(["lint", "-"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "error" in err.lower()


def test_cli_no_subcommand_exits_2(capsys):
    rc = main([])
    assert rc == 2


# ---------------------------------------------------------------------------
# mcp_server — importable after fix
# ---------------------------------------------------------------------------

def test_mcp_server_importable():
    """mcp_server must import cleanly (the broken scan/to_json import is fixed)."""
    import dripcheck.mcp_server  # noqa: F401 — import must not raise
    assert True
