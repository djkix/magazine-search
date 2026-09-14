from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Article, Collection, Magazine, Subtheme, Theme, subtheme_articles
from app.schemas import (
    MagazineThemeOut,
    SubthemeArticleOut,
    SubthemeCollectionGroupOut,
    SubthemeOut,
    TaxonomyThemeOut,
)

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


@router.get("/taxonomie", response_model=list[TaxonomyThemeOut])
def list_taxonomy_themes(db: Session = Depends(get_db)):
    """Niveau 1 : les thématiques ayant au moins un article rattaché.

    Distinct de la liste ci-dessus, qui compte les NUMÉROS portant une
    étiquette posée par Gemini. Ici on compte les ARTICLES rattachés par
    mots-clés — ni la même granularité, ni la même source.

    Les thématiques sans article rattaché sont écartées : elles ouvriraient
    sur un écran vide.
    """
    lignes = (
        db.query(
            Theme.id,
            Theme.name,
            func.count(func.distinct(Subtheme.id)),
            func.count(func.distinct(subtheme_articles.c.article_id)),
        )
        .join(Subtheme, Subtheme.theme_id == Theme.id)
        .join(subtheme_articles, subtheme_articles.c.subtheme_id == Subtheme.id)
        .group_by(Theme.id, Theme.name)
        .order_by(func.count(func.distinct(subtheme_articles.c.article_id)).desc(), Theme.name)
        .all()
    )
    return [
        TaxonomyThemeOut(id=i, name=n, subtheme_count=s, article_count=a)
        for i, n, s, a in lignes
    ]


@router.get("/{theme_id}/subthemes", response_model=list[SubthemeOut])
def list_subthemes(theme_id: int, db: Session = Depends(get_db)):
    """Niveau 2 : les sous-thématiques d'une thématique, les plus fournies
    d'abord.

    Celles sans article sont conservées : leur présence, avec un compte à
    zéro, signale des mots-clés qui n'accrochent rien — une information utile
    pour corriger la taxonomie, que masquer serait dommage.
    """
    lignes = (
        db.query(Subtheme.id, Subtheme.name, func.count(subtheme_articles.c.article_id))
        .outerjoin(subtheme_articles, subtheme_articles.c.subtheme_id == Subtheme.id)
        .filter(Subtheme.theme_id == theme_id)
        .group_by(Subtheme.id, Subtheme.name)
        .order_by(func.count(subtheme_articles.c.article_id).desc(), Subtheme.name)
        .all()
    )
    if not lignes and db.get(Theme, theme_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thème introuvable")
    return [SubthemeOut(id=i, name=n, article_count=a) for i, n, a in lignes]


@router.get("/subthemes/{subtheme_id}/articles", response_model=list[SubthemeCollectionGroupOut])
def list_subtheme_articles(subtheme_id: int, db: Session = Depends(get_db)):
    """Niveau 3 : les articles d'une sous-thématique, regroupés par collection.

    Une seule requête, jointures comprises : grouper en Python évite N+1
    requêtes sur des sous-thématiques qui peuvent en couvrir des centaines.

    Tri : les collections les plus fournies d'abord, puis au sein de chacune
    les numéros les plus récents — un numéro sans date passe en dernier
    plutôt que d'être exclu.
    """
    if db.get(Subtheme, subtheme_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Sous-thématique introuvable"
        )

    lignes = (
        db.query(
            Collection.id,
            Collection.name,
            Article.id,
            Article.title,
            Article.start_page,
            Magazine.id,
            Magazine.title,
            Magazine.issue_number,
            Magazine.issue_month_label,
            Magazine.publication_date,
        )
        .join(subtheme_articles, subtheme_articles.c.article_id == Article.id)
        .join(Magazine, Magazine.id == Article.magazine_id)
        .outerjoin(Collection, Collection.id == Magazine.collection_id)
        .filter(subtheme_articles.c.subtheme_id == subtheme_id)
        .order_by(
            Magazine.publication_date.desc().nullslast(),
            Magazine.id,
            Article.start_page,
        )
        .all()
    )

    groupes: dict[int | None, SubthemeCollectionGroupOut] = {}
    for (
        collection_id,
        collection_name,
        article_id,
        article_title,
        start_page,
        magazine_id,
        magazine_title,
        issue_number,
        issue_month_label,
        publication_date,
    ) in lignes:
        groupe = groupes.get(collection_id)
        if groupe is None:
            groupe = SubthemeCollectionGroupOut(
                collection_id=collection_id,
                # Les numéros non rattachés à une collection existent : leur
                # donner un libellé explicite vaut mieux qu'un entête vide.
                collection_name=collection_name or "Sans collection",
                article_count=0,
                articles=[],
            )
            groupes[collection_id] = groupe
        groupe.articles.append(
            SubthemeArticleOut(
                id=article_id,
                title=article_title,
                start_page=start_page,
                magazine_id=magazine_id,
                magazine_title=magazine_title,
                issue_number=issue_number,
                issue_month_label=issue_month_label,
                publication_date=publication_date,
            )
        )
        groupe.article_count += 1

    return sorted(groupes.values(), key=lambda g: g.article_count, reverse=True)
