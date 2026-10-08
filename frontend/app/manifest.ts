import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "L'Archive — Magazine Search",
    short_name: "L'Archive",
    description: "Recherche plein texte dans la collection de magazines",
    start_url: "/",
    display: "standalone",
    background_color: "#051424",
    theme_color: "#051424",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
