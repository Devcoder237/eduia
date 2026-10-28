import { afterEach, describe, expect, it, vi } from "vitest";
import { getLang, setGlobalLang, translate } from "../i18n";
import { request } from "../services/http";
import { QUICK_QUESTIONS_BY_LEVEL, TOPICS_BY_LEVEL, getQuickQuestions, topicLabel } from "../theme";
import { isLangLocked, setLangLocked } from "../lib/langLock";
import { speechLangFor } from "../hooks/useVoice";

afterEach(() => {
  vi.unstubAllGlobals();
  setGlobalLang("fr");
  setLangLocked(false);
});

describe("en-tête Accept-Language", () => {
  for (const lang of ["fr", "en"] as const) {
    it(`envoie « ${lang} » sur chaque requête`, async () => {
      const fetchMock = vi.fn(async () => new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } }));
      vi.stubGlobal("fetch", fetchMock);
      setGlobalLang(lang);
      await request("/api/ping");
      const init = (fetchMock.mock.calls[0] as unknown as [string, RequestInit])[1];
      const headers = new Headers(init.headers);
      expect(headers.get("Accept-Language")).toBe(lang);
    });
  }
});

describe("thèmes et questions rapides", () => {
  it("chaque thème a un libellé anglais distinct du français ou identique voulu", () => {
    for (const levels of Object.values(TOPICS_BY_LEVEL)) {
      for (const topics of Object.values(levels)) {
        for (const topic of topics) {
          expect(topicLabel(topic, "en").length, topic).toBeGreaterThan(0);
          expect(topicLabel(topic, "fr")).toBe(topic);
        }
      }
    }
  });

  it("chaque thème est réellement traduit (sauf termes identiques)", () => {
    const untranslated: string[] = [];
    for (const levels of Object.values(TOPICS_BY_LEVEL)) {
      for (const topics of Object.values(levels)) {
        for (const topic of topics) if (topicLabel(topic, "en") === topic) untranslated.push(topic);
      }
    }
    // Noms propres identiques dans les deux langues ; toute autre entrée accentuée signale une traduction manquante.
    const sameInBothLanguages = new Set(["La Fontaine & Molière"]);
    expect(untranslated.filter((x) => !sameInBothLanguages.has(x) && /[àâçéèêëîïôùûü]/i.test(x))).toEqual([]);
  });

  it("les questions rapides existent dans les deux langues, même nombre", () => {
    for (const [subject, levels] of Object.entries(QUICK_QUESTIONS_BY_LEVEL)) {
      for (const [level, questions] of Object.entries(levels)) {
        const en = getQuickQuestions(subject, level, "en");
        expect(en.length, `${subject}/${level}`).toBe(questions.length);
        // La matière « anglais » propose déjà ses questions rapides en anglais dans les deux interfaces.
        if (subject !== "anglais") expect(en).not.toEqual(questions);
      }
    }
  });
});

describe("verrou de langue (examen)", () => {
  it("se pose et se lève", () => {
    expect(isLangLocked()).toBe(false);
    setLangLocked(true);
    expect(isLangLocked()).toBe(true);
    setLangLocked(false);
    expect(isLangLocked()).toBe(false);
  });
});

describe("langue de la voix", () => {
  it("la matière anglais est lue en anglais même en interface française", () => {
    expect(speechLangFor("anglais", "fr")).toBe("en");
    expect(speechLangFor("mathematiques", "fr")).toBe("fr");
    expect(speechLangFor("mathematiques", "en")).toBe("en");
  });
});

describe("clés PDF", () => {
  it("existent dans les deux langues", () => {
    setGlobalLang("en");
    expect(getLang()).toBe("en");
    expect(translate("pdf.exCorrect")).toBe("Correct");
    expect(translate("pdf.answersDetail")).toBe("Answer details");
    setGlobalLang("fr");
    expect(translate("pdf.answersDetail")).toBe("Détail des réponses");
  });
});
