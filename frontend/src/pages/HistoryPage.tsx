import { useState } from "react";
import { useT } from "../i18n";
import { useSessionHistory } from "../hooks/useSessionHistory";
import { Alert, EmptyState, PageHeader, Skeleton } from "../components/ui";
import { SUBJECTS, getLevel, getMode, getSubject } from "../theme";
import { formatDate } from "../utils/format";

export default function HistoryPage({ onOpenSession }: { onOpenSession: (sessionId: string) => void }) {
  const { t, locale } = useT();
  const [filter, setFilter] = useState<string | undefined>(undefined);
  const history = useSessionHistory(filter);
  const sessions = history.data ?? [];

  return (
    <div className="page page--narrow">
      <PageHeader title={t("history.title")} subtitle={t("history.subtitle")} />

      <div className="chips-group" role="group" aria-label={t("history.filter")}>
        <button type="button" className={`chip-btn${filter === undefined ? " is-on" : ""}`} aria-pressed={filter === undefined} onClick={() => setFilter(undefined)}>{t("history.all")}</button>
        {SUBJECTS.map((s) => (
          <button key={s.id} type="button" className={`chip-btn${filter === s.id ? " is-on" : ""}`} aria-pressed={filter === s.id} onClick={() => setFilter(s.id)}>
            <span aria-hidden="true">{s.icon}</span> {t(s.labelKey)}
          </button>
        ))}
      </div>

      {history.loading && <Skeleton lines={5} />}
      {history.error && <Alert onRetry={history.reload}>{history.error}</Alert>}
      {!history.loading && !history.error && sessions.length === 0 && (
        <EmptyState icon="💬" title={t("history.emptyTitle")}>{filter ? t("history.emptyFiltered", { subject: t(getSubject(filter).labelKey) }) : t("history.empty")}</EmptyState>
      )}

      <ul className="stack">
        {sessions.map((s) => {
          const subject = getSubject(s.subject);
          const level = getLevel(s.level);
          const mode = getMode(s.mode);
          return (
            <li key={s.session_id}>
              <button type="button" className="history-item" onClick={() => onOpenSession(s.session_id)}>
                <span className="tutor__badge" style={{ background: subject.color }} aria-hidden="true">{subject.icon}</span>
                <span className="history-item__main">
                  <strong>{t(subject.labelKey)}</strong>
                  <span className="muted"> · {level.icon} {t(level.labelKey)} · {mode.icon} {t(mode.labelKey)}</span>
                  <span className="history-item__preview">{s.preview}</span>
                </span>
                <span className="history-item__meta">
                  <span>{formatDate(s.started_at, locale, { day: "2-digit", month: "short" })}</span>
                  <span className="muted">{t("history.messages", { n: s.msg_count })}</span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
