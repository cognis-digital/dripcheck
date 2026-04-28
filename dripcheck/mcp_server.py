"""DRIPCHECK MCP server — exposes scan() as an MCP tool for Cognis.Studio."""
from __future__ import annotations
from dripcheck.core import scan, to_json

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
        return to_json(scan(target))

    app.run()
    return 0
