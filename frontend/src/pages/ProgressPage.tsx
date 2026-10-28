import { useState } from "react";
import { useT } from "../i18n";
import { useCalibration, useDetailedStats, useMasteryEvolution, useProgress } from "../hooks/useProgress";
import { Alert, Button, Card, EmptyState, PageHeader, ProgressBar, Skeleton, SelectField } from "../components/ui";
import LearningChart from "../components/LearningChart";
import { getSubject, topicLabel } from "../theme";
import { formatDate, percent } from "../utils/format";
import { exportProgressPdf } from "../utils/pdf";
import { errorMessage, type BadgeRarity } from "../services";
import type { Page } from "../lib/router";

const TREND_ICON = { up: "↗", down: "↘", stable: "→" } as const;

function MasteryCard() {
  const { t, locale, lang } = useT();
  const m = useMasteryEvolution();
  if (m.isLoadingConcepts || m.concepts.length === 0) return null; // rien à tracer : pas de carte vide
  const value = m.selected ? `${m.selected.subject}|||${m.selected.concept}` : "";
  const data = m.history.map((h) => ({ label: formatDate(h.recorded_at, locale, { day: "2-digit", month: "2-digit" }), value: h.score, weight: 1 }));
  const color = m.selected ? getSubject(m.selected.subject).color : "var(--accent)";
  return (
    <Card title={`🧠 ${t("progress.mastery")}`}>
      <SelectField
        label={t("progress.concept")}
        value={value}
        onChange={(v) => { const [subject = "", concept = ""] = v.split("|||"); m.setSelected({ subject, concept }); }}
        options={m.concepts.map((c) => ({ value: `${c.subject}|||${c.concept}`, label: `${t(getSubject(c.subject).labelKey)} — ${topicLabel(c.concept, lang)} (${t("progress.points", { n: c.points_count })})` }))}
      />
      {m.historyError && <Alert>{m.historyError}</Alert>}
      {m.isLoadingHistory ? <Skeleton lines={2} /> : (
        <LearningChart data={data} color={color} lastLabel={data.at(-1)?.label ?? ""} ariaLabel={t("progress.masteryChartAlt")} emptyLabel={t("progress.notEnoughData")} />
      )}
      <p className="muted">{t("progress.masteryNote")}</p>
    </Card>
  );
}

/** Calibration : l'élève sait-il ce qu'il sait ? (affichée seulement avec assez de réponses). */
function CalibrationCard() {
  const { t } = useT();
  const cal = useCalibration();
  if (cal.loading || cal.error || !cal.data || cal.data.label === null) return null;
  const { label, overconfident_rate: over, underconfident_rate: under, answered } = cal.data;
  return (
    <Card title={`🎯 ${t("progress.calibration")}`}>
      <p>{t(`progress.calibration.${label}`)}</p>
      <p className="muted">{t("progress.calibration.rates", { over: Math.round(over * 100), under: Math.round(under * 100), n: answered })}</p>
    </Card>
  );
}

export default function ProgressPage({ onNavigate }: { onNavigate: (page: Page) => void }) {
  const { t } = useT();
  const dash = useProgress();
  const detailed = useDetailedStats();
  const [exportError, setExportError] = useState<string | null>(null);

  if (dash.loading) return <div className="page"><PageHeader title={t("progress.title")} /><Skeleton lines={6} /></div>;
  if (dash.error || !dash.data) {
    return <div className="page"><EmptyState icon="⚠️" title={t("progress.loadError")}><Alert onRetry={dash.reload}>{dash.error ?? t("error.generic")}</Alert></EmptyState></div>;
  }
  const d = dash.data;
  const rarityLabel = (r: BadgeRarity) => t(`rarity.${r}`);
  const activeDays = d.heatmap.filter((h) => h.level > 0).length;

  const exportPdf = async () => {
    setExportError(null);
    try {
      await exportProgressPdf({
        totalSessions: d.total_sessions, totalQuestions: d.total_questions, streakDays: d.streak_days,
        subjectScores: d.subject_scores.map((s) => ({ subject: t(getSubject(s.subject).labelKey), score: s.score })),
        badges: d.badges.filter((b) => b.earned_at).map((b) => ({ name: b.name, icon: b.icon, description: b.description })),
        recommendations: d.recommendations.map((r) => ({ subject: t(getSubject(r.subject).labelKey), reason: r.reason, action: r.action })),
      });
    } catch (e) {
      setExportError(errorMessage(e));
    }
  };

  const det = detailed.data;
  return (
    <div className="page">
      <PageHeader
        title={t("progress.title")}
        subtitle={t("progress.subtitle")}
        actions={<><Button variant="secondary" onClick={() => void exportPdf()}>📄 {t("common.exportPdf")}</Button><Button variant="ghost" onClick={dash.reload}>↻ {t("common.refresh")}</Button></>}
      />
      {exportError && <Alert>{exportError}</Alert>}

      <div className="tiles">
        <div className="tile"><span aria-hidden="true">📚</span><strong>{d.total_sessions}</strong><span>{t("progress.sessions")}</span></div>
        <div className="tile"><span aria-hidden="true">💬</span><strong>{d.total_questions}</strong><span>{t("progress.questions")}</span></div>
        <div className="tile"><span aria-hidden="true">🔥</span><strong>{d.streak_days}</strong><span>{t("progress.streak")}</span></div>
      </div>

      {det && (
        <Card title={`🔎 ${t("progress.detailed")}`}>
          <div className="tiles tiles--4">
            <div className="tile tile--sm"><strong>{det.avg_session_min} min</strong><span>{t("progress.avgSession")}</span></div>
            <div className="tile tile--sm"><strong>{det.total_time_min} min</strong><span>{t("progress.totalTime")}</span></div>
            <div className="tile tile--sm"><strong>{det.best_subject ? `${getSubject(det.best_subject).icon} ${t(getSubject(det.best_subject).labelKey)}` : "—"}</strong><span>{t("progress.best")}</span></div>
            <div className="tile tile--sm"><strong>{det.weakest_subject ? `${getSubject(det.weakest_subject).icon} ${t(getSubject(det.weakest_subject).labelKey)}` : "—"}</strong><span>{t("progress.weakest")}</span></div>
          </div>
          <h3 className="sub">{t("progress.weekly")}</h3>
          <LearningChart
            data={det.weekly_progress.map((w) => ({ label: w.week_label, value: w.avg_score, weight: w.questions }))}
            lastLabel={t("progress.thisWeek")} ariaLabel={t("progress.weeklyChartAlt")} emptyLabel={t("progress.notEnoughData")}
          />
        </Card>
      )}

      <MasteryCard />
      <CalibrationCard />

      <div className="grid-2">
        <Card title={`📈 ${t("progress.bySubject")}`}>
          {d.subject_scores.length === 0 && <p className="muted">{t("progress.noScores")}</p>}
          <ul className="stack">
            {d.subject_scores.map((s) => {
              const info = getSubject(s.subject);
              return (
                <li key={s.subject}>
                  <div className="rubric__row"><span>{info.icon} {t(info.labelKey)}</span><strong>{percent(s.score)} <span aria-label={t(`trend.${s.trend}`)}>{TREND_ICON[s.trend]}</span></strong></div>
                  <ProgressBar value={s.score} label={t(info.labelKey)} color={info.color} />
                </li>
              );
            })}
          </ul>
        </Card>

        <Card title={`🏅 ${t("progress.badges")}`}>
          <ul className="badges badges--grid">
            {d.badges.map((b) => (
              <li key={b.code} className={`badge badge--tile${b.earned_at ? " is-earned" : ""}`}>
                <span className="badge__icon" aria-hidden="true">{b.icon}</span>
                <strong>{b.name}</strong>
                <span className="muted">{b.earned_at ? `${rarityLabel(b.rarity)}` : t("progress.locked")}</span>
                <span className="sr-only">{b.description}</span>
              </li>
            ))}
          </ul>
        </Card>

        <Card title={`📅 ${t("progress.activity")}`}>
          <div className="heatmap" role="img" aria-label={t("progress.activityAlt", { n: activeDays })}>
            {d.heatmap.map((h) => <span key={h.date} className={`heatmap__cell heat-${Math.min(3, Math.max(0, h.level))}`} title={`${h.date} — ${h.level}`} />)}
          </div>
          <p className="muted heatmap__legend">{t("progress.less")} <span className="heatmap__cell heat-0" /><span className="heatmap__cell heat-1" /><span className="heatmap__cell heat-2" /><span className="heatmap__cell heat-3" /> {t("progress.more")}</p>
        </Card>

        <Card title={`🎯 ${t("progress.recommendations")}`}>
          {d.recommendations.length === 0 && <p className="muted">{t("progress.noRecommendations")}</p>}
          <ul className="stack">
            {d.recommendations.map((r, i) => (
              <li key={i}>
                <button type="button" className="rec rec--btn" onClick={() => onNavigate("exercise")}>
                  <span className={`prio prio--${r.priority}`} aria-label={t(`priority.${r.priority === "high" ? "high" : r.priority === "medium" ? "medium" : "low"}`)} />
                  <span><strong>{r.action}</strong><br /><span className="muted">{r.reason}</span></span>
                  <span aria-hidden="true">→</span>
                </button>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  );
}
