import { request } from "./http";

export interface CountBySubject {
  subject: string;
  count: number;
}

export interface CountByLevel {
  level: string;
  count: number;
}

export interface CountByDay {
  date: string;
  count: number;
}

export interface AdminStats {
  total_users: number;
  active_users_7d: number;
  total_sessions: number;
  total_messages: number;
  total_exercises: number;
  total_quiz_attempts: number;
  subject_popularity: CountBySubject[];
  level_distribution: CountByLevel[];
  signups_by_day: CountByDay[];
}

export const adminApi = {
  getStats: (signal?: AbortSignal) => request<AdminStats>("/admin/stats", signal ? { signal } : {}),
};
