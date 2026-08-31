import re

from app.models import Page
from app.services.toc import MAX_SOMMAIRE_PAGE

# Two families of sommaire layout are common in French magazines:
#
# 1. "Title ......... p.NN" (dot leaders) or, in a tabular/column layout,
#    "Title            p.NN-MM" (a run of plain whitespace instead of dots) -
#    the page reference trails the title on the same line.
_TRAILING_RE = re.compile(
    r"^(?P<title>.+?)(?:[.·…]{3,}|\s{3,})\s*(?:p\.?\s*)?"
    r"(?P<page>\d{1,4})(?:\s*[-–]\s*(?P<page_end>\d{1,4}))?\s*$",
    re.IGNORECASE,
)
# 2. "NN Title" - a bold page number leads the title on the same line, e.g.
#    "18 Contrôle médical", common in a magazine's "highlights" style sommaire.
_LEADING_INLINE_RE = re.compile(r"^(?P<page>\d{1,3})\s+(?P<title>[A-ZÀ-Ý].{1,})$")
# ...a page number sometimes sits alone on its own line - its own colored
# badge in the layout - either BEFORE the title (leading style: title
# follows on the next line(s)) or AFTER it (a trailing-style title whose
# closing page number ended up on its own line rather than appended with
# dots on the same line as the title).
_BARE_NUMBER_RE = re.compile(r"^(?P<page>\d{1,3})$")

# Category/kicker labels ("ENQUÊTE", "ZOOM", "LE MATCH"...) are conventionally
# short and fully uppercase - never part of an article's own title, so they
# must not get glued onto a neighbouring entry as a title continuation.
_SECTION_LABEL_RE = re.compile(r"^[A-ZÀ-Ý0-9][A-ZÀ-Ý0-9 ?!'’.-]{0,30}$")

MAX_TITLE_CONTINUATION_LINES = 3


def _is_section_label(line: str) -> bool:
    words = line.split()
    return len(words) <= 4 and bool(_SECTION_LABEL_RE.match(line)) and any(c.isalpha() for c in line)


# A few collections use English-named files/layouts (per the same
# reasoning as issue_parser's month names) even in an otherwise French
# library - checked alongside "sommaire" as an equally strong anchor.
_HEADING_WORDS = ("sommaire", "contents", "content", "summary", "tableofcontents", "index")


def _is_sommaire_heading(line: str) -> bool:
    """The word "SOMMAIRE"/"CONTENTS" is the single strongest, most
    language-specific signal that a page is the actual table of contents -
    relied on as the primary anchor whenever it's present (falling back to
    entry density only when it truly isn't). Some magazines set it in a
    letter-spaced decorative font ("S O M M A I R E"), which OCR can
    transcribe with a literal space between each letter, so the comparison
    strips whitespace before matching. A trailing issue/date sometimes ends
    up glued onto the same line by text extraction (e.g. "SOMMAIREN°613"),
    so only a word boundary is required right after the matched word - not
    an exact, standalone line - while still rejecting a longer French word
    that happens to share the same prefix (e.g. "sommairement")."""
    compact = re.sub(r"\s+", "", line).strip(" :.-").lower()
    for word in _HEADING_WORDS:
        if compact.startswith(word):
            rest = compact[len(word) :]
            if not rest or not rest[0].isalpha():
                return True
    return False


_DIGIT_RUN_RE = re.compile(r"\d+")
MIN_BOILERPLATE_PAGES = 3


def _find_boilerplate_templates(pages: list[Page]) -> set[str]:
    """A running header/footer repeats on nearly every page with only its
    page number changing (e.g. "60 Millions De Consommateurs ... 5"), which
    would otherwise be indistinguishable from a real sommaire entry to the
    patterns above - including one starting with a number that happens to
    be part of the magazine's own name. Detected generically, with no
    knowledge of what the boilerplate actually says, by normalizing out
    digit runs and finding lines whose normalized form recurs across many
    distinct pages of the WHOLE magazine (not just the sommaire page(s))."""
    template_pages: dict[str, set[int]] = {}
    for page in pages:
        if not page.raw_text:
            continue
        seen_on_this_page: set[str] = set()
        for raw_line in page.raw_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            template = _DIGIT_RUN_RE.sub("#", line).lower()
            if not template or template in seen_on_this_page:
                continue
            seen_on_this_page.add(template)
            template_pages.setdefault(template, set()).add(page.page_number)
    return {t for t, pgs in template_pages.items() if len(pgs) >= MIN_BOILERPLATE_PAGES}


def _is_boilerplate(line: str, boilerplate: set[str]) -> bool:
    return _DIGIT_RUN_RE.sub("#", line).lower() in boilerplate


def _count_entry_matches(lines: list[str]) -> int:
    return sum(1 for ln in lines if _TRAILING_RE.match(ln) or _LEADING_INLINE_RE.match(ln) or _BARE_NUMBER_RE.match(ln))


def _find_sommaire_pages(pages: list[Page], boilerplate: set[str]) -> set[int]:
    """Identifies which page(s) among the first few actually carry the
    sommaire, instead of scanning every early page - a magazine's cover,
    imprint or ad pages can otherwise contribute false-positive matches if
    every page were scanned indiscriminately."""
    candidate_pages = [p for p in pages if p.page_number <= MAX_SOMMAIRE_PAGE and p.raw_text]
    heading_pages: set[int] = set()
    match_counts: dict[int, int] = {}

    for page in candidate_pages:
        lines = [ln.strip() for ln in page.raw_text.splitlines() if ln.strip() and not _is_boilerplate(ln.strip(), boilerplate)]
        match_counts[page.page_number] = _count_entry_matches(lines)
        if any(_is_sommaire_heading(ln) for ln in lines):
            heading_pages.add(page.page_number)

    if heading_pages:
        return heading_pages | {n + 1 for n in heading_pages}

    if not match_counts or max(match_counts.values()) < 4:
        return set()
    best_page = max(match_counts, key=match_counts.get)
    return {best_page, best_page + 1}


def extract_articles_from_ocr(pages: list[Page]) -> list[dict]:
    """Best-effort, purely local extraction of a magazine's sommaire
    (title + start page, and end page when the entry itself gives a range)
    straight from its own OCR'd text - no Gemini call, so no quota/cost and
    no dependency on the account's rate limits. Runs synchronously right
    after OCR."""
    boilerplate = _find_boilerplate_templates(pages)
    sommaire_page_numbers = _find_sommaire_pages(pages, boilerplate)
    if not sommaire_page_numbers:
        return []

    candidate_pages = [p for p in pages if p.page_number in sommaire_page_numbers and p.raw_text]
    articles: list[dict] = []

    for page in candidate_pages:
        # `pending_page`/`pending_title_lines`: an entry whose page number is
        # already known and is waiting for its title (leading-style, number
        # first). `generic_pending`: title text accumulated with no page
        # number yet (trailing-style, title first) - a bare number arriving
        # while this is non-empty closes it as that entry's page instead of
        # starting a new leading-style one.
        pending_title_lines: list[str] = []
        pending_page: int | None = None
        generic_pending: list[str] = []

        def flush_leading_entry() -> None:
            nonlocal pending_page, pending_title_lines
            if pending_page is not None and pending_title_lines:
                title = " ".join(pending_title_lines).strip()
                if title:
                    articles.append({"title": title, "start_page": pending_page})
            pending_page = None
            pending_title_lines = []

        for raw_line in page.raw_text.splitlines():
            line = raw_line.strip()
            if not line or _is_boilerplate(line, boilerplate):
                flush_leading_entry()
                generic_pending.clear()
                continue

            m_trailing = _TRAILING_RE.match(line)
            if m_trailing:
                flush_leading_entry()
                title_part = m_trailing.group("title").strip(" .·…")
                title = " ".join([*generic_pending, title_part]).strip()
                generic_pending.clear()
                try:
                    start_page = int(m_trailing.group("page"))
                except ValueError:
                    continue
                if not title or not (1 <= start_page <= 999):
                    continue
                entry = {"title": title, "start_page": start_page}
                if m_trailing.group("page_end"):
                    try:
                        entry["end_page"] = int(m_trailing.group("page_end"))
                    except ValueError:
                        pass
                articles.append(entry)
                continue

            m_leading = _LEADING_INLINE_RE.match(line)
            if m_leading:
                flush_leading_entry()
                generic_pending.clear()
                pending_page = int(m_leading.group("page"))
                pending_title_lines = [m_leading.group("title").strip()]
                continue

            m_bare = _BARE_NUMBER_RE.match(line)
            if m_bare:
                page_number = int(m_bare.group("page"))
                if generic_pending and pending_page is None:
                    # A trailing-style title was accumulating with no page
                    # number yet - this bare number closes it (its badge
                    # landed on its own line instead of after dots).
                    title = " ".join(generic_pending).strip()
                    generic_pending.clear()
                    if title and 1 <= page_number <= 999:
                        articles.append({"title": title, "start_page": page_number})
                    continue
                flush_leading_entry()
                pending_page = page_number
                pending_title_lines = []
                continue

            if _is_section_label(line):
                # A kicker/category label - never part of a title, and it
                # separates whatever came before from what follows.
                flush_leading_entry()
                generic_pending.clear()
                continue

            if pending_page is not None:
                pending_title_lines.append(line)
                if len(pending_title_lines) > MAX_TITLE_CONTINUATION_LINES:
                    pending_title_lines.pop(0)
            else:
                generic_pending.append(line)
                if len(generic_pending) > MAX_TITLE_CONTINUATION_LINES:
                    generic_pending.pop(0)

        flush_leading_entry()

    return articles
