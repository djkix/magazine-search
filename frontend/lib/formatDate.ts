export function formatYearMonth(isoDate: string | null): string | null {
  if (!isoDate) return null;
  const date = new Date(isoDate);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString("fr-FR", { year: "numeric", month: "long" });
}

// "Nom du magazine - numéro - Mois année", ex. "01net - 998 - Juin 2023".
// `collectionName` est le nom propre du magazine ; `rawTitle` est le nom de
// fichier brut ("01net 998 - 06-2023"), utilisé tel quel en repli quand la
// collection est inconnue - sans repli, name serait le nom de fichier brut ET
// se ferait quand même accoler numéro/date, qui y figurent déjà (doublon,
// ex. "01net 998 - 06-2023 - 998 - Juin 2023").
export function formatMagazineHeading(
  collectionName: string | null,
  rawTitle: string,
  issueNumber: string | null,
  monthLabel: string | null,
  publicationDate: string | null
): string {
  if (!collectionName) return rawTitle;

  const parts = [collectionName];
  if (issueNumber) parts.push(issueNumber);

  const year = publicationDate ? new Date(publicationDate).getFullYear() : null;
  const yearValid = year !== null && !Number.isNaN(year);
  if (monthLabel && yearValid) parts.push(`${monthLabel} ${year}`);
  else if (monthLabel) parts.push(monthLabel);
  else if (yearValid) parts.push(String(year));

  return parts.join(" - ");
}
