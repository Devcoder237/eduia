import { useCallback, useEffect, useRef, useState } from "react";
import { chatApi, errorMessage, isAbortError, type ChatHistoryItem } from "../services";
import { translate } from "../i18n";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface ImportedDocument {
  filename: string;
  text: string;
  truncated: boolean;
}

function fromHistory(items: ChatHistoryItem[]): ChatMessage[] {
  return items.map((m) => ({
    id: m.id,
    role: m.role === "user" ? "user" : "assistant",
    content: m.content,
    created_at: m.created_at,
  }));
}

let localCounter = 0;
function localId(): string {
  localCounter += 1;
  return `local-${Date.now()}-${localCounter}`;
}

/**
 * Conversation avec le tuteur : reprise de session, streaming SSE annulable,
 * import de document (gardé en mémoire uniquement) et erreurs lisibles.
 */
export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isSessionLoading, setIsSessionLoading] = useState(false);
  const [streamingText, setStreamingText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [importedDoc, setImportedDoc] = useState<ImportedDocument | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const sessionRef = useRef<{ subject: string; level: string; mode: string } | null>(null);
  const streamAbort = useRef<AbortController | null>(null);
  const loadToken = useRef(0);
  const lastUserText = useRef("");

  // Quitter l'écran interrompt le flux en cours (le serveur enregistre ce qui a été produit).
  useEffect(() => () => streamAbort.current?.abort(), []);

  const startSession = useCallback(async (subject: string, level: string, mode: string) => {
    const token = ++loadToken.current;
    streamAbort.current?.abort();
    setIsSessionLoading(true);
    setError(null);
    try {
      const key = { subject, level, mode };
      const latest = await chatApi.getLatestSession(key);
      let id = latest.session_id;
      let history: ChatMessage[] = [];
      if (id) {
        history = fromHistory(await chatApi.getHistory(id));
      } else {
        id = (await chatApi.startSession(key)).session_id;
      }
      if (token !== loadToken.current) return; // une sélection plus récente a pris le relais
      sessionRef.current = key;
      setSessionId(id);
      setMessages(history);
    } catch (e) {
      if (token === loadToken.current && !isAbortError(e)) setError(errorMessage(e));
    } finally {
      if (token === loadToken.current) setIsSessionLoading(false);
    }
  }, []);

  /** Ouvre une conversation précise (depuis l'historique) et renvoie ses paramètres. */
  const loadSession = useCallback(async (id: string) => {
    const token = ++loadToken.current;
    streamAbort.current?.abort();
    setIsSessionLoading(true);
    setError(null);
    try {
      const info = await chatApi.getSessionInfo(id);
      const history = fromHistory(await chatApi.getHistory(id));
      if (token !== loadToken.current) return null;
      sessionRef.current = { subject: info.subject, level: info.level, mode: info.mode };
      setSessionId(info.session_id);
      setMessages(history);
      return info;
    } catch (e) {
      if (token === loadToken.current && !isAbortError(e)) setError(errorMessage(e));
      return null;
    } finally {
      if (token === loadToken.current) setIsSessionLoading(false);
    }
  }, []);

  const sendMessage = useCallback(
    async (text: string) => {
      const context = sessionRef.current;
      if (!sessionId || !context || isStreaming) return;
      lastUserText.current = text;
      setError(null);
      setMessages((prev) => [...prev, { id: localId(), role: "user", content: text, created_at: new Date().toISOString() }]);
      setIsStreaming(true);
      setStreamingText("");
      const controller = new AbortController();
      streamAbort.current = controller;
      let partial = "";
      try {
        const full = await chatApi.streamMessage(
          { session_id: sessionId, message: text, ...context, document_context: importedDoc?.text ?? null },
          {
            signal: controller.signal,
            onChunk: (soFar) => {
              partial = soFar;
              setStreamingText(soFar);
            },
            onError: (message) => setError(message),
          },
        );
        partial = full;
      } catch (e) {
        if (!isAbortError(e)) setError(errorMessage(e));
      } finally {
        if (partial !== "") {
          setMessages((prev) => [...prev, { id: localId(), role: "assistant", content: partial, created_at: new Date().toISOString() }]);
        }
        setIsStreaming(false);
        setStreamingText("");
        streamAbort.current = null;
      }
    },
    [sessionId, importedDoc, isStreaming],
  );

  /** Interrompt la réponse en cours (bouton « Arrêter »). */
  const stop = useCallback(() => streamAbort.current?.abort(), []);

  const importDocument = useCallback(async (file: File) => {
    setIsUploading(true);
    setUploadError(null);
    try {
      const res = await chatApi.uploadDocument(file);
      setImportedDoc({ filename: res.filename, text: res.text, truncated: res.truncated });
    } catch (e) {
      setUploadError(errorMessage(e, translate("tutor.uploadFailed")));
    } finally {
      setIsUploading(false);
    }
  }, []);

  const removeImportedDocument = useCallback(() => setImportedDoc(null), []);

  return {
    messages, sessionId, isStreaming, isSessionLoading, streamingText, error,
    importedDoc, isUploading, uploadError,
    startSession, loadSession, sendMessage, stop, importDocument, removeImportedDocument,
    dismissError: () => setError(null),
    lastUserText: () => lastUserText.current,
  };
}
