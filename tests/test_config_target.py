"""The server has no built-in target: dev or prod is chosen when it is deployed or run."""

import pytest

from financial_portfolios_ai_mcp.config import Settings
from financial_portfolios_ai_mcp.environments import ENVIRONMENTS

URL_VARS = (
    "FINANCIAL_PORTFOLIOS_BASE_URL",
    "OAUTH_AUTHORIZATION_SERVER",
    "MCP_PUBLIC_URL",
    "FINANCIAL_PORTFOLIOS_ENV",
)


@pytest.fixture
def clean(monkeypatch):
    for name in URL_VARS:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_no_target_refuses_to_start(clean):
    with pytest.raises(ValueError, match="No target deployment"):
        Settings(_env_file=None)


@pytest.mark.parametrize("env", sorted(ENVIRONMENTS))
def test_naming_the_environment_sets_every_url(clean, env):
    clean.setenv("FINANCIAL_PORTFOLIOS_ENV", env)
    s = Settings(_env_file=None)
    origin = ENVIRONMENTS[env]
    assert (s.portal_base_url, s.authorization_server_url, s.public_resource_url) == (
        origin,
        origin,
        f"{origin}/mcp",
    )


def test_an_unknown_environment_is_rejected(clean):
    clean.setenv("FINANCIAL_PORTFOLIOS_ENV", "staging")
    with pytest.raises(ValueError, match="not one of"):
        Settings(_env_file=None)


def test_an_explicit_url_wins_over_the_environment(clean):
    clean.setenv("FINANCIAL_PORTFOLIOS_ENV", "dev")
    clean.setenv("MCP_PUBLIC_URL", "https://mcp.example.test/mcp")
    s = Settings(_env_file=None)
    assert s.public_resource_url == "https://mcp.example.test/mcp"
    assert s.portal_base_url == ENVIRONMENTS["dev"]
