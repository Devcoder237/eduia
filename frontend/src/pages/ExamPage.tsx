import { setLangLocked } from "../lib/langLock";
import { useEffect, useRef, useState } from "react";
import { useT } from "../i18n";
import { useExam, useExamHistory } from "../hooks/useExam";
import { useTutorPrefs } from "../hooks/usePrefs";
import { Alert, Button, Card, PageHeader, ProgressBar, Skeleton, TextField, SelectField } from "../components/ui";
import { ContextPicker } from "../components/ContextPicker";
import FormattedText from "../components/FormattedText";
import { getLevel, getSubject } from "../theme";
import { exportExamResultPdf } from "../utils/pdf";
import { formatClock } from "../utils/format";
import { errorMessage, type ExamResult } from "../services";

const COUNTS = [5, 10, 15, 20] as const;
const DURATIONS = [10, 15, 30, 45, 60, 90] as const;

function remainingSeconds(deadline: number | null): number {
  return deadline === null ? 0 : Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
}

export default function ExamPage() {
  const { t } = useT();
  const { subject, level, setSubject, setLevel } = useTutorPrefs();
  const exam = useExam();
  const history = useExamHistory();
  const [label, setLabel] = useState("BEPC");
  const [count, setCount] = useState<number>(10);
  const [duration, setDuration] = useState<number>(15);
  const [picked, setPicked] = useState<number | null>(null);
  const [left, setLeft] = useState(0);
  const [announce, setAnnounce] = useState("");
  const [exportError, setExportError] = useState<string | null>(null);
  const expiredHandled = useRef(false);
  const levelInfo = getLevel(level);
  const { question, deadline, finish, isFinishing } = exam;
  const running = question !== null;
  // Langue verrouillée pendant l'épreuve : les questions suivantes sont générées dans la langue de départ.
  useEffect(() => {
    setLangLocked(running);
    return () => setLangLocked(false);
  }, [running]);

  // Chronomètre : dérivé de l'échéance (précis même si l'onglet est en arrière-plan).
  useEffect(() => {
    if (!running || deadline === null) return undefined;
    expiredHandled.current = false;
    const tick = () => {
      const remaining = remainingSeconds(deadline);
      setLeft(remaining);
      if (remaining === 300) setAnnounce(t("exam.minutesLeft", { n: 5 }));
      if (remaining === 60) setAnnounce(t("exam.minutesLeft", { n: 1 }));
      if (remaining === 0 && !expiredHandled.current) {
        expiredHandled.current = true;
        setAnnounce(t("exam.timeUp"));
        void finish();
      }
    };
    tick();
    const timer = window.setInterval(tick, 1000);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [running, deadline, finish]);

  useEffect(() => { setPicked(null); }, [question?.attempt_id]);

  const startExam = () => void exam.start({ subject, level, examLabel: label.trim() || "Examen blanc", questionCount: count, durationMin: duration });

  const exportPdf = async (res: ExamResult) => {
    setExportError(null);
    try {
      await exportExamResultPdf({
        exam_label: res.exam_label, subject: t(getSubject(res.subject).labelKey), level: t(getLevel(res.level).labelKey),
        score: res.score, correct_count: res.correct_count, total: res.total, duration_sec: res.duration_sec, details: res.details,
      });
    } catch (e) {
      setExportError(errorMessage(e));
    }
  };

  // ───── Correction affichée ─────
  if (exam.result) {
    const res = exam.result;
    const tone = res.score >= 0.8 ? "good" : res.score >= 0.5 ? "ok" : "low";
    return (
      <div className="page page--narrow">
        <PageHeader title={t("exam.resultTitle")} subtitle={`${res.exam_label} · ${t(getSubject(res.subject).labelKey)} · ${t(getLevel(res.level).labelKey)}`} />
        <Card className={`score-card score-card--${tone}`}>
          <div className="score">
            <span className="score__value">{Math.round(res.score * 100)} %</span>
            <span className="score__label">{t("exam.correctCount", { score: res.correct_count, total: res.total })} · {formatClock(res.duration_sec)}</span>
          </div>
          <ProgressBar value={res.score} label={t("exam.score")} />
        </Card>
        <Card title={t("exam.details")}>
          <ol className="stack">
            {res.details.map((d, i) => (
              <li key={i} className="detail">
                <p className="detail__q"><FormattedText content={d.question} /></p>
                <p className={d.answer_index === null ? "muted" : d.is_correct ? "detail__ok" : "detail__ko"}>
                  {d.answer_index === null
                    ? `⏭️ ${t("exam.notAnswered")}`
                    : d.is_correct
                      ? `✓ ${t("exam.yourAnswerRight")} ${d.options[d.answer_index] ?? ""}`
                      : `✗ ${t("exam.yourAnswer")} ${d.options[d.answer_index] ?? ""} — ${t("exam.rightAnswer")} ${d.options[d.correct_index] ?? ""}`}
                </p>
                {d.explanation && <p className="muted"><FormattedText content={d.explanation} /></p>}
              </li>
            ))}
          </ol>
        </Card>
        {exportError && <Alert>{exportError}</Alert>}
        <div className="actions">
          <Button variant="secondary" onClick={() => void exportPdf(res)}>📄 {t("common.exportPdf")}</Button>
          <Button onClick={() => { exam.reset(); history.reload(); }}>{t("exam.newExam")}</Button>
        </div>
      </div>
    );
  }

  // ───── Correction en cours ─────
  if (isFinishing) {
    return (
      <div className="page page--narrow">
        <Card><div className="loading-block" role="status"><span className="ui-spinner" aria-hidden="true" /><p>{t("exam.correcting")}</p></div></Card>
      </div>
    );
  }

  // ───── Épreuve en cours ─────
  if (question) {
    const urgent = left <= 60;
    return (
      <div className="page page--narrow">
        <div className="quiz-bar">
          <span>{t("exam.question", { current: question.index, total: question.total })}</span>
          <span role="timer" className={`timer${urgent ? " timer--urgent" : ""}`} aria-label={t("exam.timeLeft")}>⏱ {formatClock(left)}</span>
        </div>
        <ProgressBar value={(question.index - 1) / Math.max(1, question.total)} label={t("exam.progress")} color={levelInfo.color} />
        <p className="sr-only" role="status" aria-live="polite">{announce}</p>
        <Card>
          <h2 className="quiz-q"><FormattedText content={question.question} /></h2>
          <fieldset className="quiz-options" disabled={exam.isLoading}>
            <legend className="sr-only">{t("quiz.options")}</legend>
            {question.options.map((option, i) => (
              <label key={i} className={`quiz-opt${picked === i ? " is-picked" : ""}`}>
                <input type="radio" name="exam-option" className="quiz-opt__input" checked={picked === i} onChange={() => setPicked(i)} />
                <span className="quiz-opt__letter" aria-hidden="true">{String.fromCharCode(65 + i)}</span>
                <span className="quiz-opt__text"><FormattedText content={option} /></span>
              </label>
            ))}
          </fieldset>
          {exam.error && <Alert>{exam.error}</Alert>}
          <div className="actions">
            <Button size="lg" loading={exam.isLoading} disabled={picked === null} accent={levelInfo.color} onClick={() => picked !== null && void exam.answer(picked)}>
              {question.index >= question.total ? t("exam.sendLast") : t("exam.send")}
            </Button>
            <Button variant="ghost" disabled={exam.isLoading} onClick={() => void exam.answer(undefined)}>⏭️ {t("quiz.skip")}</Button>
          </div>
        </Card>
      </div>
    );
  }

  // ───── Configuration ─────
  return (
    <div className="page">
      <PageHeader title={t("exam.title")} subtitle={t("exam.subtitle")} />
      <Card>
        <ContextPicker subject={subject} level={level} onSubject={setSubject} onLevel={setLevel} disabled={exam.isLoading} />
        <div className="picker">
          <TextField label={t("exam.label")} value={label} onChange={setLabel} maxLength={100} />
          <SelectField label={t("quiz.questionCount")} value={String(count)} onChange={(v) => setCount(Number(v))} options={COUNTS.map((c) => ({ value: String(c), label: String(c) }))} />
          <SelectField label={t("exam.duration")} value={String(duration)} onChange={(v) => setDuration(Number(v))} options={DURATIONS.map((d) => ({ value: String(d), label: t("exam.minutes", { n: d }) }))} />
        </div>
        <p className="muted">{t("exam.rules")}</p>
        {exam.error && <Alert onRetry={startExam}>{exam.error}</Alert>}
        <Button size="lg" fullWidth loading={exam.isLoading} accent={levelInfo.color} onClick={startExam}>{t("exam.start")}</Button>
      </Card>

      <Card title={t("exam.history")}>
        {history.loading && <Skeleton lines={3} />}
        {history.error && <Alert onRetry={history.reload}>{history.error}</Alert>}
        {!history.loading && !history.error && (history.data ?? []).length === 0 && <p className="muted">{t("exam.noHistory")}</p>}
        <ul className="stack">
          {(history.data ?? []).map((h) => (
            <li key={h.exam_id} className="recap">
              <span className="recap__q">{h.exam_label} · {t(getSubject(h.subject).labelKey)}</span>
              <span className="recap__status">{Math.round(h.score * 100)} % <span className="muted">· {t("exam.correctCount", { score: h.correct_count, total: h.total })}</span></span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
