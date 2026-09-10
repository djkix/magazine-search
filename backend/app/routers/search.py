import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from meilisearch.errors import MeilisearchApiError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Page
from app.schemas import SearchHit, SearchResponse, WordBox
from app.services.meili import get_index

router = APIRouter(dependencies=[Depends(get_current_user)])

WORD_RE = re.compile(r"\w+", re.UNICODE)

# How many matching pages to pull from Meilisearch before grouping by magazine.
# Bounds the re-ranking cost; comfortably above what any single query is expected
# to match in a self-hosted, personal-scale collection.
MAX_RANKED_HITS = 500


def _matched_terms(query: str) -> set[str]:
    return {w.lower() for w in WORD_RE.findall(query)}


def _escape_filter_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _build_hit(raw: dict, terms: set[str], db: Session, occurrence_count: int | None = None) -> SearchHit:
    page_id = raw["page_id"]
    formatted = raw.get("_formatted", {})
    snippet = formatted.get("raw_text", raw.get("raw_text", ""))

    db_page = db.get(Page, page_id)
    words: list[WordBox] = []
    if db_page and db_page.words:
        words = [WordBox(**w) for w in db_page.words if re.sub(r"\W+", "", w["text"]).lower() in terms]

    return SearchHit(
        magazine_id=raw["magazine_id"],
        magazine_title=raw["magazine_title"],
        # In a single-magazine result, occurrence_count is this page's own
        # matched-word count; across magazines (occurrence_count passed in
        # explicitly), it's how many pages of that magazine matched.
        occurrence_count=occurrence_count if occurrence_count is not None else (len(words) or 1),
        page_number=raw["page_number"],
        page_id=page_id,
        snippet=snippet,
        words=words,
        publication_date=raw.get("publication_date"),
        issue_number=raw.get("issue_number"),
        issue_month=raw.get("issue_month"),
        collection_name=raw.get("collection_name"),
    )


@router.get("/search", response_model=SearchResponse)
def search(
    q: str = Query(..., min_length=1),
    magazine_id: int | None = None,
    magazine_title: str | None = None,
    year: int | None = None,
    issue_number: str | None = None,
    tag_id: list[int] = Query([], description="Restrict to magazines whose collection carries any of these tags"),
    collection_id: list[int] = Query([], description="Restrict to magazines in any of these collections"),
    page: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    filters = []
    if magazine_id is not None:
        filters.append(f"magazine_id = {magazine_id}")
    if magazine_title:
        filters.append(f'magazine_title = "{_escape_filter_value(magazine_title)}"')
    if year:
        filters.append(f"year = {year}")
    if issue_number:
        filters.append(f'issue_number = "{_escape_filter_value(issue_number)}"')
    if tag_id:
        filters.append(f"tag_ids IN [{','.join(str(tid) for tid in tag_id)}]")
    if collection_id:
        filters.append(f"collection_id IN [{','.join(str(cid) for cid in collection_id)}]")

    try:
        results = get_index().search(
            q,
            {
                "filter": " AND ".join(filters) if filters else None,
                "offset": 0,
                "limit": MAX_RANKED_HITS,
                "attributesToHighlight": ["raw_text"],
                "attributesToCrop": ["raw_text"],
                "cropLength": 40,
                "highlightPreTag": "<mark>",
                "highlightPostTag": "</mark>",
            },
        )
    except MeilisearchApiError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Search backend error") from exc

    raw_hits = results["hits"]
    terms = _matched_terms(q)

    if magazine_id is not None:
        # Single-magazine context (the viewer's "find in this document"):
        # grouping by magazine like the cross-library search below would
        # collapse everything down to just the one best-matching page,
        # since there's only one magazine in the result set - instead
        # return every matching page, in page order, so the caller can
        # step through occurrences one page at a time.
        raw_hits.sort(key=lambda h: h["page_number"])
        start = page * limit
        page_hits = raw_hits[start : start + limit]
        hits = [_build_hit(raw, terms, db) for raw in page_hits]
        return SearchResponse(
            query=q,
            total_hits=len(raw_hits),
            hits=hits,
            processing_time_ms=results.get("processingTimeMs", 0),
        )

    # One row per magazine, not per page: group hits by magazine, keeping each
    # group's own hits in Meilisearch's original relevance order so the first
    # hit in a group is that magazine's single best-matching page.
    groups: dict[int, list[dict]] = {}
    for hit in raw_hits:
        groups.setdefault(hit["magazine_id"], []).append(hit)

    # Rank magazines by how many matching pages they have (most occurrences
    # first), then by recency as a tiebreak. Python's sort is stable, so
    # applying the keys least-significant-first yields that combined order.
    magazine_ids_ranked = sorted(groups, key=lambda mid: groups[mid][0].get("publication_date") or "", reverse=True)
    magazine_ids_ranked.sort(key=lambda mid: len(groups[mid]), reverse=True)

    start = page * limit
    page_magazine_ids = magazine_ids_ranked[start : start + limit]

    hits = [_build_hit(groups[mid][0], terms, db, occurrence_count=len(groups[mid])) for mid in page_magazine_ids]

    return SearchResponse(
        query=q,
        total_hits=len(magazine_ids_ranked),
        hits=hits,
        processing_time_ms=results.get("processingTimeMs", 0),
    )
