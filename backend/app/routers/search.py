import re

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Page
from app.schemas import SearchHit, SearchResponse, WordBox
from app.services.meili import get_index

router = APIRouter(dependencies=[Depends(get_current_user)])

WORD_RE = re.compile(r"\w+", re.UNICODE)


def _matched_terms(query: str) -> set[str]:
    return {w.lower() for w in WORD_RE.findall(query)}


@router.get("/search", response_model=SearchResponse)
def search(
    q: str = Query(..., min_length=1),
    magazine_id: int | None = None,
    magazine_title: str | None = None,
    year: int | None = None,
    issue_number: str | None = None,
    page: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    filters = []
    if magazine_id:
        filters.append(f"magazine_id = {magazine_id}")
    if magazine_title:
        filters.append(f'magazine_title = "{magazine_title}"')
    if year:
        filters.append(f"year = {year}")
    if issue_number:
        filters.append(f'issue_number = "{issue_number}"')

    results = get_index().search(
        q,
        {
            "filter": " AND ".join(filters) if filters else None,
            "offset": page * limit,
            "limit": limit,
            "attributesToHighlight": ["raw_text"],
            "attributesToCrop": ["raw_text"],
            "cropLength": 40,
            "highlightPreTag": "<mark>",
            "highlightPostTag": "</mark>",
        },
    )

    terms = _matched_terms(q)
    hits: list[SearchHit] = []
    for hit in results["hits"]:
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
        total_hits=results.get("estimatedTotalHits", len(hits)),
        hits=hits,
        processing_time_ms=results.get("processingTimeMs", 0),
    )
