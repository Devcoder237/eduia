import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage, exerciseApi, isAbortError, type Exercise, type ExerciseResult } from "../services";
import { newRequestId } from "../utils/format";

/** Génération + correction d'un exercice. La clé d'idempotence évite tout doublon (et toute double facturation IA). */
export function useExercise() {
  const [exercise, setExercise] = useState<Exercise | null>(null);
  const [result, setResult] = useState<ExerciseResult | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [hintsShown, setHintsShown] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const busy = useRef(false);
  const requestId = useRef<string | null>(null);
  const abort = useRef<AbortController | null>(null);
  useEffect(() => () => abort.current?.abort(), []);

  const generate = useCallback(async (subject: string, level: string, topic: string) => {
    if (busy.current) return;
    busy.current = true;
    requestId.current ??= newRequestId();
    const controller = new AbortController();
    abort.current = controller;
    setIsGenerating(true);
    setError(null);
    setResult(null);
    setHintsShown(0);
    try {
      const created = await exerciseApi.generate({ subject, level, topic, request_id: requestId.current }, controller.signal);
      setExercise(created);
      requestId.current = null; // action terminée : la prochaine génération est une nouvelle intention
    } catch (e) {
      if (!isAbortError(e)) setError(errorMessage(e));
    } finally {
      busy.current = false;
      setIsGenerating(false);
    }
  }, []);

  const submit = useCallback(
    async (answer: string) => {
      if (!exercise || busy.current) return;
      busy.current = true;
      setIsSubmitting(true);
      setError(null);
      try {
        setResult(await exerciseApi.submit({ exercise_id: exercise.id, answer, hints_used: hintsShown }));
      } catch (e) {
        if (!isAbortError(e)) setError(errorMessage(e));
      } finally {
        busy.current = false;
        setIsSubmitting(false);
      }
    },
    [exercise, hintsShown],
  );

  const showNextHint = useCallback(() => {
    if (exercise) setHintsShown((n) => Math.min(n + 1, exercise.hints.length));
  }, [exercise]);

  const reset = useCallback(() => {
    setExercise(null);
    setResult(null);
    setHintsShown(0);
    setError(null);
    requestId.current = null;
  }, []);

  return { exercise, result, isGenerating, isSubmitting, hintsShown, error, generate, submit, showNextHint, reset };
}
