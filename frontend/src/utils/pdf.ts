/**
 * Exports PDF chargés à la demande : jsPDF (~350 Ko) n'alourdit pas le premier chargement
 * (important en 3G). Les appelants doivent capturer l'erreur (réseau coupé pendant le chargement).
 */
type Mod = typeof import("./pdfExport");

export async function exportExamResultPdf(...args: Parameters<Mod["exportExamResultPdf"]>): Promise<void> {
  (await import("./pdfExport")).exportExamResultPdf(...args);
}
export async function exportQuizSessionPdf(...args: Parameters<Mod["exportQuizSessionPdf"]>): Promise<void> {
  (await import("./pdfExport")).exportQuizSessionPdf(...args);
}
export async function exportExercisePdf(...args: Parameters<Mod["exportExercisePdf"]>): Promise<void> {
  (await import("./pdfExport")).exportExercisePdf(...args);
}
export async function exportProgressPdf(...args: Parameters<Mod["exportProgressPdf"]>): Promise<void> {
  (await import("./pdfExport")).exportProgressPdf(...args);
}
