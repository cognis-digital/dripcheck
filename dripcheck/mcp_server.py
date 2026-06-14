"""DRIPCHECK MCP server — exposes lint() as an MCP tool for Cognis.Studio."""
from __future__ import annotations

import json

from dripcheck.core import lint_sequence, loads_sequence


def serve() -> int:
    """Start an MCP stdio server. Requires the optional 'mcp' extra:
        pip install "cognis-dripcheck[mcp]"
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception:
        print("Install the MCP extra: pip install 'cognis-dripcheck[mcp]'")
        return 1
    app = FastMCP("dripcheck")

    @app.tool()
    def dripcheck_scan(target: str) -> str:
        """Lint email sequences and drip campaigns for deliverability: SPF/DKIM/DMARC, link health, unsubscribe presence, and CAN-SPAM/GDPR compliance.. Returns JSON findings."""
        try:
            emails = loads_sequence(target)
        except (ValueError, json.JSONDecodeError) as exc:
            return json.dumps({"error": str(exc)})
        report = lint_sequence(emails)
        return json.dumps(report.to_dict(), indent=2)

    app.run()
    return 0
