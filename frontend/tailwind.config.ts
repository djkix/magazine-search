import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "#051424",
        surface: "#0b1f34",
        "surface-hover": "#12293f",
        "outline-variant": "#1e3350",
        primary: {
          DEFAULT: "#ff2d78",
          light: "#ffb1c0",
        },
        foreground: {
          DEFAULT: "#d4e4fa",
          muted: "#8ba0c2",
        },
      },
      fontFamily: {
        serif: ["var(--font-serif)", "Georgia", "serif"],
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
