import { ReportButton } from "../components/ReportButton";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent, FormEvent, KeyboardEvent } from "react";
import { useT } from "../i18n";
import { useAuth } from "../context/AuthContext";
import { useChat, type ChatMessage } from "../hooks/useChat";
import { useTutorPrefs } from "../hooks/usePrefs";
import { isSpeechSynthesisSupported, speakText, speechLangFor, stopSpeaking, useSpeechRecognition } from "../hooks/useVoice";
import FormattedText from "../components/FormattedText";
import { Alert, ChoiceGroup, Drawer, Button } from "../components/ui";
import { LEVELS, MODES, SUBJECTS, getLevel, getMode, getQuickQuestions, getSubject } from "../theme";
import { formatTime } from "../utils/format";
import type { Page } from "../lib/router";

const MAX_MESSAGE_CHARS = 2000;

interface TutorPageProps {
  onNavigate: (page: Page, params?: Record<string, string>) => void;
  /** Conversation à ouvrir (depuis l'historique). */
  openSessionId?: string | undefined;
  /** Appelé une fois la conversation chargée (l'appelant nettoie l'adresse). */
  onSessionOpened?: (() => void) | undefined;
}

interface SettingsPanelProps {
  subject: string;
  level: string;
  mode: string;
  onSubject: (id: string) => void;
  onLevel: (id: string) => void;
  onMode: (id: string) => void;
  onNavigate: (page: Page) => void;
}

/** Choix matière / niveau / mode : panneau latéral (>= 1024 px) ou tiroir (mobile). */
function SettingsPanel({ subject, level, mode, onSubject, onLevel, onMode, onNavigate }: SettingsPanelProps) {
  const { t } = useT();
  return (
    <div className="tutor-settings">
      <ChoiceGroup
        legend={t("common.subject")}
        value={subject}
        onChange={onSubject}
        options={SUBJECTS.map((s) => ({ value: s.id, label: <><span aria-hidden="true">{s.icon}</span> {t(s.labelKey)}</>, color: s.color }))}
      />
      <ChoiceGroup
        legend={t("common.level")}
        value={level}
        onChange={onLevel}
        options={LEVELS.map((l) => ({ value: l.id, label: <><span aria-hidden="true">{l.icon}</span> {t(l.labelKey)}</>, sub: t(l.subKey), color: l.color }))}
      />
      <ChoiceGroup
        legend={t("common.mode")}
        value={mode}
        onChange={onMode}
        options={MODES.map((m) => ({ value: m.id, label: <><span aria-hidden="true">{m.icon}</span> {t(m.labelKey)}</>, sub: t(m.descKey), color: m.color }))}
      />
      <div className="tutor-settings__links">
        <p className="ui-choice__legend">{t("tutor.shortcuts")}</p>
        {(["exercise", "quiz", "exam", "studyplans", "history", "progress"] as const).map((p) => (
          <button key={p} type="button" className="ui-btn ui-btn--secondary ui-btn--sm ui-btn--full" onClick={() => onNavigate(p)}>
            {t(`nav.${p}`)}
          </button>
        ))}
      </div>
    </div>
  );
}

function Bubble({ message, speakingId, onSpeak, simple, locale }: {
  message: ChatMessage;
  speakingId: string | null;
  onSpeak: (id: string, text: string) => void;
  simple: boolean;
  locale: string;
}) {
  const { t } = useT();
  const isUser = message.role === "user";
  const speaking = speakingId === message.id;
  return (
    <article className={`bubble ${isUser ? "bubble--user" : "bubble--bot"}${simple ? " bubble--simple" : ""}`} aria-label={isUser ? t("tutor.you") : t("tutor.tutor")}>
      <div className="bubble__avatar" aria-hidden="true">{isUser ? "👤" : "🎓"}</div>
      <div className="bubble__body">
        {isUser ? <p className="ft-p">{message.content}</p> : <FormattedText content={message.content} />}
        <div className="bubble__meta">
          {!isUser && isSpeechSynthesisSupported() ? (
            <button type="button" className="bubble__speak" onClick={() => onSpeak(message.id, message.content)} aria-pressed={speaking} aria-label={speaking ? t("tutor.stopReading") : t("tutor.readAloud")}>
              <span aria-hidden="true">{speaking ? "⏹️" : "🔊"}</span>
            </button>
          ) : <span />}
          {!isUser && message.content.trim() !== "" && <ReportButton excerpt={message.content.slice(0, 600)} />}
          <time dateTime={message.created_at}>{formatTime(message.created_at, locale)}</time>
        </div>
      </div>
    </article>
  );
}

export default function TutorPage({ onNavigate, openSessionId, onSessionOpened }: TutorPageProps) {
  const { t, lang, locale } = useT();
  const { firstName } = useAuth();
  const { subject, level, mode, setSubject, setLevel, setMode } = useTutorPrefs();
  const chat = useChat();
  const { startSession, loadSession } = chat;
  const [draft, setDraft] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [speakingId, setSpeakingId] = useState<string | null>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const nearBottom = useRef(true);
  const loadedKey = useRef<string | null>(null);

  const subjectInfo = getSubject(subject);
  const levelInfo = getLevel(level);
  const modeInfo = getMode(mode);
  const simple = levelInfo.simplified;
  const busy = chat.isStreaming || chat.isSessionLoading;

  const mic = useSpeechRecognition((text) => setDraft((prev) => (prev ? `${prev} ` : "") + text));

  // Ouverture d'une conversation précise (depuis l'historique) : on aligne ensuite les préférences
  // sur ses paramètres sans relancer la recherche de « dernière session ».
  useEffect(() => {
    if (!openSessionId) return;
    void loadSession(openSessionId).then((info) => {
      if (!info) return;
      loadedKey.current = `${info.subject}|${info.level}|${info.mode}`;
      setSubject(info.subject);
      setLevel(info.level);
      setMode(info.mode);
      onSessionOpened?.();
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openSessionId, loadSession, setSubject, setLevel, setMode]);

  useEffect(() => {
    if (openSessionId) return; // la conversation demandée est en cours de chargement
    const key = `${subject}|${level}|${mode}`;
    if (loadedKey.current === key) {
      loadedKey.current = null; // préférences alignées sur la conversation déjà ouverte
      return;
    }
    loadedKey.current = null;
    void startSession(subject, level, mode);
  }, [subject, level, mode, startSession, openSessionId]);

  // Défilement automatique, sauf si l'élève a remonté dans la conversation.
  useEffect(() => {
    const el = logRef.current;
    if (el && nearBottom.current) el.scrollTop = el.scrollHeight;
  }, [chat.messages, chat.streamingText]);

  const onScroll = useCallback(() => {
    const el = logRef.current;
    if (el) nearBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  }, []);

  useEffect(() => () => stopSpeaking(), []);

  const send = async () => {
    const text = draft.trim();
    if (!text || busy) return;
    setDraft("");
    nearBottom.current = true;
    await chat.sendMessage(text);
  };

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void send();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void send();
    }
  };

  const onFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) await chat.importDocument(file);
    event.target.value = "";
  };

  const speak = (id: string, text: string) => {
    if (speakingId === id) {
      stopSpeaking();
      setSpeakingId(null);
      return;
    }
    setSpeakingId(id);
    speakText(text, () => setSpeakingId(null), speechLangFor(subject, lang));
  };

  const quick = useMemo(() => getQuickQuestions(subject, level, lang), [subject, level, lang]);
  const greeting = firstName ? t("tutor.hello", { name: firstName }) : t("tutor.helloAnon");
  const showEmpty = !chat.isSessionLoading && chat.messages.length === 0 && !chat.streamingText;

  return (
    <div className="tutor">
      <aside className="tutor__side" aria-label={t("tutor.settings")}>
        <SettingsPanel subject={subject} level={level} mode={mode} onSubject={setSubject} onLevel={setLevel} onMode={setMode} onNavigate={onNavigate} />
      </aside>

      <Drawer open={settingsOpen} onClose={() => setSettingsOpen(false)} title={t("tutor.settings")} side="left">
        <SettingsPanel
          subject={subject} level={level} mode={mode}
          onSubject={(id) => { setSubject(id); }} onLevel={setLevel} onMode={setMode}
          onNavigate={(p) => { setSettingsOpen(false); onNavigate(p); }}
        />
        <Button fullWidth onClick={() => setSettingsOpen(false)}>{t("common.done")}</Button>
      </Drawer>

      <section className="tutor__chat" aria-label={t("tutor.conversation")}>
        <div className="tutor__head" style={{ borderBottomColor: subjectInfo.color }}>
          <span className="tutor__badge" style={{ background: subjectInfo.color }} aria-hidden="true">{subjectInfo.icon}</span>
          <div className="tutor__headtext">
            <h1 className="tutor__title">{t(subjectInfo.labelKey)}</h1>
            <p className="tutor__subtitle">{levelInfo.icon} {t(levelInfo.labelKey)} · {modeInfo.icon} {t(modeInfo.labelKey)}</p>
          </div>
          <button type="button" className="ui-btn ui-btn--secondary ui-btn--sm tutor__settingsbtn" onClick={() => setSettingsOpen(true)} aria-haspopup="dialog">
            ⚙️ {t("tutor.settingsShort")}
          </button>
        </div>

        <div ref={logRef} className="tutor__messages" role="log" aria-live="polite" aria-relevant="additions" aria-busy={busy} onScroll={onScroll}>
          {chat.isSessionLoading && <p className="tutor__status" role="status">{t("tutor.loadingConversation")}</p>}

          {showEmpty && (
            <div className="tutor__empty">
              <span className="tutor__badge tutor__badge--lg" style={{ background: subjectInfo.color }} aria-hidden="true">{subjectInfo.icon}</span>
              <h2 className="tutor__hello">{greeting} {t("tutor.intro", { subject: t(subjectInfo.labelKey) })}</h2>
              <ul className="tutor__quick" aria-label={t("tutor.suggestions")}>
                {quick.map((q) => (
                  <li key={q}>
                    <button type="button" className="chip-btn" onClick={() => { setDraft(q); inputRef.current?.focus(); }}>{q}</button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {chat.messages.map((m) => (
            <Bubble key={m.id} message={m} speakingId={speakingId} onSpeak={speak} simple={simple} locale={locale} />
          ))}

          {chat.streamingText && (
            <article className={`bubble bubble--bot bubble--live${simple ? " bubble--simple" : ""}`} aria-label={t("tutor.tutor")}>
              <div className="bubble__avatar" aria-hidden="true">🎓</div>
              <div className="bubble__body"><FormattedText content={chat.streamingText} /><span className="caret" aria-hidden="true" /></div>
            </article>
          )}

          {chat.isStreaming && !chat.streamingText && (
            <div className="bubble bubble--bot" role="status">
              <div className="bubble__avatar" aria-hidden="true">🎓</div>
              <div className="bubble__body typing"><span className="sr-only">{t("tutor.thinking")}</span><i /><i /><i /></div>
            </div>
          )}
        </div>

        <div className="tutor__footer">
          {chat.error && <Alert tone="error" onRetry={chat.lastUserText() ? () => { void chat.sendMessage(chat.lastUserText()); } : undefined}>{chat.error}</Alert>}
          {chat.importedDoc && (
            <div className="doc-chip">
              <span aria-hidden="true">📄</span>
              <strong>{chat.importedDoc.filename}</strong>
              {chat.importedDoc.truncated && <span className="doc-chip__note">{t("tutor.docTruncated")}</span>}
              <button type="button" className="ui-iconbtn ui-iconbtn--sm" onClick={chat.removeImportedDocument} aria-label={t("tutor.removeDoc")}>✕</button>
            </div>
          )}
          {chat.uploadError && <Alert tone="error">{chat.uploadError}</Alert>}
          {mic.error && <Alert tone="warning">{mic.error}</Alert>}

          <form className="composer" onSubmit={onSubmit}>
            <input ref={fileRef} type="file" accept=".pdf,.docx,.pptx" className="sr-only" tabIndex={-1} onChange={(e) => void onFile(e)} aria-label={t("tutor.attach")} />
            <button type="button" className="ui-iconbtn" onClick={() => fileRef.current?.click()} disabled={chat.isUploading} aria-label={t("tutor.attach")} title={t("tutor.attach")}>
              <span aria-hidden="true">{chat.isUploading ? "⏳" : "📎"}</span>
            </button>
            {mic.isSupported && (
              <button type="button" className={`ui-iconbtn${mic.isListening ? " is-recording" : ""}`} onClick={mic.isListening ? mic.stop : mic.start} aria-pressed={mic.isListening} aria-label={mic.isListening ? t("tutor.micStop") : t("tutor.micStart")} title={mic.isListening ? t("tutor.micStop") : t("tutor.micStart")}>
                <span aria-hidden="true">🎤</span>
              </button>
            )}
            <label className="sr-only" htmlFor="tutor-input">{t("tutor.inputLabel")}</label>
            <textarea
              id="tutor-input"
              ref={inputRef}
              className="composer__input"
              rows={1}
              value={draft}
              maxLength={MAX_MESSAGE_CHARS}
              placeholder={mic.isListening ? t("tutor.listening") : t("tutor.placeholder", { subject: t(subjectInfo.labelKey) })}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={onKeyDown}
              disabled={chat.isSessionLoading}
            />
            {chat.isStreaming ? (
              <button type="button" className="composer__send composer__send--stop" onClick={chat.stop} aria-label={t("tutor.stop")}>■</button>
            ) : (
              <button type="submit" className="composer__send" disabled={!draft.trim() || busy} aria-label={t("common.send")} style={{ background: draft.trim() && !busy ? subjectInfo.color : undefined }}>➤</button>
            )}
          </form>
          <p className="tutor__hint">{t("tutor.disclaimer")} {t("tutor.hint")}{chat.importedDoc ? ` · 📄 ${t("tutor.docActive")}` : ""}</p>
        </div>
      </section>
    </div>
  );
}
