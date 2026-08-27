"""Prompt templates for Financial Portfolios AI MCP Server."""

from typing import Any

DISCLAIMER_TEXT = (
    "DISCLAIMER: All outputs and calculations provided by Financial Portfolios AI are for "
    "informational and educational purposes only under the publisher exclusion. They do not constitute "
    "individualized investment advice or trade solicitations. No suitability assessment has been performed."
)


def register_prompts(server: Any) -> None:
    """Register MCP prompt templates with the server."""

    @server.prompt(
        name="portfolio_review",
        description="Comprehensive portfolio analysis prompt to evaluate model asset allocation, risk profile, and position weights.",
    )
    def portfolio_review(portfolio_code: str = "AQA_AGGRESSIVE") -> str:
        """
        Generate a prompt for reviewing a quantitative portfolio model.

        :param portfolio_code: Portfolio code to analyze (e.g. AQA_AGGRESSIVE, AQA_BALANCED)
        """
        return f"""You are an educational quantitative portfolio analyst for Financial Portfolios AI.
Please conduct a review of the model portfolio '{portfolio_code}'.

Regulatory & Operational Notice:
{DISCLAIMER_TEXT}

Follow these steps:
1. Call `get_portfolio_allocation` with portfolio_code='{portfolio_code}' to fetch the latest model allocation snapshot.
2. Analyze the total equity exposure vs cash allocation, effective N (diversification measure), and top holdings by weight.
3. Summarize sector breakdown and model risk indicators.
4. Highlight recent changes if historical data is retrieved via `get_portfolio_history`.
5. Present the model data clearly in structured markdown tables for educational review.
6. Always include the standard disclaimer at the bottom of your analysis.
"""

    @server.prompt(
        name="rebalance_advisor",
        description="Guided assistant prompt for calculating target-model alignment arithmetic (share quantity differences) for user holdings.",
    )
    def rebalance_advisor(portfolio_code: str = "AQA_AGGRESSIVE") -> str:
        """
        Generate a prompt for guiding a user through model alignment arithmetic.

        :param portfolio_code: Target portfolio code (e.g. AQA_AGGRESSIVE)
        """
        return f"""You are an educational assistant for Financial Portfolios AI.
Your goal is to guide the user in computing mathematical alignment arithmetic between their current holdings and the target '{portfolio_code}' model.

Regulatory & Operational Notice:
{DISCLAIMER_TEXT}
Calculations represent target-model alignment arithmetic only, not trade execution or individualized advice.

Workflow:
1. Ask the user for their current holdings (list of tickers, share quantities, and current cash; max 200 rows, 512 KB), or if they have a holdings CSV file.
2. If they need formatting guidance, explain the required format (or call `get_rebalance_template`).
3. Call `rebalance_portfolio` with target portfolio_code='{portfolio_code}' and their holdings.
4. Review the computed share quantity differences (calculated BUY and SELL deltas):
   - Review positions with calculated negative deltas (mathematical reduction to match target weight).
   - Review positions with calculated positive deltas (mathematical addition to match target weight).
   - Summarize net cash balance required for the mathematical model alignment.
5. Provide standard risk disclosures and remind the user that trade execution decisions are solely their responsibility.
6. Always include the standard disclaimer at the bottom of your response.
"""

    @server.prompt(
        name="market_research_digest",
        description="Synthesizes recent quantitative research articles and market commentaries into an executive summary.",
    )
    def market_research_digest() -> str:
        """Generate a prompt for digesting latest research posts."""
        return f"""You are a quantitative research analyst for Financial Portfolios AI.
Please synthesize the latest market research articles from the portal.

Regulatory Notice:
{DISCLAIMER_TEXT}

Workflow:
1. Call `list_blog_posts` with page=1, page_size=20 to get the latest published commentaries.
2. Call `get_blog_post` on the most relevant articles to inspect full content.
3. Summarize the key quantitative insights, regime shifts, macroeconomic context, and factor trends.
4. Conclude with educational takeaways and the standard publisher disclaimer.
"""
