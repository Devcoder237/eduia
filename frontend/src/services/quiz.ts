import { AI_TIMEOUT_MS, request } from "./http";

export interface QuizQuestion {
  id: string;
  question: string;
  options: string[];
  subject: string;
  level: string;
  topic: string;
}

export interface QuizAnswerResult {
  question_id: string;
  correct: boolean;
  correct_index: number;
  explanation: string;
  score_delta: number;
  consecutive_wrong: number;
  /** Calibration de cette réponse ; absent si la confiance n'a pas été déclarée. */
  calibration?: Calibration | null;
}

/** Confiance déclarée avant la correction : 1 « je devine », 2 « plutôt sûr », 3 « sûr ». */
export type Confidence = 1 | 2 | 3;
export type Calibration = "overconfident" | "underconfident" | "calibrated";

export interface CalibrationProfile {
  answered: number;
  overconfident_rate: number;
  underconfident_rate: number;
  /** Absent tant que l'échantillon est trop petit pour conclure. */
  label: Calibration | null;
}

export type BadgeRarity = "common" | "rare" | "epic" | "legendary";

export interface BadgeAward {
  code: string;
  name: string;
  icon: string;
  description: string;
  rarity: BadgeRarity;
}

export interface CompleteSessionResult {
  ok: boolean;
  new_badges: BadgeAward[];
}

export const quizApi = {
  generate: (params: { subject: string; level: string; topic: string }, signal?: AbortSignal) =>
    request<QuizQuestion>("/quiz/generate", { query: { ...params }, timeoutMs: AI_TIMEOUT_MS, ...(signal ? { signal } : {}) }),

  /** `justification` : min. 10 caractères pour lycée/université, chaîne vide autorisée sinon. */
  answer: (data: { question_id: string; answer_index: number; justification: string; confidence?: Confidence }, signal?: AbortSignal) =>
    request<QuizAnswerResult>("/quiz/answer", { method: "POST", body: data, ...(signal ? { signal } : {}) }),

  getCalibration: (signal?: AbortSignal) => request<CalibrationProfile>("/quiz/calibration", signal ? { signal } : {}),

  /** Appelé UNE fois à la fin d'une série (incrémente `total_sessions` côté serveur). */
  completeSession: () => request<CompleteSessionResult>("/quiz/complete-session", { method: "POST" }),
};
