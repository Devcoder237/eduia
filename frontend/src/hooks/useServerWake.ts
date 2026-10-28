import { useCallback, useEffect, useState } from "react";
import { probeServer, type ServerState } from "../services";

const RETRY_DELAY_MS = 2_500;
const GIVE_UP_AFTER_MS = 120_000;

/**
 * Détecte le « démarrage à froid » de l'hébergeur gratuit (≈ 30 s après 15 min d'inactivité).
 *
 * - Au premier essai réussi : `ready`, aucun écran d'attente.
 * - Sinon : `waking` + secondes écoulées (pour un écran d'attente honnête), nouvel essai toutes les 2,5 s.
 * - Après 2 minutes : `down` + `retry()`.
 */
export function useServerWake(): { state: ServerState; elapsedSec: number; retry: () => void } {
  const [state, setState] = useState<ServerState>("checking");
  const [elapsedSec, setElapsedSec] = useState(0);
  const [round, setRound] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const startedAt = Date.now();
    let timer: number | undefined;
    let clock: number | undefined;
    const stopClock = () => {
      if (clock !== undefined) window.clearInterval(clock);
      clock = undefined;
    };
    setState("checking");
    setElapsedSec(0);

    const tick = async () => {
      let ok = false;
      try {
        ok = await probeServer(controller.signal);
      } catch (error) {
        if (controller.signal.aborted) return;
        console.warn("[wake] Sonde interrompue.", error);
      }
      if (controller.signal.aborted) return;
      const elapsed = Date.now() - startedAt;
      setElapsedSec(Math.floor(elapsed / 1000));
      if (ok) {
        stopClock();
        setState("ready");
      } else if (elapsed >= GIVE_UP_AFTER_MS) {
        stopClock();
        setState("down");
      } else {
        setState("waking");
        timer = window.setTimeout(() => void tick(), RETRY_DELAY_MS);
      }
    };
    void tick();

    clock = window.setInterval(() => setElapsedSec(Math.floor((Date.now() - startedAt) / 1000)), 1000);
    return () => {
      controller.abort();
      stopClock();
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [round]);

  const retry = useCallback(() => setRound((n) => n + 1), []);
  return { state, elapsedSec, retry };
}
