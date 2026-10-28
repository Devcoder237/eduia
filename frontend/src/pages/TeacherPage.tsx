import { useState } from "react";
import { useT } from "../i18n";
import { useClassroomReport, useClassrooms } from "../hooks/useClassrooms";
import { Alert, Button, Card, EmptyState, PageHeader, ProgressBar, SelectField, Skeleton, TextField } from "../components/ui";
import { LEVELS, getLevel, getSubject } from "../theme";

/** Teinte + libellé : la couleur n'est jamais le seul porteur d'information. */
function scoreTone(score: number): "good" | "ok" | "low" {
  return score >= 0.7 ? "good" : score >= 0.4 ? "ok" : "low";
}

function ClassroomList({ onOpen }: { onOpen: (id: string) => void }) {
  const { t } = useT();
  const rooms = useClassrooms();
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [level, setLevel] = useState(LEVELS[1]?.id ?? "college");
  const [created, setCreated] = useState<{ name: string; code: string } | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const create = async () => {
    if (name.trim().length < 2) { setFormError(t("teacher.nameShort")); return; }
    setFormError(null);
    const room = await rooms.create(name.trim(), level);
    if (room) {
      setCreated({ name: room.name, code: room.invite_code });
      setName("");
      setShowForm(false);
    }
  };

  return (
    <>
      {created && (
        <Alert tone="success">
          <strong>{t("teacher.created", { name: created.name })}</strong>
          <p>{t("teacher.shareCode")}</p>
          <p className="invite-code" aria-label={t("teacher.inviteCode")}>{created.code}</p>
          <ShareCode code={created.code} className={created.name} />
        </Alert>
      )}
      <div className="rubric__row">
        <h2 className="sub">{t("teacher.myClasses")}</h2>
        <Button variant={showForm ? "secondary" : "primary"} onClick={() => setShowForm((s) => !s)}>{showForm ? t("common.cancel") : `+ ${t("teacher.newClass")}`}</Button>
      </div>

      {showForm && (
        <Card>
          <div className="picker">
            <TextField label={t("teacher.className")} value={name} onChange={setName} maxLength={150} placeholder={t("teacher.classPlaceholder")} error={formError ?? undefined} />
            <SelectField label={t("common.level")} value={level} onChange={setLevel} options={LEVELS.map((l) => ({ value: l.id, label: `${l.icon} ${t(l.labelKey)}` }))} />
          </div>
          {rooms.createError && <Alert>{rooms.createError}</Alert>}
          <Button loading={rooms.isCreating} onClick={() => void create()}>{t("teacher.create")}</Button>
        </Card>
      )}

      {rooms.isLoading && <Skeleton lines={3} />}
      {rooms.error && <Alert onRetry={rooms.reload}>{rooms.error}</Alert>}
      {!rooms.isLoading && !rooms.error && rooms.classrooms.length === 0 && <EmptyState icon="🏫" title={t("teacher.emptyTitle")}>{t("teacher.empty")}</EmptyState>}

      <ul className="cards-grid">
        {rooms.classrooms.map((c) => {
          const level = getLevel(c.level);
          return (
            <li key={c.id}>
              <button type="button" className="class-card" onClick={() => onOpen(c.id)}>
                <span className="class-card__icon" aria-hidden="true">{level.icon}</span>
                <strong>{c.name}</strong>
                <span className="muted">{t(level.labelKey)}</span>
                <span className="class-card__foot">
                  <span>👥 {t("teacher.students", { n: c.student_count })}</span>
                  <code>{c.invite_code}</code>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </>
  );
}

function ClassroomDetail({ classroomId, onBack }: { classroomId: string; onBack: () => void }) {
  const { t } = useT();
  const report = useClassroomReport(classroomId);
  const [open, setOpen] = useState<string | null>(null);

  if (report.loading) return <Skeleton lines={5} />;
  const data = report.data;
  if (report.error || !data) return <Alert onRetry={report.reload}>{report.error ?? t("error.generic")}</Alert>;

  return (
    <>
      <Button variant="ghost" onClick={onBack}>← {t("common.back")}</Button>
      <h2 className="sub">{data.classroom_name}</h2>
      <p className="muted">{t("teacher.joinedCount", { n: data.student_count })}</p>

      {data.class_averages.length > 0 && (
        <Card title={`📊 ${t("teacher.averages")}`}>
          <ul className="stack">
            {data.class_averages.map((a) => {
              const s = getSubject(a.subject);
              return (
                <li key={a.subject}>
                  <div className="rubric__row"><span>{s.icon} {t(s.labelKey)}</span><strong>{Math.round(a.average_score * 100)} %</strong></div>
                  <ProgressBar value={a.average_score} label={t(s.labelKey)} color={s.color} />
                </li>
              );
            })}
          </ul>
        </Card>
      )}

      <h3 className="sub">👤 {t("teacher.individual")}</h3>
      {data.students.length === 0 && <EmptyState icon="🧑‍🎓" title={t("teacher.noStudents")}>{t("teacher.noStudentsHint")}</EmptyState>}
      <ul className="stack">
        {data.students.map((s) => {
          const isOpen = open === s.user_id;
          const panelId = `student-${s.user_id}`;
          return (
            <li key={s.user_id}>
              <Card>
                <button type="button" className="plan-head" aria-expanded={isOpen} aria-controls={panelId} onClick={() => setOpen(isOpen ? null : s.user_id)}>
                  <span>
                    <strong>{s.full_name || s.username}</strong><br />
                    <span className="muted">{t("teacher.studentLine", { sessions: s.total_sessions, questions: s.total_questions, streak: s.streak_days })}</span>
                  </span>
                  <span aria-hidden="true">{isOpen ? "▲" : "▼"}</span>
                </button>
                {isOpen && (
                  <div id={panelId}>
                    <h4 className="sub">{t("teacher.bySubject")}</h4>
                    {Object.keys(s.subject_scores).length === 0 ? <p className="muted">{t("teacher.noData")}</p> : (
                      <p className="chips">
                        {Object.entries(s.subject_scores).map(([subject, score]) => (
                          <span key={subject} className={`ui-chip tone-${scoreTone(score)}`}>{t(getSubject(subject).labelKey)} · {Math.round(score * 100)} %</span>
                        ))}
                      </p>
                    )}
                    {s.weakest_concepts.length > 0 && (
                      <>
                        <h4 className="sub">🎯 {t("teacher.weakest")}</h4>
                        <ul className="stack">
                          {s.weakest_concepts.map((w, i) => (
                            <li key={i} className="rubric__row"><span>{t(getSubject(w.subject).labelKey)} — {w.concept}</span><strong>{Math.round(w.score * 100)} %</strong></li>
                          ))}
                        </ul>
                      </>
                    )}
                  </div>
                )}
              </Card>
            </li>
          );
        })}
      </ul>
    </>
  );
}

/** Boutons « Copier » et « Partager sur WhatsApp » pour le code d'invitation. */
function ShareCode({ code, className }: { code: string; className: string }) {
  const { t } = useT();
  const [copied, setCopied] = useState(false);
  const message = t("teacher.shareMessage", { name: className, code });
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2500);
    } catch {
      setCopied(false); // presse-papiers indisponible : le code reste affiché, copiable à la main
    }
  };
  return (
    <div className="actions">
      <Button variant="secondary" size="sm" onClick={() => void copy()}>{copied ? `✓ ${t("teacher.copied")}` : t("teacher.copy")}</Button>
      <a className="ui-btn ui-btn--secondary ui-btn--sm" href={`https://wa.me/?text=${encodeURIComponent(message)}`} target="_blank" rel="noopener noreferrer">
        {t("teacher.whatsapp")}
      </a>
    </div>
  );
}

export default function TeacherPage() {
  const { t } = useT();
  const [openId, setOpenId] = useState<string | null>(null);
  return (
    <div className="page">
      <PageHeader title={t("teacher.title")} subtitle={t("teacher.subtitle")} />
      {openId ? <ClassroomDetail classroomId={openId} onBack={() => setOpenId(null)} /> : <ClassroomList onOpen={setOpenId} />}
    </div>
  );
}
