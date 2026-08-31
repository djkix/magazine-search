import re

from app.models import Page
from app.services.toc import MAX_SOMMAIRE_PAGE

# A sommaire entry is almost always laid out as "Title ......... p.NN" (dot
# leaders) or, in a tabular/column layout, "Title            p.NN-MM" (a run
# of plain whitespace instead of dots) - both are covered by requiring a run
# of at least 3 dot/whitespace characters between the title and a trailing
# page reference, which is regular enough to parse without an LLM call.
_ENTRY_RE = re.compile(
    r"^(?P<title>.+?)(?:[.·…]{3,}|\s{3,})\s*(?:p\.?\s*)?"
    r"(?P<page>\d{1,4})(?:\s*[-–]\s*(?P<page_end>\d{1,4}))?\s*$",
    re.IGNORECASE,
)
# A long title sometimes wraps onto the line(s) before the one carrying the
# dot leaders/page number - accumulate a bounded number of preceding lines
# and prepend them once an entry is matched.
MAX_TITLE_CONTINUATION_LINES = 3


def extract_articles_from_ocr(pages: list[Page]) -> list[dict]:
    """Best-effort, purely local extraction of a magazine's sommaire
    (title + start page, and end page when the entry itself gives a range)
    straight from its own OCR'd text - no Gemini call, so no quota/cost and
    no dependency on the account's rate limits, unlike the previous
    Gemini-based approach. Runs synchronously right after OCR."""
    candidate_pages = [p for p in pages if p.page_number <= MAX_SOMMAIRE_PAGE and p.raw_text]
    articles: list[dict] = []
    for page in candidate_pages:
        pending: list[str] = []
        for raw_line in page.raw_text.splitlines():
            line = raw_line.strip()
            if not line:
                pending.clear()
                continue

            m = _ENTRY_RE.match(line)
            if not m:
                pending.append(line)
                if len(pending) > MAX_TITLE_CONTINUATION_LINES:
                    pending.pop(0)
                continue

            title_part = m.group("title").strip(" .·…")
            title = " ".join([*pending, title_part]).strip()
            pending.clear()

            try:
                start_page = int(m.group("page"))
            except ValueError:
                continue
            if not title or not (1 <= start_page <= 999):
                continue

            entry = {"title": title, "start_page": start_page}
            if m.group("page_end"):
                try:
                    entry["end_page"] = int(m.group("page_end"))
                except ValueError:
                    pass
            articles.append(entry)
    return articles
