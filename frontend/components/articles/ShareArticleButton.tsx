"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import Icon from "@/components/ui/Icon";

export default function ShareArticleButton({
  articleId,
  className = "",
}: {
  articleId: number;
  className?: string;
}) {
  const [etat, setEtat] = useState<"inactif" | "copie" | "erreur">("inactif");

  async function partager(e: React.MouseEvent) {
    // Les listes qui utilisent ce bouton l'imbriquent dans une zone
    // cliquable plus large (toute la ligne ouvre l'article) : sans ceci, le
    // clic sur "Partager" ouvrirait aussi l'article.
    e.preventDefault();
    e.stopPropagation();

    let token: string;
    try {
      ({ token } = await api.post<{ token: string }>(`/articles/${articleId}/share`));
    } catch {
      // Échec réel de la création du lien (article supprimé entre-temps,
      // backend indisponible...) : contrairement à un échec de presse-
      // papiers ci-dessous, l'utilisateur croirait sinon avoir un lien
      // fonctionnel alors que rien n'a été copié.
      setEtat("erreur");
      window.setTimeout(() => setEtat("inactif"), 1500);
      return;
    }

    try {
      await navigator.clipboard.writeText(`${window.location.origin}/partage/${token}`);
      setEtat("copie");
    } catch {
      // Le lien existe bel et bien côté serveur, seule la copie automatique
      // a échoué : geste secondaire, pas de quoi alerter l'utilisateur.
    }
    window.setTimeout(() => setEtat("inactif"), 1500);
  }

  const titre = etat === "copie" ? "Lien copié" : etat === "erreur" ? "Erreur, réessayez" : "Partager cet article";
  const icone = etat === "copie" ? "check" : etat === "erreur" ? "error" : "share";

  return (
    <button onClick={partager} title={titre} className={`text-foreground-muted hover:text-foreground ${className}`}>
      <Icon name={icone} className="text-sm" />
    </button>
  );
}
