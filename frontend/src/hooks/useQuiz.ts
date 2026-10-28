import { useCallback, useState } from "react";
import { errorMessage, isAbortError, quizApi, type BadgeAward, type Confidence, type QuizAnswerResult, type QuizQuestion } from "../services";

export interface QuizRecapItem {
  question: string;
  options: string[];
  correctIndex: number;
  selectedIndex: number | null;
  correct: boolean;
  skipped: boolean;
  explanation: string;
}

interface QuizTarget {
  subject: string;
  level: string;
  topic: string;
}

/** Série de questions éclair : score, récapitulatif, passage de question, badges gagnés en fin de série. */
export function useQuiz() {
  const [question, setQuestion] = useState<QuizQuestion | null>(null);
  const [result, setResult] = useState<QuizAnswerResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedOption, setSelectedOption] = useState<number | null>(null);
  const [score, setScore] = useState(0);
  const [questionCount, setQuestionCount] = useState(0);
  const [targetCount, setTargetCount] = useState(0);
  const [finished, setFinished] = useState(false);
  const [recap, setRecap] = useState<QuizRecapItem[]>([]);
  const [newBadges, setNewBadges] = useState<BadgeAward[]>([]);
  const [error, setError] = useState<string | null>(null);

  const fetchQuestion = useCallback(async (target: QuizTarget, isFirst: boolean) => {
    setIsLoading(true);
    setError(null);
    setResult(null);
    setSelectedOption(null);
    try {
      setQuestion(await quizApi.generate(target));
      setQuestionCount((n) => (isFirst ? 1 : n + 1));
    } catch (e) {
      if (!isAbortError(e)) setError(errorMessage(e));
    } finally {
      setIsLoading(false);
    }
  }, []);

  const start = useCallback(
    async (target: QuizTarget, count: number) => {
      setScore(0);
      setQuestionCount(0);
      setFinished(false);
      setRecap([]);
      setNewBadges([]);
      setTargetCount(count);
      await fetchQuestion(target, true);
    },
    [fetchQuestion],
  );

  const completeSeries = useCallback(async () => {
    setFinished(true);
    try {
      const done = await quizApi.completeSession();
      setNewBadges(done.new_badges);
    } catch (e) {
      // La série est terminée pour l'élève ; seul le décompte serveur (et d'éventuels badges) est perdu.
      console.warn("[quiz] Fin de série non enregistrée.", e);
    }
  }, []);

  const answer = useCallback(
    async (index: number, justification: string, confidence?: Confidence) => {
      if (!question || result || isLoading) return;
      setSelectedOption(index);
      setIsLoading(true);
      setError(null);
      try {
        const res = await quizApi.answer({ question_id: question.id, answer_index: index, justification, ...(confidence ? { confidence } : {}) });
        setResult(res);
        if (res.correct) setScore((s) => s + 1);
        setRecap((r) => [
          ...r,
          { question: question.question, options: question.options, correctIndex: res.correct_index, selectedIndex: index, correct: res.correct, skipped: false, explanation: res.explanation },
        ]);
      } catch (e) {
        setSelectedOption(null);
        if (!isAbortError(e)) setError(errorMessage(e));
      } finally {
        setIsLoading(false);
      }
    },
    [question, result, isLoading],
  );

  const advance = useCallback(
    async (target: QuizTarget) => {
      if (questionCount >= targetCount) await completeSeries();
      else await fetchQuestion(target, false);
    },
    [questionCount, targetCount, completeSeries, fetchQuestion],
  );

  /** Passe la question : aucun appel de correction, aucun point, mais la série avance. */
  const skip = useCallback(
    async (target: QuizTarget) => {
      if (!question || result) return;
      setRecap((r) => [
        ...r,
        { question: question.question, options: question.options, correctIndex: -1, selectedIndex: null, correct: false, skipped: true, explanation: "" },
      ]);
      await advance(target);
    },
    [question, result, advance],
  );

  const reset = useCallback(() => {
    setQuestion(null);
    setResult(null);
    setSelectedOption(null);
    setScore(0);
    setQuestionCount(0);
    setFinished(false);
    setRecap([]);
    setNewBadges([]);
    setTargetCount(0);
    setError(null);
  }, []);

  return { question, result, isLoading, selectedOption, score, questionCount, targetCount, finished, recap, newBadges, error, start, answer, skip, next: advance, reset };
}
