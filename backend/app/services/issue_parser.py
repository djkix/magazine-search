import re
from datetime import datetime, timezone

# Both French and English month names are recognized (some collections use
# English-named files, e.g. "Computer Music 316 January 2023"), but the
# label we produce is always French.
_MONTHS = {
    "janvier": 1, "january": 1,
    "février": 2, "fevrier": 2, "february": 2,
    "mars": 3, "march": 3,
    "avril": 4, "april": 4,
    "mai": 5, "may": 5,
    "juin": 6, "june": 6,
    "juillet": 7, "july": 7,
    "août": 8, "aout": 8, "august": 8,
    "septembre": 9, "september": 9,
    "octobre": 10, "october": 10,
    "novembre": 11, "november": 11,
    "décembre": 12, "decembre": 12, "december": 12,
}
_FRENCH_MONTH_NAMES = [
    "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
]
_MONTH_ALTERNATION = "|".join(sorted(_MONTHS, key=len, reverse=True))

_MONTH_NAME_RANGE_RE = re.compile(
    rf"\b(?P<m1>{_MONTH_ALTERNATION})(?:[\s-]+(?P<m2>{_MONTH_ALTERNATION}))?\s+(?P<year>(?:19|20)\d{{2}})\b",
    re.IGNORECASE,
)
_MM_MM_YYYY_RE = re.compile(r"\b(0[1-9]|1[0-2])-(0[1-9]|1[0-2])-((?:19|20)\d{2})\b")
_YYYY_MM_MM_RE = re.compile(r"\b((?:19|20)\d{2})-(0[1-9]|1[0-2])-(0[1-9]|1[0-2])\b")
_YYYY_MM_RE = re.compile(r"\b((?:19|20)\d{2})-(0[1-9]|1[0-2])\b")
_MM_YYYY_RE = re.compile(r"\b(0[1-9]|1[0-2])-((?:19|20)\d{2})\b")
_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")


def _month_label(month1: int, month2: int) -> str:
    if month1 == month2:
        return _FRENCH_MONTH_NAMES[month1 - 1]
    return f"{_FRENCH_MONTH_NAMES[month1 - 1]}-{_FRENCH_MONTH_NAMES[month2 - 1]}"


def parse_issue_metadata(title: str) -> tuple[str | None, datetime | None, str | None]:
    """Best-effort extraction of (issue_number, publication_date, month_label)
    from a magazine's title/filename, e.g.:
    - "60 Millions De Consommateurs - 580 - 2022-05" -> ("580", 2022-05-01, "Mai")
    - "Ca M'intéresse - 514 - 12-2023" -> ("514", 2023-12-01, "Décembre")
    - "AD Architectural Digest France - Septembre-Octobre 2026" -> (None, 2026-09-01, "Septembre-Octobre")
    - "Computer Music 316 January 2023" -> ("316", 2023-01-01, "Janvier")

    publication_date always anchors on the first month of a range, for
    sorting/year filtering; month_label is the human-readable single month
    or month range for display.
    """
    year = month1 = month2 = None
    match_span: tuple[int, int] | None = None

    m = _MONTH_NAME_RANGE_RE.search(title)
    if m:
        year = int(m.group("year"))
        month1 = _MONTHS[m.group("m1").lower()]
        month2 = _MONTHS[m.group("m2").lower()] if m.group("m2") else month1
        match_span = m.span()
    else:
        m = _MM_MM_YYYY_RE.search(title)
        if m:
            month1, month2, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
            match_span = m.span()
        else:
            m = _YYYY_MM_MM_RE.search(title)
            if m:
                year, month1, month2 = int(m.group(1)), int(m.group(2)), int(m.group(3))
                match_span = m.span()
            else:
                m = _YYYY_MM_RE.search(title)
                if m:
                    year, month1 = int(m.group(1)), int(m.group(2))
                    month2 = month1
                    match_span = m.span()
                else:
                    m = _MM_YYYY_RE.search(title)
                    if m:
                        month1, year = int(m.group(1)), int(m.group(2))
                        month2 = month1
                        match_span = m.span()
                    else:
                        m = _YEAR_RE.search(title)
                        if m:
                            year = int(m.group(1))
                            match_span = m.span()

    publication_date = None
    month_label = None
    if year:
        publication_date = datetime(year, month1 or 1, 1, tzinfo=timezone.utc)
        if month1:
            month_label = _month_label(month1, month2)

    # The issue number is usually the number immediately before the date
    # (e.g. "60 Millions ... - 580 - 2022-05"), not just the first number
    # anywhere in the title - a magazine's own name can contain digits (e.g.
    # "60 Millions De Consommateurs"). Prefer the number closest to the date
    # on the left; only look to the right of the date if nothing precedes it.
    before, after = (title[: match_span[0]], title[match_span[1] :]) if match_span else (title, "")

    def _find_issue_number(text: str, prefer_last: bool) -> str | None:
        tokens = re.findall(r"\b\d{2,4}\b", text)
        candidates = [t for t in tokens if year is None or t != str(year)]
        if not candidates:
            return None
        return candidates[-1] if prefer_last else candidates[0]

    issue_number = _find_issue_number(before, prefer_last=True)
    if issue_number is None:
        issue_number = _find_issue_number(after, prefer_last=False)

    return issue_number, publication_date, month_label
