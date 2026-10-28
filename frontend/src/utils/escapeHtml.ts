const ESCAPES: Readonly<Record<string, string>> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
};

/**
 * Échappe les cinq caractères significatifs en HTML.
 *
 * À utiliser dès qu'un texte non fiable (réponse du LLM, saisie utilisateur) doit
 * transiter par du HTML brut. Dans le JSX, React échappe déjà : n'appelez cette
 * fonction que pour les rares chemins `dangerouslySetInnerHTML`.
 */
export function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (char) => ESCAPES[char] ?? char);
}
