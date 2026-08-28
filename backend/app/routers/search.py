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


@router.get("/search", response_model=SearchResponse)
def search(
    q: str = Query(..., min_length=1),
    magazine_id: int | None = None,
    magazine_title: str | None = None,
    year: int | None = None,
    issue_number: str | None = None,
    tag_id: int | None = Query(None, description="Restrict to magazines whose collection carries this tag"),
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
    if tag_id is not None:
        filters.append(f"tag_ids = {tag_id}")
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

    terms = _matched_terms(q)
    hits: list[SearchHit] = []
    for magazine_id_ in page_magazine_ids:
        group = groups[magazine_id_]
        best = group[0]
        page_id = best["page_id"]
        formatted = best.get("_formatted", {})
        snippet = formatted.get("raw_text", best.get("raw_text", ""))

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
                magazine_id=best["magazine_id"],
                magazine_title=best["magazine_title"],
                occurrence_count=len(group),
                page_number=best["page_number"],
                page_id=page_id,
                snippet=snippet,
                words=words,
            )
        )

    return SearchResponse(
        query=q,
        total_hits=len(magazine_ids_ranked),
        hits=hits,
        processing_time_ms=results.get("processingTimeMs", 0),
    )
