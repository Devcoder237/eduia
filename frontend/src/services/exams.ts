import { AI_TIMEOUT_MS, request } from "./http";

export interface ExamQuestion {
  attempt_id: string;
  question: string;
  options: string[];
  index: number;
  total: number;
}

export interface ExamStartInput {
  subject: string;
  level: string;
  exam_label?: string;
  question_count?: number;
  duration_min?: number;
  /** Clé d'idempotence : un double-clic ne crée qu'un seul examen. */
  request_id?: string;
}

export interface ExamStarted {
  exam_id: string;
  /** Durée totale de l'épreuve, en secondes (référence serveur). */
  duration_sec: number;
  question_count: number;
  /** Échéance serveur (ISO 8601) : le chronomètre affiché en dérive. */
  expires_at: string;
  first_question: ExamQuestion;
}

export interface ExamAnswerResponse {
  next_question: ExamQuestion | null;
  finished: boolean;
  /** Vrai si le temps imparti était écoulé : la réponse n'a pas été prise en compte. */
  time_expired: boolean;
}

export interface ExamDetail {
  question: string;
  options: string[];
  correct_index: number;
  answer_index: number | null;
  is_correct: boolean | null;
  explanation: string | null;
}

export interface ExamResult {
  exam_id: string;
  subject: string;
  level: string;
  exam_label: string;
  score: number;
  correct_count: number;
  total: number;
  duration_sec: number;
  details: ExamDetail[];
}

export const examApi = {
  start: (data: ExamStartInput, signal?: AbortSignal) =>
    request<ExamStarted>("/exams/start", { method: "POST", body: data, timeoutMs: AI_TIMEOUT_MS, ...(signal ? { signal } : {}) }),

  /** `time_expired` = temps écoulé : l'appelant doit alors terminer l'examen. */
  answer: (data: { attempt_id: string; answer_index?: number }, signal?: AbortSignal) =>
    request<ExamAnswerResponse>("/exams/answer", { method: "POST", body: data, ...(signal ? { signal } : {}) }),

  finish: (examId: string, signal?: AbortSignal) =>
    request<ExamResult>(`/exams/${encodeURIComponent(examId)}/finish`, { method: "POST", retry: true, ...(signal ? { signal } : {}) }),

  history: (signal?: AbortSignal) => request<ExamResult[]>("/exams/history", signal ? { signal } : {}),
};
