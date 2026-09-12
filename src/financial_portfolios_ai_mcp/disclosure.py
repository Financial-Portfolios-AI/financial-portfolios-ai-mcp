"""Canonical regulatory disclosure text.

`DISCLAIMER` is the portal's constant verbatim (`app/schemas/v1.py`, ADR-0161). Both
surfaces must cite identical wording, so it is defined once here and imported
everywhere rather than retyped - it previously existed in three slightly different
forms across tools, resources and prompts.

`SERVICE_DESCRIPTION` is the human-facing blurb a provider directory shows next to
the listing. It carries the disclosure because `instructions` (where the full
notice lives) is read by the model, not by a person browsing a directory.
"""

DISCLAIMER = (
    "Informational and educational purposes only. Not investment, legal, or tax advice, "
    "and not a recommendation or solicitation. No suitability assessment has been performed. "
    "All outputs represent mathematical target-model alignment arithmetic."
)

# Prompt bodies prefix the same notice with a label so it reads as a disclaimer
# inside generated text.
DISCLAIMER_TEXT = f"DISCLAIMER: {DISCLAIMER}"

SERVICE_DESCRIPTION = (
    "Research systematic, AI-driven model portfolios: target allocations, holdings history, "
    "model-alignment arithmetic, and quantitative market research. Subscribers see their live "
    "book; non-subscribers see the public book delayed by about 45 days. " + DISCLAIMER
)
