import { Fragment, useMemo } from "react";
import type { ReactNode } from "react";
import katex from "katex";
import { escapeHtml } from "../utils/escapeHtml";

/**
 * Rend un texte pouvant contenir du LaTeX (bloc `\[ … \]` / `$$ … $$`, ligne `\( … \)` / `$ … $`)
 * et un Markdown léger (gras, code, titres, listes).
 *
 * Sécurité (audit F7) : le texte vient d'un LLM ou de l'élève, donc n'est jamais fiable.
 *  - tout texte passe par React (échappé automatiquement) ;
 *  - le seul HTML injecté est la sortie de KaTeX en mode `trust: false` ;
 *  - si KaTeX échoue, le repli est le texte ÉCHAPPÉ (`escapeHtml`), jamais le texte brut.
 */

/** HTML d'une formule ; sûr à injecter (sortie KaTeX non fiable-désactivée, ou texte échappé). */
export function renderMathHtml(tex: string, displayMode: boolean): string {
  try {
    return katex.renderToString(tex.trim(), {
      throwOnError: false,
      displayMode,
      trust: false,
      strict: "ignore",
      maxSize: 20,
      maxExpand: 500,
    });
  } catch (error) {
    console.warn("[FormattedText] Formule illisible, affichage du texte brut échappé.", error);
    return `<span class="math-error">${escapeHtml(tex)}</span>`;
  }
}

function Formula({ tex, display }: { tex: string; display: boolean }) {
  const html = useMemo(() => renderMathHtml(tex, display), [tex, display]);
  return (
    <span
      className={display ? "ft-math ft-math--block" : "ft-math"}
      // Sortie KaTeX (trust:false) ou texte échappé : voir l'en-tête du fichier.
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

/** Gras, code et maths en ligne (ne traverse pas les retours à la ligne). */
function formatInline(text: string, keyPrefix: string): ReactNode[] {
  const tokens = text.split(/(\*\*[^*]+\*\*|`[^`]+`|\$[^$\n]+\$|\\\([\s\S]*?\\\))/g);
  return tokens.map((part, i) => {
    const key = `${keyPrefix}-${i}`;
    if (!part) return null;
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) return <strong key={key}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`") && part.length > 2) return <code key={key} className="ft-code">{part.slice(1, -1)}</code>;
    if (part.startsWith("\\(") && part.endsWith("\\)")) return <Formula key={key} tex={part.slice(2, -2)} display={false} />;
    if (part.startsWith("$") && part.endsWith("$") && part.length > 2) return <Formula key={key} tex={part.slice(1, -1)} display={false} />;
    return <Fragment key={key}>{part}</Fragment>;
  });
}

function formatBlock(text: string, keyPrefix: string): ReactNode {
  return text.split("\n").map((line, i) => {
    const key = `${keyPrefix}-l${i}`;
    if (line.startsWith("## ")) return <h4 key={key} className="ft-h">{formatInline(line.slice(3), key)}</h4>;
    if (line.startsWith("# ")) return <h3 key={key} className="ft-h">{formatInline(line.slice(2), key)}</h3>;
    if (/^\d+\.\s/.test(line)) return <p key={key} className="ft-li">{formatInline(line, key)}</p>;
    if (line.startsWith("- ") || line.startsWith("• ")) return <p key={key} className="ft-li">• {formatInline(line.replace(/^[-•]\s/, ""), key)}</p>;
    if (line.trim() === "") return <br key={key} />;
    return <p key={key} className="ft-p">{formatInline(line, key)}</p>;
  });
}

export default function FormattedText({ content }: { content: string }) {
  const nodes = useMemo(() => {
    if (!content) return null;
    // Les blocs LaTeX peuvent s'étaler sur plusieurs lignes : on les isole d'abord.
    return content.split(/(\$\$[\s\S]*?\$\$|\\\[[\s\S]*?\\\])/g).map((part, i) => {
      const key = `b${i}`;
      if (!part) return null;
      if (part.startsWith("$$") && part.endsWith("$$") && part.length > 4) return <Formula key={key} tex={part.slice(2, -2)} display />;
      if (part.startsWith("\\[") && part.endsWith("\\]")) return <Formula key={key} tex={part.slice(2, -2)} display />;
      return <Fragment key={key}>{formatBlock(part, key)}</Fragment>;
    });
  }, [content]);
  if (!nodes) return null;
  return <div className="ft">{nodes}</div>;
}
