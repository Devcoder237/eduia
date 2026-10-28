import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage, examApi, isAbortError, type ExamQuestion, type ExamResult } from "../services";
import { newRequestId } from "../utils/format";
import { useResource } from "./useResource";

export interface ExamConfig {
  subject: string;
  level: string;
  examLabel: string;
  questionCount: number;
  durationMin: number;
}

/**
 * Examen blanc. Le serveur fait foi pour le temps : on calcule l'échéance locale à partir de la
 * durée renvoyée (insensible à une horloge d'appareil déréglée) et on termine l'épreuve quand
 * le serveur signale `time_expired`.
 */
export function useExam() {
  const [examId, setExamId] = useState<string | null>(null);
  const [question, setQuestion] = useState<ExamQuestion | null>(null);
  const [deadline, setDeadline] = useState<number | null>(null);
  const [result, setResult] = useState<ExamResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isFinishing, setIsFinishing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const busy = useRef(false);
  const requestId = useRef<string | null>(null);
  const abort = useRef<AbortController | null>(null);
  useEffect(() => () => abort.current?.abort(), []);

  const start = useCallback(async (config: ExamConfig) => {
    if (busy.current) return;
    busy.current = true;
    requestId.current ??= newRequestId();
    const controller = new AbortController();
    abort.current = controller;
    setIsLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await examApi.start(
        {
          subject: config.subject,
          level: config.level,
          exam_label: config.examLabel,
          question_count: config.questionCount,
          duration_min: config.durationMin,
          request_id: requestId.current,
        },
        controller.signal,
      );
      requestId.current = null;
      setExamId(res.exam_id);
      setDeadline(Date.now() + res.duration_sec * 1000);
      setQuestion(res.first_question);
    } catch (e) {
      if (!isAbortError(e)) setError(errorMessage(e));
    } finally {
      busy.current = false;
      setIsLoading(false);
    }
  }, []);

  const finish = useCallback(async () => {
    if (!examId) return null;
    setIsFinishing(true);
    setQuestion(null);
    setError(null);
    try {
      const res = await examApi.finish(examId);
      setResult(res);
      return res;
    } catch (e) {
      if (!isAbortError(e)) setError(errorMessage(e));
      return null;
    } finally {
      setIsFinishing(false);
    }
  }, [examId]);

  /** `undefined` = question passée. */
  const answer = useCallback(
    async (answerIndex?: number) => {
      if (!question || busy.current) return;
      busy.current = true;
      setIsLoading(true);
      setError(null);
      try {
        const res = await examApi.answer({ attempt_id: question.attempt_id, ...(answerIndex === undefined ? {} : { answer_index: answerIndex }) });
        if (res.finished || res.time_expired || !res.next_question) {
          busy.current = false;
          await finish();
        } else {
          setQuestion(res.next_question);
        }
      } catch (e) {
        if (!isAbortError(e)) setError(errorMessage(e));
      } finally {
        busy.current = false;
        setIsLoading(false);
      }
    },
    [question, finish],
  );

  const reset = useCallback(() => {
    setExamId(null);
    setQuestion(null);
    setDeadline(null);
    setResult(null);
    setIsFinishing(false);
    setError(null);
    requestId.current = null;
  }, []);

  return { examId, question, deadline, result, isLoading, isFinishing, error, start, answer, finish, reset };
}

/** Historique des examens blancs de l'élève. */
export function useExamHistory() {
  return useResource((signal) => examApi.history(signal), []);
}
