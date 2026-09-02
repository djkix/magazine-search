import re
from pathlib import Path

from app.models import Page
from app.services.toc import MAX_SOMMAIRE_PAGE
from app.worker.ocr import extract_page_text_alternate

# The "SOMMAIRE" heading search looks much further into the magazine than
# the entry-density fallback below - some magazines (glossy monthlies with
# a long editorial/ad front section) bury their table of contents well past
# page 8, e.g. page 18-19 out of 210. A heading match is a precise,
# low-false-positive signal, so it's safe to search a wider window; the
# density fallback stays tight since it has no such anchor to rely on.
MAX_HEADING_SEARCH_PAGE = 30

# Two families of sommaire layout are common in French magazines:
#
# 1. "Title ......... p.NN" (dot leaders) or, in a tabular/column layout,
#    "Title            p.NN-MM" (a run of plain whitespace instead of dots) -
#    the page reference trails the title on the same line. Some magazines'
#    dot leaders come out of OCR as individual periods each separated by a
#    thin space (U+2009) rather than a run of consecutive dots, e.g.
#    "Title. . . . . p. 6" - so the leader is matched as any
#    3+-character run mixing dots and whitespace, not just a consecutive
#    run of one or the other.
_TRAILING_RE = re.compile(
    r"^(?P<title>.+?)(?:[.·…\s]{3,})(?:p\.?\s*)?"
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
_HEADING_WORDS = ("sommaire", "contents", "content", "summary", "table of contents", "index")
MAX_HEADING_LENGTH = 30


def _collapse_letter_spacing(line: str) -> str:
    """Some magazines set the heading in a letter-spaced decorative font
    ("S O M M A I R E"), which OCR can transcribe with a literal space
    between every letter - detected as a line of nothing but single-
    character tokens, and joined back into one word before matching."""
    tokens = line.split()
    if len(tokens) >= 4 and all(len(t) == 1 for t in tokens):
        return "".join(tokens)
    return line


def _is_sommaire_heading(line: str) -> bool:
    """The word "SOMMAIRE"/"CONTENTS" is the single strongest, most
    language-specific signal that a page is the actual table of contents -
    relied on as the primary anchor whenever it's present (falling back to
    entry density only when it truly isn't). A word boundary is required
    right after the matched word (a following space or punctuation, not a
    letter) so a longer French word sharing the same prefix isn't matched
    (e.g. "sommairement") while a legitimate multi-word variant still is
    (e.g. "Sommaire interactif").

    "content"/"contents" are also ordinary French words ("des lecteurs
    contents", "un article content..."), so unlike "sommaire" (rarely
    used mid-sentence) they can appear as an incidental word inside a
    wrapped line of body prose - e.g. "...contents et cela va laisser..."
    genuinely starts with the word "contents" followed by a space, which
    would otherwise match. A decorative heading is always set capitalized
    in these layouts, while a line wrapped mid-sentence from body text is
    not, so requiring the line's own (pre-lowercasing) first letter to be
    uppercase filters out this kind of false positive without needing to
    single out which heading words are ambiguous."""
    collapsed = re.sub(r"\s+", " ", _collapse_letter_spacing(line)).strip()
    if not collapsed or not collapsed[0].isupper():
        return False
    normalized = collapsed.lower()
    if len(normalized) > MAX_HEADING_LENGTH:
        return False
    for word in _HEADING_WORDS:
        if not normalized.startswith(word):
            continue
        rest = normalized[len(word) :]
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
    """Identifies which page(s) actually carry the sommaire, instead of
    scanning every early page - a magazine's cover, imprint or ad pages can
    otherwise contribute false-positive matches if every page were scanned
    indiscriminately."""
    heading_search_pages = [p for p in pages if p.page_number <= MAX_HEADING_SEARCH_PAGE and p.raw_text]
    heading_pages: set[int] = set()
    for page in heading_search_pages:
        lines = [ln.strip() for ln in page.raw_text.splitlines() if ln.strip() and not _is_boilerplate(ln.strip(), boilerplate)]
        if any(_is_sommaire_heading(ln) for ln in lines):
            heading_pages.add(page.page_number)

    if heading_pages:
        return heading_pages | {n + 1 for n in heading_pages}

    # No heading found anywhere in the wider search window - fall back to
    # whichever page, among the tighter early-page window, has the most
    # entry-shaped lines (a real TOC has many; an ad/imprint page has at
    # most one or two incidental matches).
    density_candidates = [p for p in pages if p.page_number <= MAX_SOMMAIRE_PAGE and p.raw_text]
    match_counts: dict[int, int] = {}
    for page in density_candidates:
        lines = [ln.strip() for ln in page.raw_text.splitlines() if ln.strip() and not _is_boilerplate(ln.strip(), boilerplate)]
        match_counts[page.page_number] = _count_entry_matches(lines)

    if not match_counts or max(match_counts.values()) < 4:
        return set()
    best_page = max(match_counts, key=match_counts.get)
    return {best_page, best_page + 1}


def _parse_entries(text: str, boilerplate: set[str]) -> list[dict]:
    """Runs the pattern-matching state machine over one page's text and
    returns whatever entries it finds. Pulled out of extract_articles_from_ocr
    so the same parser can be re-run against an alternate reading-order
    reconstruction of the same page when the default (linear) text yielded
    nothing."""
    articles: list[dict] = []

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

    for raw_line in text.splitlines():
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


def extract_articles_from_ocr(pages: list[Page], pdf_path: Path | None = None) -> list[dict]:
    """Best-effort, purely local extraction of a magazine's sommaire
    (title + start page, and end page when the entry itself gives a range)
    straight from its own OCR'd text - no Gemini call, so no quota/cost and
    no dependency on the account's rate limits. Runs synchronously right
    after OCR.

    The default (linear) text extraction gets the reading order wrong on
    many real two-column sommaire pages - not just producing zero entries
    (which would be easy to detect and fall back from), but sometimes one
    lone, badly mangled entry whose page range stretches to the end of the
    magazine, which looks like a "success" if only checked for emptiness.
    So rather than trying alternate reading-order reconstructions (column-
    based, then row-based) only as a fallback when linear text found
    nothing, all of them are tried whenever `pdf_path` is available, and
    whichever yields the most entries wins - a genuine sommaire has many
    entries, so a parse that only manages a handful is almost certainly
    the wrong reading order, not a magazine with an unusually short one."""
    boilerplate = _find_boilerplate_templates(pages)
    sommaire_page_numbers = _find_sommaire_pages(pages, boilerplate)
    if not sommaire_page_numbers:
        return []

    candidate_pages = [p for p in pages if p.page_number in sommaire_page_numbers and p.raw_text]
    linear_articles: list[dict] = []
    for page in candidate_pages:
        linear_articles.extend(_parse_entries(page.raw_text, boilerplate))

    best = linear_articles
    if pdf_path:
        for strategy in ("columns", "rows"):
            strategy_articles: list[dict] = []
            for page_number in sorted(sommaire_page_numbers):
                alt_text = extract_page_text_alternate(pdf_path, page_number, strategy)
                if alt_text:
                    strategy_articles.extend(_parse_entries(alt_text, boilerplate))
            if len(strategy_articles) > len(best):
                best = strategy_articles

    return best
