"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import Icon from "@/components/ui/Icon";
import Input from "@/components/ui/Input";
import Button from "@/components/ui/Button";
import GoogleSignInButton from "@/components/auth/GoogleSignInButton";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await api.post("/login", { email, password });
      router.push("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erreur de connexion");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="w-full max-w-sm">
      <div className="mb-8 flex flex-col items-center text-center">
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl border border-outline-variant bg-surface">
          <Icon name="auto_stories" className="text-2xl text-primary" />
        </div>
        <h1 className="font-serif text-2xl font-semibold text-foreground">L&apos;Archive</h1>
        <p className="mt-1 font-mono text-xs uppercase tracking-wider text-foreground-muted">Accès privé</p>
      </div>

      <form
        onSubmit={handleSubmit}
        className="space-y-5 rounded-xl border border-outline-variant bg-surface/60 p-6 backdrop-blur-sm"
      >
        <Input
          id="email"
          type="email"
          label="Email"
          required
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <Input
          id="password"
          type="password"
          label="Mot de passe"
          required
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        <Button type="submit" disabled={loading} className="w-full">
          {loading ? "Connexion..." : "Se connecter"}
        </Button>
      </form>

      {/* Partagée entre les deux méthodes de connexion : placée ni dans le
          formulaire ni collée au bouton Google, pour ne pas sembler propre à
          l'une ou l'autre selon laquelle a échoué. */}
      {error && <p className="mt-4 text-center text-sm text-red-400">{error}</p>}

      <div className="my-6 flex items-center gap-3">
        <div className="h-px flex-1 bg-outline-variant" />
        <span className="font-mono text-xs uppercase tracking-wider text-foreground-muted">ou</span>
        <div className="h-px flex-1 bg-outline-variant" />
      </div>

      <GoogleSignInButton onSuccess={() => router.push("/")} onError={setError} />

      <p className="mt-6 text-center text-xs text-foreground-muted">
        Compte oublié ou perdu ? Contactez l&apos;administrateur : les accès sont gérés manuellement.
      </p>
    </div>
  );
}
