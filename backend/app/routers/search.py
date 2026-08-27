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

# How many matching pages to pull from Meilisearch before re-ranking by magazine.
# Bounds the re-ranking cost; comfortably above what any single query is expected
# to match in a self-hosted, personal-scale collection.
MAX_RANKED_HITS = 500


def _matched_terms(query: str) -> set[str]:
    return {w.lower() for w in WORD_RE.findall(query)}


def _escape_filter_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


@router.get("/search", response_model=SearchResponse)
def search(
    q: str = Query(..., min_length=1),
    magazine_id: int | None = None,
    magazine_title: str | None = None,
    year: int | None = None,
    issue_number: str | None = None,
    category_id: int | None = Query(None, description="Restrict to magazines in this category"),
    collection_id: int | None = Query(None, description="Restrict to magazines in this collection"),
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
    if category_id is not None:
        filters.append(f"category_id = {category_id}")
    if collection_id is not None:
        filters.append(f"collection_id = {collection_id}")

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

    # Rank by magazine relevance first (the magazine with the most matching pages
    # for this query wins), then by recency (a more recent magazine wins a tie),
    # then by page order within a magazine. Python's sort is stable, so applying
    # the keys least-significant-first yields that combined ordering.
    magazine_hit_counts: dict[int, int] = {}
    magazine_pub_dates: dict[int, str] = {}
    for hit in raw_hits:
        hit_magazine_id = hit["magazine_id"]
        magazine_hit_counts[hit_magazine_id] = magazine_hit_counts.get(hit_magazine_id, 0) + 1
        pub_date = hit.get("publication_date") or ""
        if pub_date > magazine_pub_dates.get(hit_magazine_id, ""):
            magazine_pub_dates[hit_magazine_id] = pub_date

    ranked_hits = sorted(raw_hits, key=lambda h: h["page_number"])
    ranked_hits.sort(key=lambda h: magazine_pub_dates.get(h["magazine_id"], ""), reverse=True)
    ranked_hits.sort(key=lambda h: magazine_hit_counts[h["magazine_id"]], reverse=True)

    start = page * limit
    page_hits = ranked_hits[start : start + limit]

    terms = _matched_terms(q)
    hits: list[SearchHit] = []
    for hit in page_hits:
        page_id = hit["page_id"]
        formatted = hit.get("_formatted", {})
        snippet = formatted.get("raw_text", hit.get("raw_text", ""))

        db_page = db.get(Page, page_id)
        words: list[WordBox] = []
        if db_page and db_page.words:
            words = [
                WordBox(**w)
                for w in db_page.words
                if re.sub(r"\W+", "", w["text"]).lower() in terms
            ]

        hits.append(
            SearchHit(
                magazine_id=hit["magazine_id"],
                magazine_title=hit["magazine_title"],
                page_number=hit["page_number"],
                page_id=page_id,
                snippet=snippet,
                words=words,
            )
        )

    return SearchResponse(
        query=q,
        total_hits=min(results.get("estimatedTotalHits", len(hits)), len(ranked_hits)),
        hits=hits,
        processing_time_ms=results.get("processingTimeMs", 0),
    )
