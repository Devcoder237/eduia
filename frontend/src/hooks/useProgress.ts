import { useEffect, useState } from "react";
import {
  errorMessage, exerciseApi, isAbortError, progressApi, quizApi,
  type CalibrationProfile, type GuidedReview, type MasteryConceptOption, type MasteryHistoryPoint,
} from "../services";
import { useResource } from "./useResource";

export function useProgress() {
  return useResource((signal) => progressApi.getDashboard(signal), []);
}

/** Profil de calibration de la confiance (surconfiance / sous-confiance). */
export function useCalibration() {
  return useResource<CalibrationProfile>((signal) => quizApi.getCalibration(signal), []);
}

export function useDetailedStats() {
  return useResource((signal) => progressApi.getDetailedStats(signal), []);
}

/** Évolution de la maîtrise d'un concept : liste des concepts suivis + courbe du concept choisi. */
export function useMasteryEvolution() {
  const concepts = useResource<MasteryConceptOption[]>((signal) => progressApi.getMasteryConcepts(signal), []);
  const [selected, setSelected] = useState<{ subject: string; concept: string } | null>(null);
  const [history, setHistory] = useState<MasteryHistoryPoint[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);

  useEffect(() => {
    const first = concepts.data?.[0];
    if (first && selected === null) setSelected({ subject: first.subject, concept: first.concept });
  }, [concepts.data, selected]);

  useEffect(() => {
    if (!selected) {
      setHistory([]);
      return undefined;
    }
    const controller = new AbortController();
    setIsLoadingHistory(true);
    setHistoryError(null);
    progressApi
      .getMasteryHistory(selected.subject, selected.concept, controller.signal)
      .then((points) => {
        if (!controller.signal.aborted) setHistory(points);
      })
      .catch((e: unknown) => {
        if (!isAbortError(e)) setHistoryError(errorMessage(e));
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoadingHistory(false);
      });
    return () => controller.abort();
  }, [selected]);

  return {
    concepts: concepts.data ?? [], isLoadingConcepts: concepts.loading, conceptsError: concepts.error,
    selected, setSelected, history, isLoadingHistory, historyError,
  };
}

/** Révision guidée : charge à la demande les lacunes prioritaires. */
export function useGuidedReview() {
  const [review, setReview] = useState<GuidedReview | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async (subject?: string) => {
    setIsLoading(true);
    setError(null);
    try {
      setReview(await exerciseApi.guidedReview(subject));
    } catch (e) {
      if (!isAbortError(e)) setError(errorMessage(e));
    } finally {
      setIsLoading(false);
    }
  };

  return { items: review?.items ?? [], hasGaps: review?.has_gaps ?? true, isLoading, error, load };
}
