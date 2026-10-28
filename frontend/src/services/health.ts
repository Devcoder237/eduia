import { API_BASE_URL } from "./http";

/** État du serveur : l'hébergeur gratuit endort l'API après 15 min d'inactivité (réveil ≈ 30 s). */
export type ServerState = "checking" | "ready" | "waking" | "down";

const PROBE_TIMEOUT_MS = 6_000;

/**
 * Interroge `/health` (qui ne touche pas la base de données).
 * Renvoie `true` si le serveur répond 2xx avant le délai.
 */
export async function probeServer(signal?: AbortSignal): Promise<boolean> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), PROBE_TIMEOUT_MS);
  const onAbort = () => controller.abort();
  signal?.addEventListener("abort", onAbort, { once: true });
  try {
    const response = await fetch(`${API_BASE_URL}/health`, { cache: "no-store", signal: controller.signal });
    return response.ok;
  } catch (error) {
    // Réseau coupé, serveur en cours de démarrage ou délai dépassé : le serveur n'est simplement pas prêt.
    if (signal?.aborted) throw error;
    return false;
  } finally {
    window.clearTimeout(timer);
    signal?.removeEventListener("abort", onAbort);
  }
}
