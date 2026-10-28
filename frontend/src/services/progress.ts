import { request } from "./http";
import type { BadgeRarity } from "./quiz";

export type Trend = "up" | "down" | "stable";

export interface SubjectScore {
  subject: string;
  score: number;
  /** Tendance calculée par le serveur. */
  trend: Trend;
}

export interface Recommendation {
  priority: string;
  subject: string;
  concept: string | null;
  score: number;
  reason: string;
  action: string;
}

export interface BadgeStatus {
  code: string;
  name: string;
  icon: string;
  description: string;
  rarity: BadgeRarity;
  earned_at: string | null;
}

export interface HeatmapDay {
  date: string;
  /** 0 (aucune activité) à 3 (forte activité). */
  level: number;
}

export interface RecentSession {
  id: string;
  subject: string;
  duration: number | null;
  started_at: string;
}

export interface ProgressDashboard {
  total_sessions: number;
  total_questions: number;
  streak_days: number;
  subject_scores: SubjectScore[];
  recent_sessions: RecentSession[];
  recommendations: Recommendation[];
  badges: BadgeStatus[];
  heatmap: HeatmapDay[];
}

export interface WeeklyProgress {
  week_label: string;
  questions: number;
  avg_score: number;
}

export interface DetailedStats {
  avg_session_min: number;
  total_time_min: number;
  weekly_progress: WeeklyProgress[];
  sessions_by_subject: Record<string, number>;
  best_subject: string | null;
  weakest_subject: string | null;
}

export interface MasteryConceptOption {
  subject: string;
  concept: string;
  points_count: number;
  latest_score: number;
}

export interface MasteryHistoryPoint {
  recorded_at: string;
  score: number;
}

export const progressApi = {
  getDashboard: (signal?: AbortSignal) => request<ProgressDashboard>("/progress/dashboard", signal ? { signal } : {}),
  getDetailedStats: (signal?: AbortSignal) => request<DetailedStats>("/progress/detailed-stats", signal ? { signal } : {}),
  getMasteryConcepts: (signal?: AbortSignal) => request<MasteryConceptOption[]>("/progress/mastery-concepts", signal ? { signal } : {}),
  getMasteryHistory: (subject: string, concept: string, signal?: AbortSignal) =>
    request<MasteryHistoryPoint[]>("/progress/mastery-history", { query: { subject, concept }, ...(signal ? { signal } : {}) }),
};
