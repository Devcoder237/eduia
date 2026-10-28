import { request } from "./http";

export interface ClassroomOut {
  id: string;
  name: string;
  invite_code: string;
  level: string;
  student_count: number;
  created_at: string;
}

export interface JoinedClassroom {
  id: string;
  name: string;
  level: string;
  joined_at: string;
}

export interface WeakConcept {
  subject: string;
  concept: string;
  score: number;
}

export interface StudentSummary {
  user_id: string;
  full_name: string | null;
  username: string;
  total_sessions: number;
  total_questions: number;
  streak_days: number;
  subject_scores: Record<string, number>;
  weakest_concepts: WeakConcept[];
  joined_at: string;
}

export interface ClassAverage {
  subject: string;
  average_score: number;
}

export interface ClassroomReport {
  classroom_id: string;
  classroom_name: string;
  student_count: number;
  students: StudentSummary[];
  class_averages: ClassAverage[];
}

export interface JoinResult {
  ok: boolean;
  already_member: boolean;
  classroom_name: string;
}

export const classroomApi = {
  create: (data: { name: string; level: string }) =>
    request<ClassroomOut>("/classrooms/", { method: "POST", body: data }),

  listMine: (signal?: AbortSignal) => request<ClassroomOut[]>("/classrooms/mine", signal ? { signal } : {}),

  getReport: (classroomId: string, signal?: AbortSignal) =>
    request<ClassroomReport>(`/classrooms/${encodeURIComponent(classroomId)}/report`, signal ? { signal } : {}),

  join: (inviteCode: string) =>
    request<JoinResult>("/classrooms/join", { method: "POST", body: { invite_code: inviteCode }, retry: true }),

  /** Classes rejointes par l'élève connecté. */
  listJoined: (signal?: AbortSignal) => request<JoinedClassroom[]>("/classrooms/joined", signal ? { signal } : {}),

  /** L'élève quitte la classe (ses données restent les siennes, l'enseignant n'y a plus accès). */
  leave: (classroomId: string) =>
    request<{ status: string }>(`/classrooms/membership/${encodeURIComponent(classroomId)}`, { method: "DELETE" }),
};
