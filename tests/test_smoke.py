"""Smoke tests for DRIPCHECK — import the core, run on the demo, assert behavior."""
import json
import os
import subprocess
import sys

import pytest

from dripcheck import (
    TOOL_NAME,
    TOOL_VERSION,
    lint_email,
    lint_sequence,
    load_sequence,
    SEVERITY_ERROR,
)
from dripcheck.cli import main

DEMO = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "demos", "01-basic", "sequence.json",
)


def test_exports():
    assert TOOL_NAME == "dripcheck"
    assert isinstance(TOOL_VERSION, str) and TOOL_VERSION


def test_demo_loads():
    emails = load_sequence(DEMO)
    assert len(emails) == 3
    assert emails[0]["id"] == "welcome-1"


def test_clean_email_passes():
    emails = load_sequence(DEMO)
    report = lint_email(emails[0], index=0)
    codes = {f.code for f in report.findings}
    # Clean welcome email has unsubscribe + address, so no compliance errors.
    assert "no-unsubscribe" not in codes
    assert "no-physical-address" not in codes
    assert not report.errors


def test_spammy_email_flagged():
    emails = load_sequence(DEMO)
    report = lint_email(emails[1], index=1)
    codes = {f.code for f in report.findings}
    assert "no-unsubscribe" in codes
    assert "no-physical-address" in codes
    assert "spam-words-subject" in codes
    assert "subject-all-caps" in codes
    assert "subject-punctuation" in codes
    assert any(f.severity == SEVERITY_ERROR for f in report.findings)


def test_deceptive_subject_flagged():
    emails = load_sequence(DEMO)
    report = lint_email(emails[2], index=2)
    codes = {f.code for f in report.findings}
    assert "deceptive-subject" in codes
    # followup-3 has an opt-out link, so unsubscribe should NOT be flagged.
    assert "no-unsubscribe" not in codes


def test_sequence_fails_overall():
    emails = load_sequence(DEMO)
    report = lint_sequence(emails)
    assert report.failed is True
    assert report.error_count > 0
    d = report.to_dict()
    assert d["summary"]["failed"] is True
    assert d["summary"]["emails"] == 3


def test_unsubscribe_detection_variants():
    base_addr = "Acme Inc, 123 Main Street, Austin, TX 78701"
    for body in [
        f"hello world this is content. unsubscribe here. {base_addr}",
        f"hello world this is content. you may opt-out anytime. {base_addr}",
        f"hello world this is content. manage your preferences. {base_addr}",
    ]:
        report = lint_email({"subject": "hi friend", "body": body})
        codes = {f.code for f in report.findings}
        assert "no-unsubscribe" not in codes


def test_empty_sequence_is_error():
    report = lint_sequence([])
    assert report.failed is True
    assert any(f.code == "empty-sequence" for f in report.sequence_findings)


def test_cli_returns_nonzero_on_findings(capsys):
    rc = main(["lint", DEMO])
    assert rc == 1
    out = capsys.readouterr().out
    assert "DRIPCHECK report" in out
    assert "FAIL" in out


def test_cli_json_format(capsys):
    rc = main(["lint", DEMO, "--format", "json"])
    assert rc == 1
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["tool"] == "dripcheck"
    assert data["summary"]["failed"] is True


def test_cli_clean_sequence_passes(tmp_path, capsys):
    clean = [{
        "id": "only",
        "subject": "A normal newsletter update",
        "body": (
            "Here is our regular monthly update with helpful content for "
            "readers. To stop these, you can unsubscribe here. "
            "Acme Inc, 123 Main Street, Austin, TX 78701"
        ),
    }]
    p = tmp_path / "clean.json"
    p.write_text(json.dumps(clean), encoding="utf-8")
    rc = main(["lint", str(p)])
    assert rc == 0
    assert "PASS" in capsys.readouterr().out


def test_sarif_export_shape():
    from dripcheck.core import to_sarif
    emails = load_sequence(DEMO)
    report = lint_sequence(emails)
    sarif = to_sarif(report)
    assert sarif["version"] == "2.1.0"
    run = sarif["runs"][0]
    assert run["tool"]["driver"]["name"] == "dripcheck"
    # every result references a registered rule
    rule_ids = {r["id"] for r in run["tool"]["driver"]["rules"]}
    assert rule_ids
    for res in run["results"]:
        assert res["ruleId"] in rule_ids
        assert res["level"] in {"error", "warning", "note"}
        assert res["locations"][0]["logicalLocations"][0]["name"]


def test_csv_export_has_header_and_rows():
    import csv as _csv
    import io as _io
    from dripcheck.core import to_csv
    emails = load_sequence(DEMO)
    report = lint_sequence(emails)
    text = to_csv(report)
    rows = list(_csv.DictReader(_io.StringIO(text)))
    assert rows, "expected at least one finding row"
    assert set(rows[0]) >= {"email_id", "subject", "severity", "code", "message"}
    assert any(r["code"] == "no-unsubscribe" for r in rows)


def test_cli_sarif_and_csv_formats(capsys):
    rc = main(["lint", DEMO, "--format", "sarif"])
    assert rc == 1
    data = json.loads(capsys.readouterr().out)
    assert data["runs"][0]["tool"]["driver"]["name"] == "dripcheck"
    rc = main(["lint", DEMO, "--format", "csv"])
    assert rc == 1
    out = capsys.readouterr().out
    assert out.splitlines()[0].startswith("email_id,subject,severity,code,message")


def test_international_address_detected():
    # Non-US footers should satisfy the physical-address requirement.
    for footer in [
        "EnergyEU SARL, 12 Rue de la Loi, 1040 Brussels, Belgium",
        "Beispiel GmbH, Bahnhofstrasse 5, 8001 Zurich, Switzerland",
        "Ejemplo SL, Calle Mayor 10, 28013 Madrid, Spain",
    ]:
        body = ("Hello, here is some genuine newsletter content for readers. "
                "You can unsubscribe anytime. " + footer)
        report = lint_email({"subject": "Monthly update", "body": body})
        codes = {f.code for f in report.findings}
        assert "no-physical-address" not in codes, footer


def test_demos_lint_without_error():
    """Every shipped demo must parse and lint (no crash, exit 0 or 1)."""
    demos_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "demos")
    seqs = []
    for name in sorted(os.listdir(demos_dir)):
        p = os.path.join(demos_dir, name, "sequence.json")
        if os.path.isfile(p):
            seqs.append(p)
    assert len(seqs) >= 8, "expected the full demo set to be present"
    for p in seqs:
        emails = load_sequence(p)
        report = lint_sequence(emails)
        # to_dict / exporters must all succeed on real demo data
        assert report.to_dict()["tool"] == "dripcheck"


def test_module_entrypoint_runs():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    proc = subprocess.run(
        [sys.executable, "-m", "dripcheck", "--version"],
        cwd=root, capture_output=True, text=True,
    )
    assert proc.returncode == 0
    assert "dripcheck" in proc.stdout.lower()
