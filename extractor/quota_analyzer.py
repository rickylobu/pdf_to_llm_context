"""
quota_analyzer.py
Analyzes the PDF and estimates API quota consumption BEFORE processing starts.
Displays a clear warning if the free tier will be exceeded.
"""

import fitz  # PyMuPDF
import yaml
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


# Free tier limits (as of 2025) — update if Google changes them
GEMINI_FREE_LIMITS = {
    "gemini-1.5-flash": {
        "requests_per_minute": 15,
        "requests_per_day": 1500,
        "tokens_per_minute": 1_000_000,
        "name": "Gemini 1.5 Flash",
    },
    "gemini-1.5-pro": {
        "requests_per_minute": 2,
        "requests_per_day": 50,
        "tokens_per_minute": 32_000,
        "name": "Gemini 1.5 Pro",
    },
}

# Estimated tokens per page (image + prompt overhead)
ESTIMATED_TOKENS_PER_PAGE = 800
# Estimated processing time per page (seconds), including rate limit delay
ESTIMATED_SECONDS_PER_PAGE = 5.5  # 4.5s delay + ~1s API latency


@dataclass
class QuotaReport:
    total_pages: int
    pages_to_process: int
    model: str
    estimated_minutes: float
    estimated_tokens: int
    daily_limit: int
    fits_in_free_tier: bool
    days_needed: int
    estimated_cost_usd: Optional[float]
    warning_message: Optional[str]


def load_config(config_path: str = "config.yaml") -> dict:
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def count_pages_to_process(pdf_path: Path, config: dict) -> tuple[int, int]:
    """Returns (total_pages, pages_to_process)."""
    doc = fitz.open(str(pdf_path))
    total = len(doc)
    doc.close()

    page_range = config["processing"].get("page_range")
    if page_range:
        start, end = page_range
        to_process = min(end, total) - max(start, 1) + 1
    else:
        to_process = total

    # Subtract already-processed pages if skip_existing is enabled
    if config["processing"].get("skip_existing", True):
        output_dir = Path(config["output"]["pages_dir"])
        existing = len(list(output_dir.glob("page_*.md"))) if output_dir.exists() else 0
        to_process = max(0, to_process - existing)

    return total, to_process


def analyze_quota(config: dict, pdf_path: Path) -> QuotaReport:
    model_key = config["ai"]["ocr_model"]
    limits = GEMINI_FREE_LIMITS.get(model_key, GEMINI_FREE_LIMITS["gemini-1.5-flash"])

    total_pages, pages_to_process = count_pages_to_process(pdf_path, config)

    estimated_tokens = pages_to_process * ESTIMATED_TOKENS_PER_PAGE
    estimated_seconds = pages_to_process * ESTIMATED_SECONDS_PER_PAGE
    estimated_minutes = estimated_seconds / 60

    daily_limit = limits["requests_per_day"]
    fits_in_free_tier = pages_to_process <= daily_limit
    days_needed = max(1, -(-pages_to_process // daily_limit))  # ceiling division

    # Rough paid cost estimate (Gemini Flash: ~$0.075 per 1M input tokens for images)
    estimated_cost = None
    warning = None

    if not fits_in_free_tier:
        image_tokens = pages_to_process * 258  # Gemini image token cost approximation
        estimated_cost = round((image_tokens / 1_000_000) * 0.075, 4)
        warning = (
            f"⚠️  {pages_to_process} pages exceeds the free tier daily limit "
            f"({daily_limit} requests/day) for {limits['name']}.\n"
            f"   Options:\n"
            f"   [A] Process in {days_needed} sessions (resume is automatic).\n"
            f"   [B] Upgrade to paid tier (~${estimated_cost:.4f} USD estimated).\n"
            f"   [C] Switch to a smaller page range in config.yaml."
        )

    return QuotaReport(
        total_pages=total_pages,
        pages_to_process=pages_to_process,
        model=limits["name"],
        estimated_minutes=round(estimated_minutes, 1),
        estimated_tokens=estimated_tokens,
        daily_limit=daily_limit,
        fits_in_free_tier=fits_in_free_tier,
        days_needed=days_needed,
        estimated_cost_usd=estimated_cost,
        warning_message=warning,
    )


def print_quota_report(report: QuotaReport) -> bool:
    """Prints the quota report. Returns True if user confirms to proceed."""
    bar_length = 40
    pct = min(report.pages_to_process / report.daily_limit, 1.0)
    filled = int(bar_length * pct)
    bar = "█" * filled + "░" * (bar_length - filled)
    bar_label = f"{report.pages_to_process}/{report.daily_limit} req/day"

    print("\n" + "=" * 60)
    print("  📊  QUOTA ANALYSIS — Pre-flight Check")
    print("=" * 60)
    print(f"  Book pages       : {report.total_pages}")
    print(f"  Pages to process : {report.pages_to_process}")
    print(f"  AI model         : {report.model}")
    print(f"  Est. time        : ~{report.estimated_minutes} minutes")
    print(f"  Est. tokens      : ~{report.estimated_tokens:,}")
    print(f"\n  Free tier usage  : [{bar}] {bar_label}")

    if report.fits_in_free_tier:
        print(f"\n  ✅  Fits within the free tier. Good to go!\n")
        return True
    else:
        print(f"\n  {report.warning_message}\n")
        print("=" * 60)

        if not sys.stdin.isatty():
            # Non-interactive mode (e.g. CI) — abort
            print("  ❌  Non-interactive mode: aborting to avoid unexpected charges.")
            return False

        answer = input(
            "  Continue anyway? Processing will auto-pause after the daily limit.\n"
            "  [y] Yes, start now   [n] No, abort: "
        ).strip().lower()
        print()
        return answer == "y"


def run_preflight(config_path: str = "config.yaml") -> tuple[bool, QuotaReport]:
    """Entry point: loads config, analyzes quota, prompts user. Returns (proceed, report)."""
    config = load_config(config_path)
    pdf_filename = config["input"]["pdf_filename"]
    pdf_path = Path("input") / pdf_filename

    if not pdf_path.exists():
        print(f"\n  ❌  PDF not found: {pdf_path}")
        print(f"      Place your PDF inside the /input/ folder and update config.yaml.\n")
        sys.exit(1)

    report = analyze_quota(config, pdf_path)
    proceed = print_quota_report(report)
    return proceed, report


if __name__ == "__main__":
    proceed, report = run_preflight()
    if not proceed:
        sys.exit(0)
    print("  Proceeding with extraction...")
