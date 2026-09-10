import { Fragment } from "react";

/**
 * Surligne les occurrences d'un terme dans un texte brut.
 *
 * Contrairement a sanitizeHighlightedSnippet, qui traite des extraits ou
 * Meilisearch a DEJA pose les balises <mark>, ce composant travaille sur du
 * texte sans balisage : titres d'articles, noms de numeros.
 *
 * Il construit des elements React au lieu d'injecter du HTML. React echappe
 * alors tout le contenu, ce qui rend l'injection impossible par construction —
 * la ou un second `dangerouslySetInnerHTML` aurait demande un assainissement
 * supplementaire sur du texte issu de PDF que l'on ne maitrise pas.
 */

/** Neutralise les caracteres speciaux d'expression reguliere : un nom de
 *  thematique peut contenir un plus, un point ou une parenthese. */
function echapperRegex(terme: string): string {
  return terme.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export default function TexteSurligne({
  texte,
  terme,
  className = "rounded bg-primary/20 px-0.5 text-primary-light",
}: {
  texte: string;
  /** Terme a surligner. Vide ou absent : le texte est rendu tel quel. */
  terme?: string | null;
  className?: string;
}) {
  const recherche = terme?.trim();
  if (!recherche) {
    return <>{texte}</>;
  }

  // La capture entre parentheses conserve les separateurs dans le resultat
  // de split, ce qui permet de reconstituer le texte complet.
  const morceaux = texte.split(new RegExp(`(${echapperRegex(recherche)})`, "gi"));

  return (
    <>
      {morceaux.map((morceau, i) =>
        morceau.toLowerCase() === recherche.toLowerCase() ? (
          <mark key={i} className={className}>
            {morceau}
          </mark>
        ) : (
          <Fragment key={i}>{morceau}</Fragment>
        )
      )}
    </>
  );
}
