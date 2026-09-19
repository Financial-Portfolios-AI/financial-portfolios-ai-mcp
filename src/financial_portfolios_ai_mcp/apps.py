"""Every MCP App this server ships, on one Apps extension.

An app is a `ui://` HTML resource plus the tools bound to it. They live on a single
extension because the server takes one: each app module registers itself onto the `Apps`
instance built here.

Why apps rather than prompts or elicitation, for anything that needs a choice:

* MCP prompt arguments carry only a name, title, description and required flag - there is
  no way to offer options, so a dropdown is impossible.
* Elicitation would allow one, but as of 2026-09 it is supported in Claude Code and not in
  claude.ai, Claude Desktop or Claude mobile (modelcontextprotocol/ext-apps client matrix;
  anthropics/claude-ai-mcp#153, open since April 2026). Anthropic's own MCP Apps docs point
  at an app form as the answer for "configuring with many options".
* Whether claude.ai surfaces MCP prompts to users at all is disputed - Anthropic says yes,
  an open bug report says they appear nowhere. Anything important therefore ships as a
  tool, which every host does surface.
"""

from mcp.server.apps import Apps

from financial_portfolios_ai_mcp.access_centre import register_access_centre
from financial_portfolios_ai_mcp.explorer import build_explorer
from financial_portfolios_ai_mcp.rebalance_studio import register_rebalance_studio
from financial_portfolios_ai_mcp.research_reader import register_research_reader


def build_apps() -> Apps:
    """The Apps extension carrying every app's UI resource and tools."""
    apps = build_explorer()
    register_access_centre(apps)
    register_rebalance_studio(apps)
    register_research_reader(apps)
    return apps
