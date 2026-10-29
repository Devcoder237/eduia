import { useEffect, useMemo, useRef } from "react";
import { activityApi } from "../services/activity";
import { getAccessToken } from "../services/tokenStore";
import { ActiveTimeCounter, BEAT_EVERY_S, type ActivityModule } from "../utils/activity";

const INTERACTION_EVENTS = ["pointerdown", "pointermove", "keydown", "touchstart", "scroll", "wheel"] as const;

/**
 * Mesure le temps d'utilisation réel et l'envoie au serveur, sans aucun affichage.
 *
 * - Une seconde compte seulement si l'onglet est visible et si l'élève a interagi dans la dernière minute.
 * - Un signal part toutes les 30 s d'activité, quand l'onglet est masqué, et au changement de module.
 * - Passer `null` (page publique, déconnexion) arrête le suivi.
 * - En cas d'échec (réseau coupé), les secondes sont conservées et renvoyées 30 s plus tard.
 *   Limite connue : fermer brutalement l'onglet peut perdre jusqu'à 30 s.
 */
export function useActivityTracker(module: ActivityModule | null): void {
  const counter = useMemo(() => new ActiveTimeCounter(), []);
  const lastInteraction = useRef<number>(Date.now());
  const retryAfter = useRef<number>(0);

  useEffect(() => {
    if (module === null) return undefined;

    const flush = (): void => {
      if (getAccessToken() === null) return; // déconnecté : on n'envoie rien
      const seconds = counter.take();
      if (seconds <= 0) return;
      activityApi.beat(module, seconds).catch((error: unknown) => {
        counter.restore(seconds);
        retryAfter.current = Date.now() + BEAT_EVERY_S * 1000;
        console.debug("[activity] Signal non envoyé, nouvel essai plus tard.", error);
      });
    };

    const onInteraction = (): void => {
      lastInteraction.current = Date.now();
    };
    const onVisibility = (): void => {
      if (document.visibilityState === "hidden") flush();
    };

    const timer = window.setInterval(() => {
      const due = counter.tick(document.visibilityState === "visible", Date.now() - lastInteraction.current);
      if (due && Date.now() >= retryAfter.current) flush();
    }, 1000);

    for (const name of INTERACTION_EVENTS) window.addEventListener(name, onInteraction, { passive: true });
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      window.clearInterval(timer);
      for (const name of INTERACTION_EVENTS) window.removeEventListener(name, onInteraction);
      document.removeEventListener("visibilitychange", onVisibility);
      flush(); // changement de module : les secondes déjà comptées vont au module qui vient de se terminer
    };
  }, [module, counter]);
}