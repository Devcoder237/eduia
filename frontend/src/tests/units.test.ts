import { describe, expect, it } from "vitest";
import { escapeHtml } from "../utils/escapeHtml";
import { passwordProblem, usernameProblem } from "../utils/validation";
import { daysUntil, formatClock } from "../utils/format";
import { PUBLIC_PAGES, parseHash, toHash } from "../lib/router";
import { buildQuery, normalizeBase } from "../services/http";
import { renderMathHtml } from "../components/FormattedText";
import { fr } from "../i18n/fr";
import { en } from "../i18n/en";

describe("escapeHtml", () => {
  it("neutralise les balises et guillemets", () => {
    expect(escapeHtml(`<img src=x onerror="a()">&'`)).toBe("&lt;img src=x onerror=&quot;a()&quot;&gt;&amp;&#39;");
  });
});

describe("validation", () => {
  it("refuse les mots de passe faibles", () => {
    expect(passwordProblem("court1A")).toBe("validation.passwordShort");
    expect(passwordProblem("toutenminuscule1")).toBe("validation.passwordUpper");
    expect(passwordProblem("SansChiffreIci")).toBe("validation.passwordDigit");
    expect(passwordProblem("Valide123")).toBeNull();
  });
  it("valide les noms d'utilisateur", () => {
    expect(usernameProblem("ab")).toBe("validation.usernameLength");
    expect(usernameProblem("a b c")).toBe("validation.usernameChars");
    expect(usernameProblem("awa.n-1")).toBeNull();
  });
});

describe("format", () => {
  it("formatClock", () => {
    expect(formatClock(65)).toBe("01:05");
    expect(formatClock(-3)).toBe("00:00");
  });
  it("daysUntil", () => {
    const now = new Date(2026, 5, 10, 15);
    expect(daysUntil(new Date(2026, 5, 13, 1).toISOString(), now)).toBe(3);
    expect(daysUntil(new Date(2026, 5, 10, 23).toISOString(), now)).toBe(0);
    expect(daysUntil("n'importe quoi", now)).toBe(0);
  });
});

describe("routeur", () => {
  it("parse et retombe sur l'accueil", () => {
    expect(parseHash("#/tutor?session=12")).toEqual({ page: "tutor", params: { session: "12" } });
    expect(parseHash("#/inconnu").page).toBe("landing");
  });

  it("lit le jeton d'un lien de réinitialisation et reste public", () => {
    const token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2lnLW5hdHVyZS1fLQ";
    expect(parseHash(`#/reset?token=${token}`)).toEqual({ page: "reset", params: { token } });
    expect(toHash("reset", { token })).toBe(`#/reset?token=${token}`);
    expect(PUBLIC_PAGES).toContain("reset");
    expect(toHash("quiz")).toBe("#/quiz");
  });
});

describe("http", () => {
  it("buildQuery ignore les valeurs vides", () => {
    expect(buildQuery({ a: 1, b: undefined, c: null, d: "x y" })).toBe("?a=1&d=x+y");
    expect(buildQuery()).toBe("");
  });
  it("normalizeBase retire /api et le slash final", () => {
    expect(normalizeBase("https://x.onrender.com/api/")).toBe("https://x.onrender.com");
    expect(normalizeBase(undefined)).toBe("");
  });
});

describe("FormattedText", () => {
  it("n'injecte jamais de HTML brut via les formules", () => {
    const html = renderMathHtml("<img src=x onerror=alert(1)>", false);
    expect(html).not.toContain("<img");
  });
});

describe("i18n", () => {
  it("fr et en ont exactement les mêmes clés", () => {
    expect(Object.keys(en).sort()).toEqual(Object.keys(fr).sort());
  });
  it("mêmes paramètres {x} dans chaque langue", () => {
    const params = (s: string): string[] => (s.match(/\{\w+\}/g) ?? []).sort();
    for (const key of Object.keys(fr) as (keyof typeof fr)[]) {
      expect(params(en[key]), key).toEqual(params(fr[key]));
    }
  });
});
