from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Collection
from app.schemas import CollectionOut

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[CollectionOut])
def list_collections(db: Session = Depends(get_db)):
    collections = db.query(Collection).order_by(Collection.name).all()
    return [
        CollectionOut(
            id=c.id,
            name=c.name,
            category_id=c.category_id,
            category_name=c.category.name if c.category else None,
        )
        for c in collections
    ]
