"""
state_manager.py
Tracks extraction progress to enable idempotent retries and seamless resume.
State is persisted as JSON so the process can be safely interrupted at any time.
"""

import json
import time
from pathlib import Path
from dataclasses import dataclass, asdict, field
from enum import Enum
from typing import Optional


class PageStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"       # already existed, skip_existing=true


@dataclass
class PageState:
    page_number: int
    status: PageStatus = PageStatus.PENDING
    attempts: int = 0
    last_attempt_at: Optional[str] = None
    error_message: Optional[str] = None
    output_file: Optional[str] = None
    tokens_used: Optional[int] = None


@dataclass
class ExtractionState:
    pdf_filename: str
    total_pages: int
    started_at: str
    last_updated_at: str
    pages: dict = field(default_factory=dict)   # page_number (str) → PageState dict

    @property
    def done_count(self) -> int:
        return sum(1 for p in self.pages.values() if p["status"] in (PageStatus.DONE, PageStatus.SKIPPED))

    @property
    def failed_count(self) -> int:
        return sum(1 for p in self.pages.values() if p["status"] == PageStatus.FAILED)

    @property
    def pending_pages(self) -> list[int]:
        return [
            int(k) for k, v in self.pages.items()
            if v["status"] in (PageStatus.PENDING, PageStatus.IN_PROGRESS)
        ]


STATE_FILE = Path("output") / ".extraction_state.json"


class StateManager:
    """
    Manages extraction state with atomic writes.
    Guarantees idempotency: if a page is already DONE, it will never be reprocessed.
    """

    def __init__(self, pdf_filename: str, total_pages: int):
        self.pdf_filename = pdf_filename
        self.total_pages = total_pages
        self.state_file = STATE_FILE
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state: ExtractionState = self._load_or_create()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_or_create(self) -> ExtractionState:
        if self.state_file.exists():
            raw = json.loads(self.state_file.read_text())
            if raw.get("pdf_filename") == self.pdf_filename:
                state = ExtractionState(
                    pdf_filename=raw["pdf_filename"],
                    total_pages=raw["total_pages"],
                    started_at=raw["started_at"],
                    last_updated_at=raw["last_updated_at"],
                    pages=raw["pages"],
                )
                print(f"  ♻️   Resuming from saved state: {state.done_count}/{state.total_pages} pages done.")
                return state
            else:
                print("  ⚠️   State file found for a different PDF. Starting fresh.")

        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        state = ExtractionState(
            pdf_filename=self.pdf_filename,
            total_pages=self.total_pages,
            started_at=now,
            last_updated_at=now,
            pages={
                str(i): asdict(PageState(page_number=i))
                for i in range(1, self.total_pages + 1)
            },
        )
        self._persist(state)
        return state

    def _persist(self, state: Optional[ExtractionState] = None) -> None:
        s = state or self._state
        s.last_updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        # Atomic write: write to temp file, then rename
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(s), indent=2))
        tmp.replace(self.state_file)

    # ------------------------------------------------------------------
    # Page lifecycle
    # ------------------------------------------------------------------

    def is_done(self, page_number: int) -> bool:
        entry = self._state.pages.get(str(page_number), {})
        return entry.get("status") in (PageStatus.DONE, PageStatus.SKIPPED)

    def mark_in_progress(self, page_number: int) -> None:
        entry = self._state.pages[str(page_number)]
        entry["status"] = PageStatus.IN_PROGRESS
        entry["attempts"] = entry.get("attempts", 0) + 1
        entry["last_attempt_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self._persist()

    def mark_done(self, page_number: int, output_file: str, tokens_used: int = 0) -> None:
        entry = self._state.pages[str(page_number)]
        entry["status"] = PageStatus.DONE
        entry["output_file"] = output_file
        entry["tokens_used"] = tokens_used
        entry["error_message"] = None
        self._persist()

    def mark_skipped(self, page_number: int, output_file: str) -> None:
        entry = self._state.pages[str(page_number)]
        entry["status"] = PageStatus.SKIPPED
        entry["output_file"] = output_file
        self._persist()

    def mark_failed(self, page_number: int, error: str) -> None:
        entry = self._state.pages[str(page_number)]
        entry["status"] = PageStatus.FAILED
        entry["error_message"] = error
        self._persist()

    def get_attempts(self, page_number: int) -> int:
        return self._state.pages.get(str(page_number), {}).get("attempts", 0)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> dict:
        counts = {s: 0 for s in PageStatus}
        for entry in self._state.pages.values():
            counts[entry["status"]] += 1
        total_tokens = sum(
            e.get("tokens_used", 0) or 0 for e in self._state.pages.values()
        )
        return {
            "total": self._state.total_pages,
            "done": counts[PageStatus.DONE],
            "skipped": counts[PageStatus.SKIPPED],
            "failed": counts[PageStatus.FAILED],
            "pending": counts[PageStatus.PENDING],
            "in_progress": counts[PageStatus.IN_PROGRESS],
            "total_tokens_used": total_tokens,
            "started_at": self._state.started_at,
            "last_updated_at": self._state.last_updated_at,
        }

    def failed_pages(self) -> list[int]:
        return [
            int(k) for k, v in self._state.pages.items()
            if v["status"] == PageStatus.FAILED
        ]
