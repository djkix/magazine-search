"use client";

import Script from "next/script";
import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";

interface GoogleSignInButtonProps {
  // Fourni par la page appelante (lu depuis GET /auth/google/client-id) :
  // NEXT_PUBLIC_GOOGLE_CLIENT_ID ne peut pas fonctionner ici, Next.js le
  // fige au build d'une image Docker déjà construite une fois pour tous
  // les self-hosters, alors que cet identifiant est propre à chacun.
  clientId: string;
  onSuccess: () => void;
  onError: (message: string) => void;
}

export default function GoogleSignInButton({ clientId, onSuccess, onError }: GoogleSignInButtonProps) {
  const buttonRef = useRef<HTMLDivElement>(null);
  const [scriptLoaded, setScriptLoaded] = useState(false);

  useEffect(() => {
    if (!clientId || !scriptLoaded || !buttonRef.current || !window.google) {
      return;
    }

    async function handleCredentialResponse(response: { credential: string }) {
      try {
        await api.post("/auth/google", { credential: response.credential });
        onSuccess();
      } catch (err) {
        onError(err instanceof ApiError ? err.message : "Erreur de connexion");
      }
    }

    window.google.accounts.id.initialize({
      client_id: clientId,
      callback: handleCredentialResponse,
    });
    window.google.accounts.id.renderButton(buttonRef.current, {
      theme: "filled_black",
      size: "large",
      shape: "pill",
      width: 320,
    });
  }, [clientId, scriptLoaded, onSuccess, onError]);

  // Les auto-hébergeurs n'ayant pas configuré d'identifiant client OAuth ne
  // doivent voir apparaître aucun bouton mort : on ne rend rien.
  if (!clientId) {
    return null;
  }

  return (
    <>
      <Script
        src="https://accounts.google.com/gsi/client"
        strategy="afterInteractive"
        onLoad={() => setScriptLoaded(true)}
      />
      <div ref={buttonRef} className="flex justify-center" />
    </>
  );
}
