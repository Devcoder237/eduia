import { useEffect, useState } from "react";
import { useT } from "../i18n";
import { useQuiz } from "../hooks/useQuiz";
import { useTutorPrefs } from "../hooks/usePrefs";
import { Alert, Button, Card, Chip, PageHeader, ProgressBar, SelectField, TextArea } from "../components/ui";
import { ContextPicker } from "../components/ContextPicker";
import FormattedText from "../components/FormattedText";
import { getLevel, getSubject, getTopics, topicLabel } from "../theme";
import { exportQuizSessionPdf } from "../utils/pdf";
import { errorMessage, type Confidence } from "../services";

/** Longueur minimale de la justification écrite (dès le collège ; facultative en primaire). */
const JUSTIFICATION_MIN = 10;
const COUNTS = [5, 10, 15, 20] as const;
const MAX_INTERLEAVED = 4;

export default function QuizPage() {
  const { t, lang } = useT();
  const { subject, level, setSubject, setLevel } = useTutorPrefs();
  const quiz = useQuiz();
  const topics = getTopics(subject, level);
  const [topic, setTopic] = useState(topics[0] ?? "");
  const [count, setCount] = useState<number>(10);
  // Entrelacement : mélanger 2 à 4 thèmes dans une série améliore la rétention à long terme
  // (Rohrer & Taylor, 2007 ; Dunlosky et al., 2013) par rapport à un bloc sur un seul thème.
  const [interleave, setInterleave] = useState(false);
  const [mixed, setMixed] = useState<string[]>([]);
  const [pending, setPending] = useState<number | null>(null);
  const [justification, setJustification] = useState("");
  const [confidence, setConfidence] = useState<Confidence | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const levelInfo = getLevel(level);
  const subjectInfo = getSubject(subject);
  const justificationRequired = !levelInfo.simplified;

  useEffect(() => { setTopic(getTopics(subject, level)[0] ?? ""); setMixed([]); }, [subject, level]);
  useEffect(() => { setPending(null); setJustification(""); setConfidence(null); }, [quiz.question?.id]);

  const toggleMixed = (name: string) =>
    setMixed((prev) => (prev.includes(name) ? prev.filter((x) => x !== name) : prev.length < MAX_INTERLEAVED ? [...prev, name] : prev));

  const nextTopic = (): string => (interleave && mixed.length >= 2 ? mixed[quiz.questionCount % mixed.length] ?? topic : topic || (topics[0] ?? ""));
  const target = () => ({ subject, level, topic: nextTopic() });
  const interleaveInvalid = interleave && mixed.length < 2;

  const justified = !justificationRequired || justification.trim().length >= JUSTIFICATION_MIN;
  const canValidate = pending !== null && justified && !quiz.isLoading && !quiz.result;

  const exportPdf = async () => {
    setExportError(null);
    try {
      await exportQuizSessionPdf({
        subject: t(subjectInfo.labelKey), level: t(levelInfo.labelKey),
        topic: interleave && mixed.length >= 2 ? mixed.join(" + ") : topicLabel(topic, lang),
        score: quiz.score, total: quiz.recap.length, recap: quiz.recap,
      });
    } catch (e) {
      setExportError(errorMessage(e));
    }
  };

  // ───── Fin de série ─────
  if (quiz.finished) {
    const total = quiz.recap.length;
    const ratio = total > 0 ? quiz.score / total : 0;
    const tone = ratio >= 0.8 ? "good" : ratio >= 0.5 ? "ok" : "low";
    return (
      <div className="page page--narrow">
        <PageHeader title={t("quiz.finished")} subtitle={`${t(subjectInfo.labelKey)} · ${t(levelInfo.labelKey)}`} />
        <Card className={`score-card score-card--${tone}`}>
          <div className="score">
            <span className="score__value">{Math.round(ratio * 100)} %</span>
            <span className="score__label">{t("quiz.correctCount", { score: quiz.score, total })}</span>
          </div>
          <ProgressBar value={ratio} label={t("quiz.score")} />
        </Card>
        {quiz.newBadges.length > 0 && (
          <Card title={t("quiz.newBadges")}>
            <ul className="badges">
              {quiz.newBadges.map((b) => (
                <li key={b.code} className="badge"><span className="badge__icon" aria-hidden="true">{b.icon}</span><div><strong>{b.name}</strong><p className="muted">{b.description}</p></div></li>
              ))}
            </ul>
          </Card>
        )}
        <Card title={t("quiz.recap")}>
          <ol className="stack">
            {quiz.recap.map((r, i) => (
              <li key={i} className="recap">
                <span className="recap__q">{r.question}</span>
                <span className={`recap__status ${r.skipped ? "" : r.correct ? "is-good" : "is-bad"}`}>
                  {r.skipped ? `⏭️ ${t("quiz.skipped")}` : r.correct ? `✓ ${t("quiz.right")}` : `✗ ${t("quiz.wrong")}`}
                </span>
              </li>
            ))}
          </ol>
        </Card>
        {exportError && <Alert>{exportError}</Alert>}
        <div className="actions">
          <Button accent={levelInfo.color} onClick={() => void quiz.start(target(), count)}>{t("quiz.again")}</Button>
          <Button variant="secondary" onClick={() => void exportPdf()}>📄 {t("common.exportPdf")}</Button>
          <Button variant="ghost" onClick={quiz.reset}>{t("quiz.changeTheme")}</Button>
        </div>
      </div>
    );
  }

  // ───── Configuration ─────
  if (!quiz.question) {
    return (
      <div className="page">
        <PageHeader title={t("quiz.title")} subtitle={t("quiz.subtitle")} />
        <Card>
          <ContextPicker subject={subject} level={level} onSubject={setSubject} onLevel={setLevel} {...(interleave ? {} : { topic, onTopic: setTopic })} />
          <SelectField label={t("quiz.questionCount")} value={String(count)} onChange={(v) => setCount(Number(v))} options={COUNTS.map((c) => ({ value: String(c), label: String(c) }))} />
          <label className="check">
            <input type="checkbox" checked={interleave} onChange={(e) => setInterleave(e.target.checked)} />
            <span><strong>{t("quiz.interleave")}</strong><br /><span className="muted">{t("quiz.interleaveHint")}</span></span>
          </label>
          {interleave && (
            <fieldset className="chips-group">
              <legend className="ui-choice__legend">{t("quiz.pickThemes", { max: MAX_INTERLEAVED })}</legend>
              {topics.map((name) => (
                <button key={name} type="button" className={`chip-btn${mixed.includes(name) ? " is-on" : ""}`} aria-pressed={mixed.includes(name)} onClick={() => toggleMixed(name)}>
                  {mixed.includes(name) ? "✓ " : ""}{topicLabel(name, lang)}
                </button>
              ))}
              {interleaveInvalid && <p className="muted" role="status">{t("quiz.pickAtLeastTwo")}</p>}
            </fieldset>
          )}
          {quiz.error && <Alert onRetry={() => void quiz.start(target(), count)}>{quiz.error}</Alert>}
          <Button size="lg" fullWidth loading={quiz.isLoading} disabled={interleaveInvalid} accent={levelInfo.color} onClick={() => void quiz.start(target(), count)}>
            {t("quiz.start")}
          </Button>
        </Card>
      </div>
    );
  }

  // ───── Question en cours ─────
  const { question, result } = quiz;
  return (
    <div className="page page--narrow">
      <div className="quiz-bar">
        <span>{t("quiz.progress", { current: quiz.questionCount, total: quiz.targetCount })}</span>
        <span>{t("quiz.scoreNow", { score: quiz.score })}</span>
      </div>
      <ProgressBar value={quiz.questionCount / Math.max(1, quiz.targetCount)} label={t("quiz.progressLabel")} color={levelInfo.color} />

      <Card>
        <p className="chips"><Chip>{question.topic}</Chip></p>
        <h2 className="quiz-q"><FormattedText content={question.question} /></h2>

        <fieldset className="quiz-options" disabled={quiz.isLoading || result !== null}>
          <legend className="sr-only">{t("quiz.options")}</legend>
          {question.options.map((option, i) => {
            const isCorrect = result !== null && i === result.correct_index;
            const isWrongPick = result !== null && i === quiz.selectedOption && !result.correct;
            const picked = result === null && pending === i;
            return (
              <label key={i} className={`quiz-opt${picked ? " is-picked" : ""}${isCorrect ? " is-correct" : ""}${isWrongPick ? " is-wrong" : ""}`}>
                <input type="radio" name="quiz-option" className="quiz-opt__input" checked={result === null ? pending === i : quiz.selectedOption === i} onChange={() => setPending(i)} />
                <span className="quiz-opt__letter" aria-hidden="true">{isCorrect ? "✓" : isWrongPick ? "✗" : String.fromCharCode(65 + i)}</span>
                <span className="quiz-opt__text"><FormattedText content={option} /></span>
                {isCorrect && <span className="sr-only">{t("quiz.correctAnswer")}</span>}
                {isWrongPick && <span className="sr-only">{t("quiz.yourWrongAnswer")}</span>}
              </label>
            );
          })}
        </fieldset>

        {!result && (
          <>
            <TextArea
              label={justificationRequired ? t("quiz.justify") : t("quiz.justifyOptional")}
              hint={justificationRequired ? t("quiz.justifyHint", { n: justification.trim().length, min: JUSTIFICATION_MIN }) : undefined}
              value={justification}
              onChange={setJustification}
              rows={3}
              maxLength={500}
              placeholder={t("quiz.justifyPlaceholder")}
            />
            <fieldset className="chips-group">
              <legend className="ui-choice__legend">{t("quiz.confidence")}</legend>
              {([1, 2, 3] as const).map((c) => (
                <button key={c} type="button" className={`chip-btn${confidence === c ? " is-on" : ""}`} aria-pressed={confidence === c} onClick={() => setConfidence(confidence === c ? null : c)}>
                  {t(`quiz.confidence${c}`)}
                </button>
              ))}
              <p className="muted">{t("quiz.confidenceHint")}</p>
            </fieldset>
            {quiz.error && <Alert>{quiz.error}</Alert>}
            <div className="actions">
              <Button size="lg" loading={quiz.isLoading} disabled={!canValidate} accent={levelInfo.color} onClick={() => pending !== null && void quiz.answer(pending, justification.trim(), confidence ?? undefined)}>
                {t("quiz.validate")}
              </Button>
              <Button variant="ghost" disabled={quiz.isLoading} onClick={() => void quiz.skip(target())}>⏭️ {t("quiz.skip")}</Button>
            </div>
          </>
        )}

        {result && (
          <div className={`feedback ${result.correct ? "feedback--good" : "feedback--bad"}`} role="status">
            <h3>{result.correct ? `✅ ${t("quiz.right")}` : `❌ ${t("quiz.notQuite")}`}</h3>
            <FormattedText content={result.explanation} />
            {justification.trim() !== "" && <p className="muted">{t("quiz.yourReasoning")} {justification}</p>}
            {result.calibration === "overconfident" && <Alert tone="warning">{t("quiz.calibration.overconfident")}</Alert>}
            {result.calibration === "underconfident" && <Alert tone="info">{t("quiz.calibration.underconfident")}</Alert>}
            {result.consecutive_wrong >= 3 && <Alert tone="info">{t("quiz.struggling")}</Alert>}
            <Button size="lg" accent={levelInfo.color} loading={quiz.isLoading} onClick={() => void quiz.next(target())}>
              {quiz.questionCount >= quiz.targetCount ? t("quiz.seeResults") : t("quiz.next")}
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
}
