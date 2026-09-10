from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Magazine, Theme
from app.schemas import MagazineThemeOut

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[MagazineThemeOut])
def list_themes(db: Session = Depends(get_db)):
    """Every theme in use across the whole library, with how many magazines
    carry it.

    A theme is a label shared library-wide: "Bricolage" can be attached to a
    buying guide in *60 Millions de consommateurs* and to an issue of
    *Systeme D* alike. Its weight is therefore the number of distinct
    magazines carrying it, regardless of collection.

    Ordering, in this order:
      1. magazine count, descending - the most represented themes first;
      2. on a tie, the most recent theme first, "recent" meaning the
         publication date of the newest magazine carrying it (more useful
         than the label's own creation date, which only reflects when
         Gemini happened to coin it). Magazines with no publication date
         sort last so an undated issue never promotes a theme;
      3. name, so the order is stable between two identical rows.

    Themes attached to no magazine are excluded by the join - an empty
    entry would lead to an empty result page.
    """
    rows = (
        db.query(
            Theme.id,
            Theme.name,
            func.count(Magazine.id.distinct()).label("magazine_count"),
        )
        .join(Theme.magazines)
        .group_by(Theme.id, Theme.name)
        .order_by(
            func.count(Magazine.id.distinct()).desc(),
            func.max(Magazine.publication_date).desc().nullslast(),
            Theme.name,
        )
        .all()
    )
    return [MagazineThemeOut(id=theme_id, name=name, magazine_count=count) for theme_id, name, count in rows]
