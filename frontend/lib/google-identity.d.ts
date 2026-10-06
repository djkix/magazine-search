// Typage minimal de l'API Google Identity Services (GSI), chargée via un
// <script> externe (pas de paquet npm). Juste assez pour éviter `any` côté
// appelant : https://developers.google.com/identity/gsi/web/reference/js-reference
export {};

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize(config: {
            client_id: string;
            callback: (response: { credential: string; select_by: string }) => void;
          }): void;
          renderButton(
            parent: HTMLElement,
            options: {
              theme?: "outline" | "filled_blue" | "filled_black";
              size?: "small" | "medium" | "large";
              shape?: "rectangular" | "pill" | "circle" | "square";
              width?: number;
            }
          ): void;
        };
      };
    };
  }
}
