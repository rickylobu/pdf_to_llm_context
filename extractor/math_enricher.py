"""
math_enricher.py
Detects mathematical/accounting expressions in extracted Markdown
and optionally validates/enriches them using the Wolfram Alpha API.
GeoGebra embed links are generated for renderable equations.
"""

import re
import time
import urllib.parse
import urllib.request
import json
import os
from typing import Optional


WOLFRAM_APP_ID = os.getenv("WOLFRAM_APP_ID", "")

# Patterns that suggest mathematical content worth validating
MATH_PATTERNS = [
    r"\b\d+[\+\-\×\÷\*\/]\d+",            # arithmetic expressions
    r"\b[A-Z][a-z]?\s*=\s*[\d\+\-\(\)]+", # variable assignments
    r"\$[\d,]+\.?\d*",                      # currency values
    r"\b\d+\s*%",                           # percentages
    r"(?:Debe|Haber|Activo|Pasivo)\s*[=:]\s*[\d,]+",  # accounting entries
]

MATH_REGEX = re.compile("|".join(MATH_PATTERNS), re.IGNORECASE)


def detect_math_expressions(markdown_text: str) -> list[str]:
    """Extract likely mathematical expressions from Markdown."""
    matches = MATH_REGEX.findall(markdown_text)
    return list(set(m.strip() for m in matches if len(m.strip()) > 2))


def wolfram_validate(expression: str, app_id: str, timeout: int = 5) -> Optional[str]:
    """
    Queries Wolfram Alpha Short Answers API for a given expression.
    Returns the plain text result or None on failure.
    """
    if not app_id:
        return None

    encoded = urllib.parse.quote(expression)
    url = f"https://api.wolframalpha.com/v1/result?appid={app_id}&i={encoded}&timeout={timeout}"

    try:
        with urllib.request.urlopen(url, timeout=timeout + 2) as resp:
            if resp.status == 200:
                return resp.read().decode("utf-8")
    except Exception:
        pass
    return None


def geogebra_embed_url(expression: str) -> str:
    """
    Generates a GeoGebra Classic embed URL for a mathematical expression.
    These are rendered as iframes in the React viewer.
    """
    encoded = urllib.parse.quote(expression)
    return f"https://www.geogebra.org/calculator?lang=en&expression={encoded}"


def enrich_markdown_with_math(
    markdown_text: str,
    enable_wolfram: bool = False,
    add_geogebra_links: bool = True,
) -> str:
    """
    Scans Markdown for math expressions and:
    1. Optionally validates them with Wolfram Alpha.
    2. Optionally appends GeoGebra visualization links.
    Returns enriched Markdown.
    """
    expressions = detect_math_expressions(markdown_text)
    if not expressions:
        return markdown_text

    enrichments = []

    for expr in expressions[:5]:  # cap at 5 per page to avoid rate limits
        note_parts = [f"`{expr}`"]

        if enable_wolfram and WOLFRAM_APP_ID:
            result = wolfram_validate(expr, WOLFRAM_APP_ID)
            if result:
                note_parts.append(f"= {result} *(via Wolfram Alpha)*")
            time.sleep(0.5)  # polite delay

        if add_geogebra_links:
            url = geogebra_embed_url(expr)
            note_parts.append(f"[📊 Visualize]({url})")

        enrichments.append(" — ".join(note_parts))

    if enrichments:
        block = "\n\n> **Math Notes**\n" + "\n".join(f"> - {e}" for e in enrichments)
        return markdown_text + block

    return markdown_text
