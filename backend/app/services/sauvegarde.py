"""Alerte de sauvegarde pour le tableau de bord d'administration."""

from datetime import datetime, timedelta, timezone

# Au-delà, l'absence de sauvegarde réussie est signalée à l'administrateur.
AGE_MAX = timedelta(hours=36)


def _utc(d: datetime) -> datetime:
    # SQLite (tests) rend des dates naïves ; PostgreSQL, des dates avec fuseau.
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def alerte(
    derniere_reussie: bool | None,
    message: str,
    derniere_reussite: datetime | None,
    maintenant: datetime,
) -> str | None:
    """Dernière tentative en échec, ou dernière réussite de plus de 36 h.
    Aucune tentative (service jamais lancé) : rien."""
    if derniere_reussie is False:
        return f"Dernière sauvegarde en échec : {message}."
    if derniere_reussite and maintenant - _utc(derniere_reussite) > AGE_MAX:
        return "Aucune sauvegarde réussie depuis 36 h."
    return None
