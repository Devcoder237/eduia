import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage, isAbortError } from "../services";

export interface Resource<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
  /** Remplace localement la donnée (mise à jour optimiste). */
  setData: (value: T | null) => void;
}

/**
 * Charge une ressource au montage (et à chaque changement de `deps`), annule la requête
 * en cours si l'écran est quitté, et expose chargement + erreur lisible.
 */
export function useResource<T>(loader: (signal: AbortSignal) => Promise<T>, deps: readonly unknown[]): Resource<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    loaderRef
      .current(controller.signal)
      .then((value) => {
        if (!controller.signal.aborted) setData(value);
      })
      .catch((e: unknown) => {
        if (isAbortError(e) || controller.signal.aborted) return;
        setError(errorMessage(e));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick, ...deps]);

  const reload = useCallback(() => setTick((n) => n + 1), []);
  return { data, loading, error, reload, setData };
}
