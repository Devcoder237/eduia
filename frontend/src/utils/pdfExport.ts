import { jsPDF } from "jspdf";
import { translate as t } from "../i18n";
import { toPdfText } from "./pdfText";
/**
 * Petit constructeur de PDF texte, pense pour rester simple et fiable (pas de
 * capture HTML type html2canvas qui est fragile sur ce genre de mise en page).
 * Gere l'habillage du texte (wrap) et les sauts de page automatiques.
 */
class PdfBuilder {
  private doc: jsPDF;
  private y: number;
  private readonly marginX = 18;
  private readonly pageWidth: number;
  private readonly pageHeight: number;
  private readonly contentWidth: number;
    /** Écrit un texte en le renvoyant à la ligne et en changeant de page si besoin. */
  private wrapped(text: string, lineHeight: number) {
    for (const line of this.doc.splitTextToSize(toPdfText(text), this.contentWidth)) {
      this.ensureSpace(lineHeight);
      this.doc.text(line, this.marginX, this.y);
      this.y += lineHeight;
    }
  }
  constructor() {
    this.doc = new jsPDF({ unit: "mm", format: "a4" });
    this.pageWidth = this.doc.internal.pageSize.getWidth();
    this.pageHeight = this.doc.internal.pageSize.getHeight();
    this.contentWidth = this.pageWidth - this.marginX * 2;
    this.y = 20;
  }

  private ensureSpace(next: number) {
    if (this.y + next > this.pageHeight - 18) {
      this.doc.addPage();
      this.y = 20;
    }
  }

  header(appName: string, subtitle: string) {
    this.doc.setFont("helvetica", "bold");
    this.doc.setFontSize(16);
    this.doc.setTextColor(181, 86, 58); // couleur terracotta EduIA
    this.doc.text(appName, this.marginX, this.y);
    this.y += 7;
    this.doc.setFont("helvetica", "normal");
    this.doc.setFontSize(10);
    this.doc.setTextColor(110, 110, 110);
    this.wrapped(subtitle, 4.5);
    this.doc.setDrawColor(220, 210, 195);
    this.doc.line(this.marginX, this.y, this.pageWidth - this.marginX, this.y);
    this.y += 9;
    this.doc.setTextColor(30, 30, 30);
  }

  title(text: string) {
    this.ensureSpace(10);
    this.doc.setFont("helvetica", "bold");
    this.doc.setFontSize(13);
    this.doc.setTextColor(30, 30, 30);
    this.wrapped(text, 7); 
    this.y += 1;
  }

  scoreBlock(percent: number, label: string) {
    this.ensureSpace(28);
    const color: [number, number, number] = percent >= 80 ? [61, 122, 92] : percent >= 50 ? [184, 132, 46] : [181, 86, 58];
    this.doc.setDrawColor(color[0], color[1], color[2]);
    this.doc.setLineWidth(0.6);
    this.doc.roundedRect(this.marginX, this.y, this.contentWidth, 22, 3, 3);
    this.doc.setFont("helvetica", "bold");
    this.doc.setFontSize(20);
    this.doc.setTextColor(color[0], color[1], color[2]);
    this.doc.text(`${Math.round(percent)}%`, this.marginX + 8, this.y + 14);
    this.doc.setFont("helvetica", "normal");
    this.doc.setFontSize(11);
    this.doc.setTextColor(60, 60, 60);
    this.doc.text(this.doc.splitTextToSize(toPdfText(label), this.contentWidth - 50), this.marginX + 45, this.y + 10);
    this.y += 30;
    this.doc.setTextColor(30, 30, 30);
  }

  subheading(text: string, color: [number, number, number] = [30, 30, 30]) {
    this.ensureSpace(8);
    this.doc.setFont("helvetica", "bold");
    this.doc.setFontSize(11);
    this.doc.setTextColor(color[0], color[1], color[2]);
    this.wrapped(text, 5.5); 
    this.y += 1;
    this.doc.setTextColor(30, 30, 30);
  }

  paragraph(text: string, opts: { bold?: boolean; size?: number; color?: [number, number, number] } = {}) {
    if (!text) return;
    this.doc.setFont("helvetica", opts.bold ? "bold" : "normal");
    this.doc.setFontSize(opts.size ?? 10.5);
    const c = opts.color ?? [40, 40, 40];
    this.doc.setTextColor(c[0], c[1], c[2]);
    const lines = this.doc.splitTextToSize(toPdfText(text), this.contentWidth);
    for (const line of lines) {
      this.ensureSpace(6);
      this.doc.text(line, this.marginX, this.y);
      this.y += 5.5;
    }
    this.doc.setTextColor(30, 30, 30);
  }

  bullet(text: string, symbol: string, color: [number, number, number]) {
    if (!text) return;
    this.doc.setFont("helvetica", "normal");
    this.doc.setFontSize(10.5);
    this.doc.setTextColor(color[0], color[1], color[2]);
    const lines = this.doc.splitTextToSize(toPdfText(`${symbol} ${text}`), this.contentWidth - 4);
    for (const line of lines) {
      this.ensureSpace(6);
      this.doc.text(line, this.marginX + 2, this.y);
      this.y += 5.5;
    }
    this.doc.setTextColor(30, 30, 30);
  }

  spacer(h = 4) {
    this.y += h;
  }

  divider() {
    this.ensureSpace(6);
    this.doc.setDrawColor(225, 220, 210);
    this.doc.line(this.marginX, this.y, this.pageWidth - this.marginX, this.y);
    this.y += 6;
  }

  save(filename: string) {
    this.doc.save(filename);
  }
}

function slug(s: string) {
  return s.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

// ───────────────────────── Examen blanc ─────────────────────────
export function exportExamResultPdf(result: {
  exam_label: string; subject: string; level: string; score: number;
  correct_count: number; total: number; duration_sec: number;
  details: { question: string; options: string[]; correct_index: number; answer_index: number | null; is_correct: boolean | null; explanation: string | null }[];
}) {
  const pdf = new PdfBuilder();
  pdf.header("EduIA", t("pdf.examTitle", { label: result.exam_label, subject: result.subject, level: result.level }));
  const mm = Math.floor(result.duration_sec / 60), ss = result.duration_sec % 60;
  pdf.scoreBlock(result.score * 100, t("pdf.correctAnswers", { correct: result.correct_count, total: result.total, mm, ss }));
  pdf.title(t("pdf.answersDetail"));
  result.details.forEach((d, i) => {
    pdf.subheading(`${i + 1}. ${d.question}`);
    if (d.answer_index === null || d.answer_index === undefined) {
      pdf.paragraph(t("pdf.unanswered"), { color: [150, 130, 60] });
    } else if (d.is_correct) {
      pdf.paragraph(t("pdf.correctPick", { answer: d.options[d.answer_index] ?? "" }), { color: [61, 122, 92] });
    } else {
      pdf.paragraph(t("pdf.wrongPick", { answer: d.options[d.answer_index] ?? "", right: d.options[d.correct_index] ?? "" }), { color: [181, 86, 58] });
    }
    pdf.paragraph(d.explanation ?? "", { size: 9.5, color: [90, 90, 90] });
    pdf.spacer(3);
  });
  pdf.save(`examen-${slug(result.exam_label)}-${slug(result.subject)}.pdf`);
}

// ───────────────────────── Quiz Flash — une seule question ─────────────────────────
export function exportQuizResultPdf(data: {
  subject: string; level: string; topic: string; question: string; options: string[];
  correctIndex: number; selectedIndex: number | null; correct: boolean; explanation: string;
}) {
  const pdf = new PdfBuilder();
  pdf.header("EduIA", t("pdf.quizTitle", { subject: data.subject, level: data.level, topic: data.topic }));
  pdf.title(t("pdf.question"));
  pdf.paragraph(data.question, { bold: true });
  pdf.spacer(2);
  data.options.forEach((opt, i) => {
    const letter = String.fromCharCode(65 + i);
    if (i === data.correctIndex) pdf.bullet(`${letter}. ${opt}`, "✓", [61, 122, 92]);
    else if (i === data.selectedIndex && !data.correct) pdf.bullet(`${letter}. ${opt}`, "✗", [181, 86, 58]);
    else pdf.bullet(`${letter}. ${opt}`, " ", [60, 60, 60]);
  });
  pdf.spacer(4);
  pdf.subheading(data.correct ? t("pdf.rightAnswer") : t("pdf.wrongAnswer"), data.correct ? [61, 122, 92] : [181, 86, 58]);
  pdf.paragraph(data.explanation);
  pdf.save(`quiz-${slug(data.subject)}-${slug(data.topic)}.pdf`);
}

// ───────────────────────── Quiz Flash — session complete (fin de quiz) ─────────────────────────
export function exportQuizSessionPdf(data: {
  subject: string; level: string; topic: string; score: number; total: number;
  recap: { question: string; options: string[]; correctIndex: number; selectedIndex: number | null; correct: boolean; skipped: boolean; explanation: string | null }[];
}) {
  const pdf = new PdfBuilder();
  pdf.header("EduIA", t("pdf.quizTitle", { subject: data.subject, level: data.level, topic: data.topic }));
  const ratio = data.total > 0 ? data.score / data.total : 0;
  pdf.scoreBlock(ratio * 100, t("pdf.score", { score: data.score, total: data.total }));
  pdf.title(t("pdf.questionsDetail"));
  data.recap.forEach((r, i) => {
    pdf.subheading(`${i + 1}. ${r.question}`);
    r.options.forEach((opt, j) => {
      const letter = String.fromCharCode(65 + j);
      if (j === r.correctIndex) pdf.bullet(`${letter}. ${opt}`, "✓", [61, 122, 92]);
      else if (j === r.selectedIndex && !r.correct) pdf.bullet(`${letter}. ${opt}`, "✗", [181, 86, 58]);
      else pdf.bullet(`${letter}. ${opt}`, " ", [70, 70, 70]);
    });
    if (r.skipped) {
      pdf.paragraph(t("pdf.skipped"), { size: 9.5, color: [150, 130, 60] });
    } else {
      pdf.paragraph(r.explanation ?? "", { size: 9.5, color: [90, 90, 90] });
    }
    pdf.spacer(3);
  });
  pdf.save(`quiz-${slug(data.subject)}-${slug(data.topic)}-complet.pdf`);
}

// ───────────────────────── Exercices ─────────────────────────
export function exportExercisePdf(data: {
  subject: string; level: string; topic: string; statement: string; score: number;
  correct: boolean; partial: boolean; feedback: string;
  positivePoints: string[]; errors: string[]; conceptsToReview: string[];
}) {
  const pdf = new PdfBuilder();
  pdf.header("EduIA", t("pdf.exerciseTitle", { subject: data.subject, level: data.level, topic: data.topic }));
  pdf.title(t("pdf.statement"));
  pdf.paragraph(data.statement);
  pdf.spacer(4);
  pdf.scoreBlock(data.score * 100, data.correct ? t("pdf.exCorrect") : data.partial ? t("pdf.exPartial") : t("pdf.exRework"));
  pdf.title(t("pdf.tutorFeedback"));
  pdf.paragraph(data.feedback);
  if (data.positivePoints.length > 0) {
    pdf.spacer(3);
    pdf.subheading(t("pdf.positives"), [61, 122, 92]);
    data.positivePoints.forEach(p => pdf.bullet(p, "✓", [61, 122, 92]));
  }
  if (data.errors.length > 0) {
    pdf.spacer(3);
    pdf.subheading(t("pdf.errors"), [181, 86, 58]);
    data.errors.forEach(e => pdf.bullet(e, "✗", [181, 86, 58]));
  }
  if (data.conceptsToReview.length > 0) {
    pdf.spacer(3);
    pdf.subheading(t("pdf.exRework"));
    pdf.paragraph(data.conceptsToReview.join(", "));
  }
  pdf.save(`exercice-${slug(data.subject)}-${slug(data.topic)}.pdf`);
}

// ───────────────────────── Progression — tableau de bord ─────────────────────────
export function exportProgressPdf(data: {
  totalSessions: number; totalQuestions: number; streakDays: number;
  subjectScores: { subject: string; score: number }[];
  badges: { name: string; icon: string; description: string }[];
  recommendations: { subject: string; reason: string; action: string }[];
}) {
  const pdf = new PdfBuilder();
  pdf.header("EduIA", t("pdf.progressTitle"));

  pdf.title(t("pdf.overview"));
  pdf.paragraph(
    t("pdf.overviewLine", { sessions: data.totalSessions, questions: data.totalQuestions, streak: data.streakDays }),
    { bold: true }
  );
  pdf.spacer(4);

  pdf.title(t("pdf.subjectScores"));
  if (data.subjectScores.length === 0) {
    pdf.paragraph(t("pdf.noSubjectData"), { color: [130, 130, 130] });
  } else {
    data.subjectScores.forEach(s => {
      const pct = Math.round(s.score * 100);
      const color: [number, number, number] = s.score >= 0.8 ? [61, 122, 92] : s.score >= 0.5 ? [184, 132, 46] : [181, 86, 58];
      pdf.bullet(`${s.subject} — ${pct}%`, "•", color);
    });
  }
  pdf.spacer(4);

  pdf.title(t("pdf.badges"));
  if (data.badges.length === 0) {
    pdf.paragraph(t("pdf.noBadges"), { color: [130, 130, 130] });
  } else {
    data.badges.forEach(b => pdf.bullet(`${b.icon} ${b.name} — ${b.description}`, " ", [60, 60, 60]));
  }
  pdf.spacer(4);

  if (data.recommendations.length > 0) {
    pdf.title(t("pdf.recommendations"));
    data.recommendations.forEach(r => {
      pdf.bullet(`${r.subject} — ${r.reason}`, "→", [181, 86, 58]);
    });
  }

  pdf.save("progression-eduia.pdf");
}
