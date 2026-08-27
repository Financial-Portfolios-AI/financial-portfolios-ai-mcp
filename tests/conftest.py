"""Test fixtures for Financial Portfolios AI MCP Server tests."""

from datetime import datetime, timezone

import pytest
from financial_portfolios_ai.models import (
    APITokenInfo,
    BlogPost,
    BlogPostListResponse,
    BlogPostSummary,
    PortfolioHistoryResponse,
    PortfolioListResponse,
    PortfolioSnapshot,
    PortfolioSummary,
    Position,
    RebalanceOrder,
    RebalanceResult,
)


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    """Set default test environment variables."""
    monkeypatch.setenv("FINANCIAL_PORTFOLIOS_BASE_URL", "https://test.financial-portfolios.ai")
    monkeypatch.setenv("FINANCIAL_PORTFOLIOS_API_TOKEN", "aqat_v1_testsecretkey1234567890abcdef")


@pytest.fixture
def mock_portfolio_list():
    return PortfolioListResponse(
        total=2,
        portfolios=[
            PortfolioSummary(
                code="AQA_AGGRESSIVE",
                product_name="Aggressive Growth Portfolio",
                product_description="High-growth algorithmic equity strategy",
                risk_level="High",
                theme="Momentum & Growth",
            ),
            PortfolioSummary(
                code="AQA_BALANCED",
                product_name="Balanced Growth & Income",
                product_description="Diversified multi-asset strategy",
                risk_level="Moderate",
                theme="Balanced Quality",
            ),
        ],
    )


@pytest.fixture
def mock_portfolio_snapshot():
    return PortfolioSnapshot(
        portfolio_code="AQA_AGGRESSIVE",
        date=datetime(2026, 8, 20, 0, 0, 0, tzinfo=timezone.utc),
        model_version="v2.4.1",
        equity_exposure=0.92,
        cash_allocation=0.08,
        effective_n=14.2,
        total_positions=2,
        positions=[
            Position(
                ticker="AAPL",
                weight=0.15,
                sector="Technology",
                expected_return=0.125,
                expected_volatility=0.22,
            ),
            Position(
                ticker="NVDA",
                weight=0.20,
                sector="Technology",
                expected_return=0.182,
                expected_volatility=0.34,
            ),
        ],
    )


@pytest.fixture
def mock_portfolio_history():
    return PortfolioHistoryResponse(
        portfolio_code="AQA_AGGRESSIVE",
        days=30,
        total_snapshots=0,
        snapshots=[],
    )


@pytest.fixture
def mock_rebalance_result():
    return RebalanceResult(
        portfolio_code="AQA_AGGRESSIVE",
        snapshot_date="2026-08-20",
        total_orders=2,
        portfolio_value=10000.0,
        orders=[
            RebalanceOrder(
                ticker="NVDA",
                action="BUY",
                quantity=5.0,
                estimated_price=120.0,
                estimated_value=600.0,
                current_weight_pct=5.0,
                target_weight_pct=20.0,
                change_pct=15.0,
                notes=None,
            ),
            RebalanceOrder(
                ticker="INTC",
                action="SELL",
                quantity=10.0,
                estimated_price=30.0,
                estimated_value=300.0,
                current_weight_pct=10.0,
                target_weight_pct=0.0,
                change_pct=-10.0,
                notes=None,
            ),
        ],
        csv_raw="action,ticker,quantity,price,value\nBUY,NVDA,5,120.0,600.0\nSELL,INTC,10,30.0,300.0",
    )


@pytest.fixture
def mock_blog_posts():
    return BlogPostListResponse(
        items=[
            BlogPostSummary(
                id=1,
                title="Q3 2026 Quantitative Outlook",
                slug="q3-2026-quant-outlook",
                excerpt="Deep-dive into macroeconomic regime shifts and factor returns.",
                featured_image_url="https://financial-portfolios.ai/img1.png",
                author="Chief Investment Strategist",
                published_at=datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc),
                tags=["Macro", "Factor Investing"],
                is_gated=False,
                is_accessible=True,
            )
        ],
        total=1,
        page=1,
        page_size=10,
        total_pages=1,
    )


@pytest.fixture
def mock_single_blog_post():
    return BlogPost(
        id=1,
        title="Q3 2026 Quantitative Outlook",
        slug="q3-2026-quant-outlook",
        excerpt="Deep-dive into macroeconomic regime shifts and factor returns.",
        content="Full content here...",
        featured_image_url="https://financial-portfolios.ai/img1.png",
        author="Chief Investment Strategist",
        published_at=datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 8, 2, 12, 0, 0, tzinfo=timezone.utc),
        tags=["Macro", "Factor Investing"],
        is_gated=False,
    )


@pytest.fixture
def mock_token_info():
    return APITokenInfo(
        id="tok-1",
        name="Claude Connector Key",
        token_prefix="aqat_v1_testsec...",
        created_at=datetime(2026, 8, 1, 0, 0, 0, tzinfo=timezone.utc),
        last_used_at=datetime(2026, 8, 20, 10, 0, 0, tzinfo=timezone.utc),
        is_active=True,
    )
