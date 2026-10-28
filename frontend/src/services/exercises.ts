import { AI_TIMEOUT_MS, request } from "./http";

export interface Exercise {
  id: string;
  subject: string;
  level: string;
  difficulty: string;
  topic: string;
  statement: string;
  hints: string[];
  concepts: string[];
  estimated_min: number;
}

export interface RubricScoreItem {
  critere: string;
  points_max: number;
  points_obtenus: number;
  taux: number;
  justification: string;
}

export interface ExerciseResult {
  exercise_id: string;
  score: number;
  correct: boolean;
  partial: boolean;
  feedback: string;
  errors: string[];
  concepts_to_review: string[];
  positive_points: string[];
  rubric_breakdown: RubricScoreItem[];
}

export interface GuidedReviewItem {
  priority: string;
  subject: string;
  concept: string | null;
  score: number;
  reason: string;
  action: string;
}

export interface GuidedReview {
  items: GuidedReviewItem[];
  has_gaps: boolean;
}

export interface ExerciseGenerateInput {
  subject: string;
  level: string;
  topic: string;
  difficulty?: string;
  /** Clé d'idempotence : un double-clic ne génère (et ne facture) qu'un seul exercice. */
  request_id?: string;
}

export const exerciseApi = {
  generate: (data: ExerciseGenerateInput, signal?: AbortSignal) =>
    request<Exercise>("/exercises/generate", { method: "POST", body: data, timeoutMs: AI_TIMEOUT_MS, ...(signal ? { signal } : {}) }),

  submit: (data: { exercise_id: string; answer: string; hints_used?: number }, signal?: AbortSignal) =>
    request<ExerciseResult>("/exercises/submit", { method: "POST", body: data, timeoutMs: AI_TIMEOUT_MS, ...(signal ? { signal } : {}) }),

  guidedReview: (subject?: string, signal?: AbortSignal) =>
    request<GuidedReview>("/exercises/guided-review", {
      method: "POST",
      body: { subject },
      retry: true,
      ...(signal ? { signal } : {}),
    }),
};
