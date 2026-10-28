import { request } from "./http";

export type ReportReason = "wrong" | "inappropriate" | "confusing" | "other";

export interface ReportPayload {
  reason: ReportReason;
  /** Extrait court de la réponse signalée (600 caractères maximum). */
  excerpt: string;
  comment?: string;
}

/** Signale une réponse du tuteur. */
export async function sendReport(payload: ReportPayload): Promise<void> {
  const body = {
    reason: payload.reason,
    excerpt: payload.excerpt.slice(0, 600),
    ...(payload.comment?.trim() ? { comment: payload.comment.trim().slice(0, 500) } : {}),
  };
  await request<{ status: string }>("/reports", { method: "POST", body });
}
