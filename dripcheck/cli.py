"""Command line interface for DRIPCHECK.

Examples
--------
  # Lint a sequence file and print a table (exits non-zero on errors):
  dripcheck lint demos/01-basic/sequence.json

  # Machine-readable output for CI / piping:
  dripcheck lint sequence.json --format json | jq .summary

  # Read from stdin:
  cat sequence.json | dripcheck lint -

  # Treat warnings as failures too (strict CI gate):
  dripcheck lint sequence.json --strict
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from . import TOOL_NAME, TOOL_VERSION
from .core import (
    SequenceReport,
    lint_sequence,
    load_sequence,
    loads_sequence,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    SEVERITY_INFO,
)

_SEV_LABEL = {
    SEVERITY_ERROR: "ERROR",
    SEVERITY_WARNING: "WARN",
    SEVERITY_INFO: "INFO",
}


def _render_table(report: SequenceReport) -> str:
    lines: List[str] = []
    lines.append("DRIPCHECK report")
    lines.append("=" * 60)
    for er in report.emails:
        subj = er.subject or "(no subject)"
        lines.append(f"\n[{er.email_id}] {subj}")
        if not er.findings:
            lines.append("  ok  no findings")
            continue
        for f in er.findings:
            label = _SEV_LABEL.get(f.severity, f.severity.upper())
            line = f"  {label:<5} {f.code}: {f.message}"
            lines.append(line)
            if f.detail:
                lines.append(f"        ↳ {f.detail}")
    if report.sequence_findings:
        lines.append("\n[sequence]")
        for f in report.sequence_findings:
            label = _SEV_LABEL.get(f.severity, f.severity.upper())
            lines.append(f"  {label:<5} {f.code}: {f.message}")
    lines.append("\n" + "-" * 60)
    lines.append(
        f"emails={len(report.emails)}  "
        f"errors={report.error_count}  warnings={report.warning_count}  "
        f"{'FAIL' if report.failed else 'PASS'}"
    )
    return "\n".join(lines)


def _read_input(path: str):
    if path == "-":
        return loads_sequence(sys.stdin.read())
    return load_sequence(path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description=(
            "Lint email drip sequences for deliverability and CAN-SPAM "
            "compliance (unsubscribe, physical address, spam triggers)."
        ),
        epilog=(
            "examples:\n"
            "  dripcheck lint sequence.json\n"
            "  dripcheck lint sequence.json --format json | jq .summary\n"
            "  cat sequence.json | dripcheck lint -\n"
            "  dripcheck lint sequence.json --strict\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version", action="version",
        version=f"{TOOL_NAME} {TOOL_VERSION}",
    )
    sub = parser.add_subparsers(dest="command")

    lint = sub.add_parser(
        "lint",
        help="Lint an email sequence file (or '-' for stdin).",
        description="Lint an email sequence JSON file for deliverability issues.",
    )
    lint.add_argument(
        "path",
        help="Path to a JSON sequence file, or '-' to read from stdin.",
    )
    lint.add_argument(
        "--format", choices=["table", "json"], default="table",
        help="Output format (default: table).",
    )
    lint.add_argument(
        "--strict", action="store_true",
        help="Exit non-zero on warnings as well as errors.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command != "lint":
        parser.print_help()
        return 2

    try:
        emails = _read_input(args.path)
    except FileNotFoundError:
        print(f"{TOOL_NAME}: error: file not found: {args.path}", file=sys.stderr)
        return 2
    except IsADirectoryError:
        print(f"{TOOL_NAME}: error: path is a directory, not a file: {args.path}", file=sys.stderr)
        return 2
    except PermissionError:
        print(f"{TOOL_NAME}: error: permission denied: {args.path}", file=sys.stderr)
        return 2
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"{TOOL_NAME}: error: could not parse sequence: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"{TOOL_NAME}: error: could not read file: {exc}", file=sys.stderr)
        return 2

    report = lint_sequence(emails)

    if args.format == "json":
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(_render_table(report))

    if report.failed:
        return 1
    if args.strict and report.warning_count > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
