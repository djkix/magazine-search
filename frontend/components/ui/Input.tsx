"use client";

import type { InputHTMLAttributes } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
}

export default function Input({ label, id, className = "", ...props }: InputProps) {
  return (
    <div className="space-y-1.5">
      {label && (
        <label htmlFor={id} className="block font-mono text-xs uppercase tracking-wider text-foreground-muted">
          {label}
        </label>
      )}
      <input
        id={id}
        className={`w-full rounded-xl border border-outline-variant bg-surface px-4 py-2.5 text-sm text-foreground outline-none transition placeholder:text-foreground-muted/60 focus:border-primary ${className}`}
        {...props}
      />
    </div>
  );
}
