import { useEffect, useState } from "react";
import { useT } from "../i18n";
import { useExercise } from "../hooks/useExercise";
import { useGuidedReview } from "../hooks/useProgress";
import { useTutorPrefs } from "../hooks/usePrefs";
import { Alert, Button, Card, PageHeader, Spinner, TextArea, Chip, ProgressBar } from "../components/ui";
import { ContextPicker } from "../components/ContextPicker";
import FormattedText from "../components/FormattedText";
import { getLevel, getSubject, getTopics, topicLabel } from "../theme";
import { exportExercisePdf } from "../utils/pdf";
import { errorMessage } from "../services";

export default function ExercisePage() {
  const { t, lang } = useT();
  const { subject, level, setSubject, setLevel } = useTutorPrefs();
  const ex = useExercise();
  const review = useGuidedReview();
  const [topic, setTopic] = useState(() => getTopics(subject, level)[0] ?? "");
  const [answer, setAnswer] = useState("");
  const [showReview, setShowReview] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const levelInfo = getLevel(level);

  // Le thème reste cohérent avec la matière ET le niveau choisis.
  useEffect(() => { setTopic(getTopics(subject, level)[0] ?? ""); }, [subject, level]);
  // Brouillon vidé à chaque nouvel exercice.
  useEffect(() => { setAnswer(""); }, [ex.exercise?.id]);

  const openReview = () => { setShowReview(true); void review.load(); };
  const fromRecommendation = (recSubject: string, concept: string | null) => {
    setSubject(recSubject);
    setShowReview(false);
    void ex.generate(recSubject, level, concept ?? getTopics(recSubject, level)[0] ?? topic);
  };

  const exportPdf = async () => {
    if (!ex.exercise || !ex.result) return;
    setExportError(null);
    try {
      await exportExercisePdf({
        subject: t(getSubject(ex.exercise.subject).labelKey), level: t(levelInfo.labelKey), topic: topicLabel(ex.exercise.topic, lang),
        statement: ex.exercise.statement, score: ex.result.score, correct: ex.result.correct, partial: ex.result.partial,
        feedback: ex.result.feedback, positivePoints: ex.result.positive_points, errors: ex.result.errors,
        conceptsToReview: ex.result.concepts_to_review,
      });
    } catch (e) {
      setExportError(errorMessage(e));
    }
  };

  // ───── Écran de configuration ─────
  if (!ex.exercise) {
    return (
      <div className="page">
        <PageHeader title={t("exercise.title")} subtitle={t("exercise.subtitle")} actions={<Button variant="secondary" onClick={openReview}>🧭 {t("exercise.guided")}</Button>} />
        {showReview && (
          <Card title={t("exercise.guidedTitle")}>
            {review.isLoading && <Spinner />}
            {review.error && <Alert onRetry={() => void review.load()}>{review.error}</Alert>}
            {!review.isLoading && !review.error && !review.hasGaps && <p>{t("exercise.noGaps")}</p>}
            <ul className="stack">
              {review.items.map((item) => (
                <li key={`${item.subject}-${item.concept ?? ""}`} className="rec">
                  <div>
                    <strong>{getSubject(item.subject).icon} {t(getSubject(item.subject).labelKey)}{item.concept ? ` — ${topicLabel(item.concept, lang)}` : ""}</strong>
                    <p className="muted">{item.reason}</p>
                    <p>{item.action}</p>
                  </div>
                  <Button size="sm" onClick={() => fromRecommendation(item.subject, item.concept)}>{t("exercise.start")}</Button>
                </li>
              ))}
            </ul>
          </Card>
        )}
        <Card>
          <ContextPicker subject={subject} level={level} onSubject={setSubject} onLevel={setLevel} topic={topic} onTopic={setTopic} disabled={ex.isGenerating} />
          {ex.error && <Alert onRetry={() => void ex.generate(subject, level, topic)}>{ex.error}</Alert>}
          <Button size="lg" fullWidth loading={ex.isGenerating} accent={levelInfo.color} onClick={() => void ex.generate(subject, level, topic)}>
            {ex.isGenerating ? t("exercise.generating") : t("exercise.generate")}
          </Button>
        </Card>
      </div>
    );
  }

  // ───── Énoncé et correction ─────
  const { exercise, result } = ex;
  const scoreTone = result ? (result.score >= 0.8 ? "good" : result.score >= 0.5 ? "ok" : "low") : "ok";
  return (
    <div className="page page--narrow">
      <PageHeader
        title={topicLabel(exercise.topic, lang)}
        subtitle={`${getSubject(exercise.subject).icon} ${t(getSubject(exercise.subject).labelKey)} · ${t(getLevel(exercise.level).labelKey)} · ${t("exercise.minutes", { n: exercise.estimated_min })}`}
        actions={<Button variant="ghost" onClick={ex.reset}>← {t("exercise.back")}</Button>}
      />
      <Card title={t("exercise.statement")}>
        <FormattedText content={exercise.statement} />
        {exercise.concepts.length > 0 && <p className="chips">{exercise.concepts.map((c) => <Chip key={c}>{c}</Chip>)}</p>}
      </Card>

      {exercise.hints.length > 0 && !result && (
        <Card title={t("exercise.hints")} as="h2">
          <ol className="stack">
            {exercise.hints.slice(0, ex.hintsShown).map((h, i) => <li key={i}><FormattedText content={h} /></li>)}
          </ol>
          {ex.hintsShown < exercise.hints.length && (
            <Button variant="secondary" onClick={ex.showNextHint}>
              💡 {t("exercise.hintNext", { shown: ex.hintsShown, total: exercise.hints.length })}
            </Button>
          )}
        </Card>
      )}

      {!result && (
        <Card title={t("exercise.yourAnswer")}>
          <TextArea label={t("exercise.answerLabel")} value={answer} onChange={setAnswer} rows={6} maxLength={5000} placeholder={t("exercise.answerPlaceholder")} disabled={ex.isSubmitting} />
          {ex.error && <Alert>{ex.error}</Alert>}
          <Button size="lg" fullWidth loading={ex.isSubmitting} disabled={!answer.trim()} onClick={() => void ex.submit(answer.trim())}>
            {ex.isSubmitting ? t("exercise.correcting") : t("exercise.submit")}
          </Button>
        </Card>
      )}

      {result && (
        <Card title={t("exercise.correction")} className={`score-card score-card--${scoreTone}`}>
          <div className="score">
            <span className="score__value">{Math.round(result.score * 100)} %</span>
            <span className="score__label">{result.correct ? t("exercise.correct") : result.partial ? t("exercise.partial") : t("exercise.toReview")}</span>
          </div>
          <ProgressBar value={result.score} label={t("exercise.score")} />
          <FormattedText content={result.feedback} />
          {result.positive_points.length > 0 && (
            <div><h3 className="sub sub--good">✓ {t("exercise.positives")}</h3><ul>{result.positive_points.map((p, i) => <li key={i}>{p}</li>)}</ul></div>
          )}
          {result.errors.length > 0 && (
            <div><h3 className="sub sub--bad">✗ {t("exercise.errors")}</h3><ul>{result.errors.map((p, i) => <li key={i}>{p}</li>)}</ul></div>
          )}
          {result.concepts_to_review.length > 0 && (
            <div><h3 className="sub">📌 {t("exercise.conceptsToReview")}</h3><p className="chips">{result.concepts_to_review.map((c) => <Chip key={c}>{c}</Chip>)}</p></div>
          )}
          {result.rubric_breakdown.length > 0 && (
            <details className="rubric">
              <summary>{t("exercise.rubric")}</summary>
              <ul className="stack">
                {result.rubric_breakdown.map((r) => (
                  <li key={r.critere}>
                    <div className="rubric__row"><strong>{r.critere}</strong><span>{r.points_obtenus} / {r.points_max}</span></div>
                    <p className="muted">{r.justification}</p>
                  </li>
                ))}
              </ul>
            </details>
          )}
          {exportError && <Alert>{exportError}</Alert>}
          <div className="actions">
            <Button onClick={() => { ex.reset(); void ex.generate(subject, level, topic); }} accent={levelInfo.color}>{t("exercise.another")}</Button>
            <Button variant="secondary" onClick={() => void exportPdf()}>📄 {t("common.exportPdf")}</Button>
            <Button variant="ghost" onClick={ex.reset}>{t("exercise.back")}</Button>
          </div>
        </Card>
      )}
    </div>
  );
}
