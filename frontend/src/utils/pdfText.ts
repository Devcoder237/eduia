/** Caractères que la police standard du PDF (Helvetica, jeu WinAnsi) sait dessiner. */
const SAFE = /[\u0020-\u007E\u00A0-\u00FF\u2013\u2014\u2018\u2019\u201C\u201D\u2022\u2026\u20AC\u0152\u0153\u0160\u0161\u0178\u017D\u017E\u2122\n]/;

const REPLACEMENTS: [RegExp, string | ((c: string) => string)][] = [
  [/\\frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}/g, "($1)/($2)"],
  [/\\sqrt\s*\{([^{}]*)\}/g, "racine($1)"],
  [/\\(?:cdot|times)/g, "×"],
  [/\\(?:le|leq)\b/g, "<="],
  [/\\(?:ge|geq)\b/g, ">="],
  [/\\(?:left|right)/g, ""],
  [/\^\{([^{}]*)\}/g, "^$1"],
  [/_\{([^{}]*)\}/g, "_$1"],
  [/\$\$?|\\\(|\\\)|\\\[|\\\]/g, ""],
  [/\*\*([^*]+)\*\*/g, "$1"],
  [/→|⟶|⇒/g, "->"],
  [/≥/g, ">="],
  [/≤/g, "<="],
  [/≠/g, "!="],
  [/≈/g, "~"],
  [/√/g, "racine "],
  [/∞/g, "infini"],
  [/π/g, "pi"],
  [/−/g, "-"],
  [/[✓✔✅]/g, "[v]"],
  [/[✗✘❌]/g, "[x]"],
  [/[⁰¹²³⁴⁵⁶⁷⁸⁹]/g, (c: string) => `^${"⁰¹²³⁴⁵⁶⁷⁸⁹".indexOf(c)}`],
];

/** Prépare un texte pour le PDF : retire le Markdown/LaTeX brut, convertit les symboles usuels, supprime ce que la police ne sait pas dessiner. */
export function toPdfText(input: string): string {
  let text = input.normalize("NFC");
  for (const [pattern, replacement] of REPLACEMENTS) text = text.replace(pattern, replacement as string);
  return Array.from(text).filter((ch) => SAFE.test(ch)).join("").replace(/[ \t]{2,}/g, " ").trim();
}