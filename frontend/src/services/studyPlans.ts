import { AI_TIMEOUT_MS, request } from "./http";

export interface StudyPlanDay {
  date: string;
  day_label: string;
  subjects: string[];
  tasks: string[];
  completed: boolean;
}

export interface StudyPlanOut {
  id: string;
  title: string;
  exam_label: string;
  target_date: string;
  subjects: string[];
  level: string;
  days: StudyPlanDay[];
  is_active: boolean;
  created_at: string;
  /** Information à afficher (ex. plan simplifié car l'IA n'a pas répondu). */
  notice: string | null;
}

export interface StudyPlanInput {
  exam_label: string;
  target_date: string;
  subjects: string[];
  level: string;
}

export const studyPlanApi = {
  generate: (data: StudyPlanInput, signal?: AbortSignal) =>
    request<StudyPlanOut>("/study-plans/generate", { method: "POST", body: data, timeoutMs: AI_TIMEOUT_MS, ...(signal ? { signal } : {}) }),

  listActive: (signal?: AbortSignal) => request<StudyPlanOut[]>("/study-plans/active", signal ? { signal } : {}),

  get: (planId: string, signal?: AbortSignal) =>
    request<StudyPlanOut>(`/study-plans/${encodeURIComponent(planId)}`, signal ? { signal } : {}),

  toggleDay: (planId: string, dayIndex: number, completed: boolean) =>
    request<StudyPlanOut>(`/study-plans/${encodeURIComponent(planId)}/day`, {
      method: "PUT",
      body: { day_index: dayIndex, completed },
      retry: true,
    }),

  /** Réorganise les jours futurs non complétés selon la maîtrise actuelle ; l'historique n'est jamais réécrit. */
  refresh: (planId: string) =>
    request<StudyPlanOut>(`/study-plans/${encodeURIComponent(planId)}/refresh`, { method: "PUT", timeoutMs: AI_TIMEOUT_MS }),

  archive: (planId: string) =>
    request<{ status: string }>(`/study-plans/${encodeURIComponent(planId)}`, { method: "DELETE" }),
};
