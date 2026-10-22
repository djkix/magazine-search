// Configuration ESLint « flat » (ESLint 9). `next lint` est déprécié depuis
// Next.js 15.5 : le script `npm run lint` appelle désormais ESLint
// directement, avec les règles recommandées par Next (core-web-vitals).
import { dirname } from "path";
import { fileURLToPath } from "url";
import { FlatCompat } from "@eslint/eslintrc";

const compat = new FlatCompat({ baseDirectory: dirname(fileURLToPath(import.meta.url)) });

const config = [
  { ignores: [".next/**", "node_modules/**", "public/**", "next-env.d.ts"] },
  ...compat.extends("next/core-web-vitals", "next/typescript"),
];

export default config;
