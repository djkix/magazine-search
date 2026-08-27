import meilisearch
from meilisearch.errors import MeilisearchApiError

from app.config import get_settings

settings = get_settings()

_client: meilisearch.Client | None = None


def get_client() -> meilisearch.Client:
    global _client
    if _client is None:
        _client = meilisearch.Client(settings.meili_host, settings.meili_master_key)
    return _client


def get_index():
    return get_client().index(settings.meili_index_pages)


def ensure_index_configured() -> None:
    client = get_client()
    try:
        client.create_index(settings.meili_index_pages, {"primaryKey": "page_id"})
    except MeilisearchApiError as exc:
        if exc.code != "index_already_exists":
            raise

    index = get_index()
    index.update_searchable_attributes(["raw_text", "magazine_title"])
    index.update_filterable_attributes(
        ["magazine_id", "magazine_title", "issue_number", "year", "category_id", "collection_id"]
    )
    index.update_sortable_attributes(["publication_date"])


def _page_doc(page, magazine) -> dict:
    return {
        "page_id": page.id,
        "magazine_id": magazine.id,
        "magazine_title": magazine.title,
        "issue_number": magazine.issue_number,
        "year": magazine.publication_date.year if magazine.publication_date else None,
        "publication_date": magazine.publication_date.isoformat() if magazine.publication_date else None,
        "page_number": page.page_number,
        "raw_text": page.raw_text or "",
        "language": page.language.value if page.language else None,
        "collection_id": magazine.collection_id,
        "category_id": magazine.collection.category_id if magazine.collection else None,
    }


def index_page(page, magazine) -> None:
    get_index().add_documents([_page_doc(page, magazine)])


def index_pages(pages, magazine) -> None:
    """Batch variant of index_page, for bulk operations like a full reindex."""
    docs = [_page_doc(page, magazine) for page in pages]
    if docs:
        get_index().add_documents(docs)


def delete_magazine_pages(magazine_id: int) -> None:
    get_index().delete_documents(filter=f"magazine_id = {magazine_id}")
