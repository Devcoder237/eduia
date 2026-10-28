/** Enregistre le service worker (coquille d'application uniquement) en production. */
export function registerServiceWorker(): void {
  if (!import.meta.env.PROD || !("serviceWorker" in navigator)) return;
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch((err: unknown) => {
      console.warn("Service worker non enregistré", err instanceof Error ? err.message : err);
    });
  });
}
