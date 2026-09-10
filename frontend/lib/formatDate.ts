export function formatYearMonth(isoDate: string | null): string | null {
  if (!isoDate) return null;
  const date = new Date(isoDate);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString("fr-FR", { year: "numeric", month: "long" });
}

// "Nom du magazine - numéro - Mois année", ex. "01net - 998 - Juin 2023".
// `name` doit déjà être le nom propre du magazine (nom de collection), pas
// le nom de fichier brut ("01net 998 - 06-2023"), qui répéterait le numéro.
export function formatMagazineHeading(
  name: string,
  issueNumber: string | null,
  monthLabel: string | null,
  publicationDate: string | null
): string {
  const parts = [name];
  if (issueNumber) parts.push(issueNumber);

  const year = publicationDate ? new Date(publicationDate).getFullYear() : null;
  const yearValid = year !== null && !Number.isNaN(year);
  if (monthLabel && yearValid) parts.push(`${monthLabel} ${year}`);
  else if (monthLabel) parts.push(monthLabel);
  else if (yearValid) parts.push(String(year));

  return parts.join(" - ");
}
