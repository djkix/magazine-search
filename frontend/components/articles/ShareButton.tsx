"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import Icon from "@/components/ui/Icon";

// Les deux cibles partagent la même forme de réponse ({token}) et la même
// logique de copie/erreur côté frontend ; seuls le endpoint et le préfixe
// de l'URL publique diffèrent.
const CONFIG = {
  article: { endpoint: (id: number) => `/articles/${id}/share`, urlPrefix: "/partage" },
  magazine: { endpoint: (id: number) => `/magazines/${id}/share`, urlPrefix: "/partage/magazine" },
} as const;

export default function ShareButton({
  kind,
  id,
  className = "",
}: {
  kind: keyof typeof CONFIG;
  id: number;
  className?: string;
}) {
  const [etat, setEtat] = useState<"inactif" | "copie" | "erreur">("inactif");
  const { endpoint, urlPrefix } = CONFIG[kind];
  const titreArticleOuNumero = kind === "article" ? "cet article" : "ce numéro";

  async function partager(e: React.MouseEvent) {
    // Les listes qui utilisent ce bouton l'imbriquent dans une zone
    // cliquable plus large (toute la ligne/carte ouvre l'article ou le
    // numéro) : sans ceci, le clic sur "Partager" déclencherait aussi la
    // navigation.
    e.preventDefault();
    e.stopPropagation();

    let token: string;
    try {
      ({ token } = await api.post<{ token: string }>(endpoint(id)));
    } catch {
      // Échec réel de la création du lien (ressource supprimée entre-temps,
      // backend indisponible...) : contrairement à un échec de presse-
      // papiers ci-dessous, l'utilisateur croirait sinon avoir un lien
      // fonctionnel alors que rien n'a été copié.
      setEtat("erreur");
      window.setTimeout(() => setEtat("inactif"), 1500);
      return;
    }

    const url = `${window.location.origin}${urlPrefix}/${token}`;

    // Sur mobile, navigator.share ouvre le sélecteur natif du système
    // (WhatsApp, Messages, Mail...) : c'est exactement ce qu'on veut, plutôt
    // que de copier le lien et obliger à aller le coller soi-même ailleurs.
    if (typeof navigator.share === "function") {
      try {
        await navigator.share({ url });
        return;
      } catch (err) {
        // L'utilisateur a fermé le sélecteur sans choisir d'app : un choix
        // délibéré, pas un échec à signaler. Toute autre erreur retombe sur
        // la copie presse-papiers ci-dessous.
        if (err instanceof DOMException && err.name === "AbortError") return;
      }
    }

    try {
      await navigator.clipboard.writeText(url);
      setEtat("copie");
    } catch {
      // Le lien existe bel et bien côté serveur, seule la copie automatique
      // a échoué : geste secondaire, pas de quoi alerter l'utilisateur.
    }
    window.setTimeout(() => setEtat("inactif"), 1500);
  }

  const titre = etat === "copie" ? "Lien copié" : etat === "erreur" ? "Erreur, réessayez" : `Partager ${titreArticleOuNumero}`;
  const icone = etat === "copie" ? "check" : etat === "erreur" ? "error" : "share";

  return (
    <button onClick={partager} title={titre} className={`text-foreground-muted hover:text-foreground ${className}`}>
      <Icon name={icone} className="text-sm" />
    </button>
  );
}
