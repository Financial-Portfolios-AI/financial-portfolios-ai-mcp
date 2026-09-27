"""The deployments this service runs against, defined once.

The server config, the manifest renderer, the marketplace publisher and their tests must all
agree on what "dev" and "prod" mean - a second copy is how an artifact ends up pointing at the
wrong environment. Nothing in the repository picks one by default: the target is named when
the server is deployed or run (FINANCIAL_PORTFOLIOS_ENV) and when artifacts are published
(`--env`).
"""

ENVIRONMENTS = {
    "prod": "https://financial-portfolios.ai",
    "dev": "https://dev.financial-portfolios.ai",
}
