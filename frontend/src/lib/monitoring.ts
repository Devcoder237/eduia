/**
 * Supervision des erreurs côté navigateur — sans dépendance npm supplémentaire.
 *
 * Choix (documenté) : si `VITE_SENTRY_DSN` est défini, les erreurs non gérées sont envoyées
 * à l'endpoint « envelope » de Sentry via `fetch` (aucun SDK, bundle inchangé). Sans DSN : rien.
 * Aucune donnée personnelle n'est envoyée : seulement type, message tronqué et pile.
 */

interface ParsedDsn { readonly key: string; readonly endpoint: string; }

function parseDsn(dsn: string): ParsedDsn | null {
  try {
    const url = new URL(dsn);
    const projectId = url.pathname.replace(/^\//, "");
    if (!url.username || !projectId) return null;
    return { key: url.username, endpoint: `${url.protocol}//${url.host}/api/${projectId}/envelope/?sentry_key=${url.username}&sentry_version=7` };
  } catch {
    return null;
  }
}

function send(target: ParsedDsn, error: unknown): void {
  const err = error instanceof Error ? error : new Error(String(error));
  const eventId = crypto.randomUUID().replace(/-/g, "");
  const header = JSON.stringify({ event_id: eventId, sent_at: new Date().toISOString() });
  const item = JSON.stringify({ type: "event" });
  const payload = JSON.stringify({
    event_id: eventId,
    platform: "javascript",
    level: "error",
    environment: import.meta.env.MODE,
    exception: { values: [{ type: err.name, value: err.message.slice(0, 300), stacktrace: undefined }] },
    extra: { stack: (err.stack ?? "").slice(0, 4000) },
  });
  void fetch(target.endpoint, { method: "POST", body: `${header}\n${item}\n${payload}`, keepalive: true }).catch(() => {
    /* La supervision ne doit jamais perturber l'application : échec réseau ignoré volontairement. */
  });
}

/** Active la remontée d'erreurs si un DSN est configuré. */
export function initMonitoring(): void {
  const dsn = import.meta.env.VITE_SENTRY_DSN;
  const target = dsn ? parseDsn(dsn) : null;
  if (!target) return;
  window.addEventListener("error", (e) => send(target, e.error ?? e.message));
  window.addEventListener("unhandledrejection", (e) => send(target, e.reason));
  window.addEventListener("eduia:render-error", (e) => send(target, (e as CustomEvent<unknown>).detail));
}
