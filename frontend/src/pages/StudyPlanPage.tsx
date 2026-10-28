import { useState } from "react";
import { useT } from "../i18n";
import { useStudyPlans } from "../hooks/useStudyPlans";
import { useTutorPrefs } from "../hooks/usePrefs";
import { Alert, Button, Card, EmptyState, PageHeader, ProgressBar, Skeleton, TextField } from "../components/ui";
import { SUBJECTS, getSubject } from "../theme";
import { daysUntil, formatDateOnly, localIsoDate } from "../utils/format";

export default function StudyPlanPage() {
  const { t, locale } = useT();
  const { level } = useTutorPrefs();
  const plans = useStudyPlans();
  const [showForm, setShowForm] = useState(false);
  const [label, setLabel] = useState("BEPC");
  const [date, setDate] = useState(() => localIsoDate(14));
  const [subjects, setSubjects] = useState<string[]>(["mathematiques"]);
  const [openId, setOpenId] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const toggleSubject = (id: string) => setSubjects((prev) => (prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]));

  const submit = async () => {
    setFormError(null);
    if (subjects.length === 0) { setFormError(t("plan.pickSubject")); return; }
    if (date < localIsoDate(0)) { setFormError(t("plan.datePast")); return; }
    // Midi UTC : la date choisie reste la même dans tous les fuseaux horaires.
    const plan = await plans.generate({ exam_label: label.trim() || t("pdf.examFallback"), target_date: `${date}T12:00:00Z`, subjects, level });
    if (plan) { setShowForm(false); setOpenId(plan.id); }
  };

  return (
    <div className="page page--narrow">
      <PageHeader
        title={t("plan.title")}
        subtitle={t("plan.subtitle")}
        actions={<Button variant={showForm ? "secondary" : "primary"} onClick={() => setShowForm((s) => !s)} pressed={showForm}>{showForm ? `✕ ${t("common.cancel")}` : `+ ${t("plan.new")}`}</Button>}
      />

      {showForm && (
        <Card title={`🗓️ ${t("plan.configure")}`}>
          <div className="picker">
            <TextField label={t("plan.goal")} value={label} onChange={setLabel} maxLength={200} placeholder={t("plan.goalPlaceholder")} />
            <TextField label={t("plan.targetDate")} type="date" value={date} onChange={setDate} />
          </div>
          <fieldset className="chips-group">
            <legend className="ui-choice__legend">{t("plan.subjects")}</legend>
            {SUBJECTS.map((s) => (
              <button key={s.id} type="button" className={`chip-btn${subjects.includes(s.id) ? " is-on" : ""}`} aria-pressed={subjects.includes(s.id)} onClick={() => toggleSubject(s.id)}>
                <span aria-hidden="true">{s.icon}</span> {t(s.labelKey)}
              </button>
            ))}
          </fieldset>
          {formError && <Alert>{formError}</Alert>}
          {plans.actionError && <Alert>{plans.actionError}</Alert>}
          <Button size="lg" fullWidth loading={plans.isGenerating} onClick={() => void submit()}>
            {plans.isGenerating ? t("plan.generating") : `✨ ${t("plan.generate")}`}
          </Button>
        </Card>
      )}

      {!showForm && plans.actionError && <Alert>{plans.actionError}</Alert>}
      {plans.isLoading && <Skeleton lines={4} />}
      {plans.loadError && <Alert onRetry={plans.reload}>{plans.loadError}</Alert>}
      {!plans.isLoading && !plans.loadError && plans.plans.length === 0 && !showForm && (
        <EmptyState icon="🗓️" title={t("plan.emptyTitle")}>{t("plan.empty")}</EmptyState>
      )}

      <ul className="stack">
        {plans.plans.map((plan) => {
          const open = openId === plan.id;
          const remaining = daysUntil(plan.target_date);
          const done = plan.days.filter((d) => d.completed).length;
          const ratio = plan.days.length > 0 ? done / plan.days.length : 0;
          const panelId = `plan-${plan.id}`;
          return (
            <li key={plan.id}>
              <Card>
                <button type="button" className="plan-head" aria-expanded={open} aria-controls={panelId} onClick={() => setOpenId(open ? null : plan.id)}>
                  <span>
                    <strong>{plan.exam_label}</strong><br />
                    <span className="muted">
                      {remaining > 0 ? t("plan.daysLeft", { n: remaining }) : remaining === 0 ? t("plan.today") : t("plan.past")} · {plan.subjects.map((s) => getSubject(s).icon).join(" ")}
                    </span>
                  </span>
                  <span className="plan-head__pct">{Math.round(ratio * 100)} % <span aria-hidden="true">{open ? "▲" : "▼"}</span><br /><span className="muted">{t("plan.daysDone", { done, total: plan.days.length })}</span></span>
                </button>
                <ProgressBar value={ratio} label={t("plan.progress")} />
                {plan.notice && <Alert tone="info">{plan.notice}</Alert>}

                {open && (
                  <div id={panelId}>
                    <ul className="stack">
                      {plan.days.map((day, i) => (
                        <li key={`${day.date}-${i}`} className={`day${day.completed ? " day--done" : ""}`}>
                          <label className="day__check">
                            <input type="checkbox" checked={day.completed} onChange={() => void plans.toggleDay(plan.id, i, !day.completed)} />
                            <span className="sr-only">{t("plan.markDone", { day: day.day_label })}</span>
                          </label>
                          <div>
                            <strong>{day.day_label}</strong> <span className="muted">· {formatDateOnly(day.date, locale)}</span>
                            <p className="chips">{day.subjects.map((s) => <span key={s} className="ui-chip">{getSubject(s).icon} {t(getSubject(s).labelKey)}</span>)}</p>
                            <ul>{day.tasks.map((task, ti) => <li key={ti}>{task}</li>)}</ul>
                          </div>
                        </li>
                      ))}
                    </ul>
                    <div className="actions">
                      <Button variant="secondary" loading={plans.isRefreshing} onClick={() => void plans.refresh(plan.id)}>🔄 {t("plan.refresh")}</Button>
                      <Button variant="ghost" onClick={() => void plans.archive(plan.id)}>🗄️ {t("plan.archive")}</Button>
                    </div>
                  </div>
                )}
              </Card>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
