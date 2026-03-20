"""
extractor.py
Main pipeline: PDF → images → Gemini OCR → enriched Markdown → index.json
Run with: python extractor.py
"""

import os
import io
import sys
import json
import time
import shutil
import yaml
import fitz  # PyMuPDF
import google.generativeai as genai
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional

# Local modules
sys.path.insert(0, str(Path(__file__).parent))
from quota_analyzer import run_preflight
from state_manager import StateManager
from cover_analyzer import run_cover_analysis
from math_enricher import enrich_markdown_with_math

load_dotenv()

# ──────────────────────────────────────────────
# Gemini OCR prompt  (language-aware, structured)
# ──────────────────────────────────────────────
OCR_PROMPT = """
You are an expert document digitizer specializing in accounting and financial texts written in Spanish.

Analyze this book page image and extract ALL content with the following rules:

1. TEXT: Transcribe all text verbatim, preserving paragraph breaks.

2. HEADINGS: Use Markdown heading levels (# ## ###) that match the visual hierarchy.

3. STANDARD TABLES: Render as GitHub-Flavored Markdown tables with | delimiters.

4. T-ACCOUNTS (Cuentas T / Esquemas de Mayor): Render as a Markdown table with three columns:
   | **Debe** | **Cuenta: [Name]** | **Haber** |
   |---|---|---|
   | [left entries] | | [right entries] |

5. FORMULAS & EQUATIONS: Wrap inline math in backticks. E.g. `Activo = Pasivo + Capital`.

6. NUMBERED LISTS & BULLETS: Preserve using Markdown list syntax.

7. FOOTNOTES: Append at the bottom prefixed with > **Nota:**.

8. IF THE PAGE IS BLANK or ONLY contains a page number: respond with exactly: [BLANK_PAGE]

9. DO NOT add any commentary, preamble, or explanation outside the extracted content.

Output: pure Markdown only.
"""

CLAUDE_ENRICHMENT_PROMPT = """
You receive raw Markdown extracted from a scanned accounting textbook page.
Your job is to improve structure and clarity WITHOUT changing the content:
- Fix obvious OCR errors in Spanish words.
- Ensure heading hierarchy is consistent.
- Fix broken table rows.
- Do not add or remove factual content.
- Return only the improved Markdown.
"""


# ──────────────────────────────────────────────
# Configuration loader
# ──────────────────────────────────────────────

def load_config(path: str = "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


# ──────────────────────────────────────────────
# PDF → image (per page)
# ──────────────────────────────────────────────

def pdf_page_to_image_bytes(doc: fitz.Document, page_index: int, dpi: int) -> bytes:
    page = doc[page_index]
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
    return pix.tobytes("png")


# ──────────────────────────────────────────────
# Gemini OCR call (with retry)
# ──────────────────────────────────────────────

def gemini_ocr(
    model: genai.GenerativeModel,
    image_bytes: bytes,
    max_retries: int = 3,
    delay: float = 4.5,
) -> tuple[str, int]:
    """
    Sends an image to Gemini for OCR.
    Returns (markdown_text, token_count).
    Raises RuntimeError if all retries are exhausted.
    """
    from google.generativeai.types import HarmCategory, HarmBlockThreshold

    image_part = {"mime_type": "image/png", "data": image_bytes}

    for attempt in range(1, max_retries + 1):
        try:
            response = model.generate_content(
                [OCR_PROMPT, image_part],
                safety_settings={
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                },
            )
            text = response.text or ""
            token_count = getattr(response.usage_metadata, "total_token_count", 0)
            return text, token_count
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower() or "rate" in err.lower():
                wait = delay * (2 ** (attempt - 1))  # exponential backoff
                print(f"\n  ⏳  Rate limit hit. Waiting {wait:.0f}s (attempt {attempt}/{max_retries})...")
                time.sleep(wait)
            elif attempt == max_retries:
                raise RuntimeError(f"Gemini API error after {max_retries} attempts: {e}")
            else:
                time.sleep(delay)

    raise RuntimeError("Exhausted all retries.")


# ──────────────────────────────────────────────
# Optional: Claude enrichment pass
# ──────────────────────────────────────────────

def claude_enrich(markdown_text: str, model_name: str) -> str:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        msg = client.messages.create(
            model=model_name,
            max_tokens=4096,
            messages=[
                {"role": "user", "content": f"{CLAUDE_ENRICHMENT_PROMPT}\n\n---\n\n{markdown_text}"}
            ],
        )
        return msg.content[0].text
    except Exception as e:
        print(f"\n  ⚠️  Claude enrichment failed: {e}. Using raw Gemini output.")
        return markdown_text


# ──────────────────────────────────────────────
# Markdown page wrapper (adds frontmatter)
# ──────────────────────────────────────────────

def wrap_page_markdown(
    content: str,
    page_number: int,
    config: dict,
) -> str:
    book = config["input"]
    citation_lines = []
    citation_lines.append(f"**Source:** {book.get('title', 'Unknown Title')}")
    if book.get("author"):
        citation_lines.append(f"**Author:** {book['author']}")
    if book.get("year"):
        citation_lines.append(f"**Year:** {book['year']}")
    if book.get("isbn"):
        citation_lines.append(f"**ISBN:** {book['isbn']}")
    if book.get("original_url"):
        citation_lines.append(f"**Original source:** [{book['original_url']}]({book['original_url']})")

    citation_block = (
        "\n\n---\n\n> " + "  \n> ".join(citation_lines)
        if citation_lines else ""
    )

    return f"""---
page: {page_number}
source: "{book.get('title', '')}"
author: "{book.get('author', '')}"
---

{content}
{citation_block}
"""


# ──────────────────────────────────────────────
# Progress bar
# ──────────────────────────────────────────────

def print_progress(current: int, total: int, page_num: int, status: str = "") -> None:
    pct = current / total if total else 0
    bar_len = 35
    filled = int(bar_len * pct)
    bar = "█" * filled + "░" * (bar_len - filled)
    pct_str = f"{pct * 100:5.1f}%"
    suffix = f" {status}" if status else ""
    print(f"\r  [{bar}] {pct_str}  Page {page_num}/{total}{suffix}   ", end="", flush=True)


# ──────────────────────────────────────────────
# Index builder
# ──────────────────────────────────────────────

def build_index(pages_dir: Path, config: dict, theme: dict) -> dict:
    """Scans generated .md files and builds index.json for the viewer."""
    entries = []
    for md_file in sorted(pages_dir.glob("page_*.md")):
        page_num = int(md_file.stem.replace("page_", ""))
        text_preview = md_file.read_text()[:200].replace("\n", " ").strip()
        entries.append({
            "page": page_num,
            "file": f"pages/{md_file.name}",
            "preview": text_preview,
        })

    index = {
        "title": config["input"].get("title", "Untitled"),
        "author": config["input"].get("author", ""),
        "year": config["input"].get("year", ""),
        "isbn": config["input"].get("isbn", ""),
        "original_url": config["input"].get("original_url", ""),
        "total_pages": len(entries),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "theme": theme,
        "pages": entries,
    }
    return index


# ──────────────────────────────────────────────
# Main pipeline
# ──────────────────────────────────────────────

def main():
    print("\n" + "=" * 60)
    print("  📖  PDF → LLM Context Extractor")
    print("=" * 60)

    # 1. Load config
    config = load_config("config.yaml")
    pdf_filename = config["input"]["pdf_filename"]
    pdf_path = Path("input") / pdf_filename
    output_dir = Path(config["output"]["pages_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    # 2. Pre-flight quota check
    proceed, quota_report = run_preflight("config.yaml")
    if not proceed:
        sys.exit(0)

    # 3. Cover analysis & theme extraction
    root_output = output_dir.parent
    theme = run_cover_analysis(pdf_path, root_output, config.get("theme", {}))

    # 4. Initialize Gemini
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("\n  ❌  GEMINI_API_KEY not set. Add it to your .env file.\n")
        sys.exit(1)
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(config["ai"]["ocr_model"])

    # 5. Open PDF
    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)
    dpi = config["processing"]["dpi"]
    delay = config["processing"]["rate_limit_delay"]
    max_retries = config["processing"]["max_retries"]
    skip_existing = config["processing"]["skip_existing"]

    # 6. Determine page range
    page_range = config["processing"].get("page_range")
    if page_range:
        start_page, end_page = max(1, page_range[0]), min(total_pages, page_range[1])
    else:
        start_page, end_page = 1, total_pages
    pages_to_process = list(range(start_page, end_page + 1))

    # 7. State manager (resume + idempotency)
    state = StateManager(pdf_filename=pdf_filename, total_pages=total_pages)

    # 8. Process pages
    print(f"\n  🔄  Processing pages {start_page}–{end_page} of {total_pages}...\n")
    processed = 0
    failed_pages = []

    enable_claude = config["ai"].get("enable_claude_enrichment", False)
    claude_model = config["ai"].get("claude_model", "claude-sonnet-4-20250514")
    enable_wolfram = config["ai"].get("enable_wolfram_math", False)

    for i, page_num in enumerate(pages_to_process):
        output_file = output_dir / f"page_{page_num:04d}.md"

        # Skip if already done
        if skip_existing and state.is_done(page_num):
            print_progress(i + 1, len(pages_to_process), page_num, "⏭ skipped")
            state.mark_skipped(page_num, str(output_file))
            continue

        # Check max retries
        if state.get_attempts(page_num) >= max_retries:
            print_progress(i + 1, len(pages_to_process), page_num, "❌ max retries")
            failed_pages.append(page_num)
            continue

        state.mark_in_progress(page_num)
        print_progress(i + 1, len(pages_to_process), page_num, "🔍 extracting")

        try:
            # PDF page → PNG bytes
            img_bytes = pdf_page_to_image_bytes(doc, page_num - 1, dpi)

            # Gemini OCR
            raw_md, tokens = gemini_ocr(model, img_bytes, max_retries=max_retries, delay=delay)

            # Skip blank pages
            if raw_md.strip() == "[BLANK_PAGE]":
                output_file.write_text(f"<!-- Page {page_num}: blank -->\n")
                state.mark_done(page_num, str(output_file), tokens)
                print_progress(i + 1, len(pages_to_process), page_num, "⬜ blank")
                time.sleep(delay)
                continue

            # Optional: Claude enrichment pass
            if enable_claude:
                raw_md = claude_enrich(raw_md, claude_model)

            # Optional: Math enrichment via Wolfram
            if enable_wolfram:
                raw_md = enrich_markdown_with_math(raw_md, enable_wolfram=True)

            # Wrap with citation frontmatter
            final_md = wrap_page_markdown(raw_md, page_num, config)
            output_file.write_text(final_md, encoding="utf-8")

            state.mark_done(page_num, str(output_file), tokens)
            processed += 1
            print_progress(i + 1, len(pages_to_process), page_num, "✅ done")

        except Exception as e:
            state.mark_failed(page_num, str(e))
            failed_pages.append(page_num)
            print_progress(i + 1, len(pages_to_process), page_num, f"⚠️  error")

        time.sleep(delay)

    doc.close()

    # 9. Build index.json
    print(f"\n\n  📋  Building index.json...")
    index = build_index(output_dir, config, theme)
    index_path = output_dir.parent / "index.json"
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False))
    print(f"  ✅  index.json → {index_path}")

    # 10. Sync to viewer if configured
    if config["output"].get("sync_to_viewer"):
        viewer_dir = Path(config["output"]["viewer_public_dir"])
        viewer_dir.mkdir(parents=True, exist_ok=True)
        for md_file in output_dir.glob("*.md"):
            shutil.copy(md_file, viewer_dir / md_file.name)
        shutil.copy(index_path, viewer_dir.parent / "index.json")
        # Copy theme and cover
        for extra in ["theme.json", "cover.png"]:
            src = output_dir.parent / extra
            if src.exists():
                shutil.copy(src, viewer_dir.parent / extra)
        print(f"  🚀  Output synced → {viewer_dir.parent}")

    # 11. Summary
    summary = state.summary()
    print("\n" + "=" * 60)
    print("  📊  EXTRACTION COMPLETE")
    print("=" * 60)
    print(f"  ✅  Done      : {summary['done']}")
    print(f"  ⏭️   Skipped   : {summary['skipped']}")
    print(f"  ❌  Failed    : {summary['failed']}")
    print(f"  🔢  Tokens    : ~{summary['total_tokens_used']:,}")
    if failed_pages:
        print(f"\n  Failed pages: {failed_pages}")
        print("  Run the script again — failed pages will be retried automatically.")
    print()


if __name__ == "__main__":
    main()
