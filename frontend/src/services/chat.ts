import { AI_TIMEOUT_MS, ApiError, isAbortError, request, requestStream, requestVoid } from "./http";
import { translate } from "../i18n";

export interface SessionKey {
  subject: string;
  level: string;
  mode: string;
}

export interface SessionStarted extends SessionKey {
  session_id: string;
  started_at: string;
}

export interface ChatMessageRequest extends SessionKey {
  session_id: string;
  message: string;
  document_context?: string | null;
}

export interface ChatMessageResponse extends SessionKey {
  session_id: string;
  message: string;
}

export interface UploadedDocument {
  filename: string;
  text: string;
  truncated: boolean;
  char_count: number;
}

export interface ChatHistoryItem {
  id: string;
  role: string;
  content: string;
  created_at: string;
}

export interface SessionSummary extends SessionKey {
  session_id: string;
  started_at: string;
  ended_at: string | null;
  msg_count: number;
  preview: string;
}

export interface StreamHandlers {
  /** Reçoit le texte cumulé à chaque morceau reçu. */
  onChunk: (textSoFar: string) => void;
  /** Reçoit le message d'erreur envoyé par le serveur dans le flux (`{"error": "..."}`). */
  onError?: (message: string) => void;
  signal?: AbortSignal;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Interprète un évènement SSE complet ; renvoie `true` si le flux est terminé. */
function handleEvent(
  rawEvent: string,
  state: { text: string },
  handlers: StreamHandlers,
): boolean {
  const dataLines = rawEvent
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart());
  if (dataLines.length === 0) return false;
  const payload = dataLines.join("\n").trim();
  if (payload === "[DONE]") return true;
  let parsed: unknown;
  try {
    parsed = JSON.parse(payload);
  } catch (error) {
    console.warn("[chat] Évènement SSE ignoré (JSON invalide).", error);
    return false;
  }
  if (!isRecord(parsed)) return false;
  if (typeof parsed.error === "string") {
    handlers.onError?.(parsed.error);
    return true;
  }
  if (typeof parsed.text === "string" && parsed.text !== "") {
    state.text += parsed.text;
    handlers.onChunk(state.text);
  }
  return false;
}

export const chatApi = {
  getLatestSession: (key: SessionKey, signal?: AbortSignal) =>
    request<{ session_id: string | null }>("/chat/session/latest", { query: { ...key }, ...(signal ? { signal } : {}) }),

  startSession: (key: SessionKey, signal?: AbortSignal) =>
    request<SessionStarted>("/chat/session", { method: "POST", body: key, ...(signal ? { signal } : {}) }),

  sendMessage: (data: ChatMessageRequest, signal?: AbortSignal) =>
    request<ChatMessageResponse>("/chat/message", { method: "POST", body: data, timeoutMs: AI_TIMEOUT_MS, ...(signal ? { signal } : {}) }),

  /** Extrait le texte d'un document importé (PDF/Word/PowerPoint) ; rien n'est stocké côté serveur. */
  uploadDocument: (file: File, signal?: AbortSignal) => {
    const formData = new FormData();
    formData.append("file", file);
    return request<UploadedDocument>("/chat/upload", {
      method: "POST",
      formData,
      timeoutMs: AI_TIMEOUT_MS,
      ...(signal ? { signal } : {}),
    });
  },

  /**
   * Lit la réponse de l'IA en flux (SSE). Renvoie le texte complet reçu.
   * Lève ApiError si la réponse HTTP n'est pas OK ; un `{"error": ...}` dans le flux appelle `onError`.
   */
  streamMessage: async (data: ChatMessageRequest, handlers: StreamHandlers): Promise<string> => {
    const response = await requestStream("/chat/stream", {
      method: "POST",
      body: data,
      timeoutMs: AI_TIMEOUT_MS,
      ...(handlers.signal ? { signal: handlers.signal } : {}),
    });
    if (!response.body) throw new ApiError(response.status, translate("error.badResponse"));

    const reader = response.body.getReader();
    const onAbort = () => {
      reader.cancel().catch((error: unknown) => console.warn("[chat] Annulation du flux impossible.", error));
    };
    handlers.signal?.addEventListener("abort", onAbort, { once: true });

    const decoder = new TextDecoder();
    const state = { text: "" };
    let buffer = "";
    let finished = false;
    try {
      while (!finished) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
        let boundary = buffer.indexOf("\n\n");
        while (boundary !== -1 && !finished) {
          const rawEvent = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);
          finished = handleEvent(rawEvent, state, handlers);
          boundary = buffer.indexOf("\n\n");
        }
      }
      buffer += decoder.decode();
      if (!finished && buffer.trim() !== "") handleEvent(buffer, state, handlers);
    } catch (error) {
      if (handlers.signal?.aborted || isAbortError(error)) throw new DOMException("Aborted", "AbortError");
      throw new ApiError(0, translate("error.network"));
    } finally {
      handlers.signal?.removeEventListener("abort", onAbort);
      if (finished) {
        reader.cancel().catch((error: unknown) => console.warn("[chat] Fermeture du flux impossible.", error));
      }
    }
    return state.text;
  },

  getHistory: (sessionId: string, signal?: AbortSignal) =>
    request<ChatHistoryItem[]>(`/chat/history/${encodeURIComponent(sessionId)}`, signal ? { signal } : {}),

  listSessions: (subject?: string, signal?: AbortSignal) =>
    request<SessionSummary[]>("/chat/sessions", { query: { subject }, ...(signal ? { signal } : {}) }),

  getSessionInfo: (sessionId: string, signal?: AbortSignal) =>
    request<SessionStarted>(`/chat/session/${encodeURIComponent(sessionId)}/info`, signal ? { signal } : {}),

  endSession: (sessionId: string, satisfaction?: number) =>
    requestVoid(`/chat/session/${encodeURIComponent(sessionId)}`, {
      method: "DELETE",
      query: { satisfaction: satisfaction && satisfaction > 0 ? satisfaction : undefined },
    }),
};
