import { createContext, useContext } from "react";
import { fr, type TranslationKey } from "./fr";
import { en } from "./en";

/**
 * Module i18n maison (aucune dépendance) : clés typées, interpolation `{nom}`,
 * pluriels via les suffixes `_one` / `_other`, langue persistée dans localStorage.
 * `en.ts` doit définir EXACTEMENT les mêmes clés que `fr.ts` (vérifié par le compilateur).
 */

export type { TranslationKey };
export type Lang = "fr" | "en";
export const LANGS: readonly Lang[] = ["fr", "en"];
export const LANG_STORAGE_KEY = "eduia_lang";

export type TranslateParams = Record<string, string | number>;

/** Clés de base pour lesquelles `<base>_one` et `<base>_other` existent. */
export type PluralBase = TranslationKey extends infer K
  ? K extends `${infer B}_one`
    ? B
    : never
  : never;

const DICTS: Record<Lang, Record<TranslationKey, string>> = { fr, en };

export function isLang(value: unknown): value is Lang {
  return value === "fr" || value === "en";
}

/** Langue initiale : préférence enregistrée, sinon langue du navigateur (fr par défaut). */
export function detectInitialLang(): Lang {
  try {
    const stored = window.localStorage.getItem(LANG_STORAGE_KEY);
    if (isLang(stored)) return stored;
  } catch (error) {
    console.warn("[i18n] Stockage local indisponible, langue du navigateur utilisée.", error);
  }
  const nav = typeof navigator !== "undefined" ? navigator.language.toLowerCase() : "fr";
  return nav.startsWith("en") ? "en" : "fr";
}

let currentLang: Lang = detectInitialLang();

export function getLang(): Lang {
  return currentLang;
}

/** Change la langue globale, la persiste et met à jour `<html lang>`. */
export function setGlobalLang(lang: Lang): void {
  currentLang = lang;
  try {
    window.localStorage.setItem(LANG_STORAGE_KEY, lang);
  } catch (error) {
    console.warn("[i18n] Impossible d'enregistrer la langue (stockage indisponible).", error);
  }
  if (typeof document !== "undefined") document.documentElement.lang = lang;
}

function interpolate(template: string, params?: TranslateParams): string {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (match, name: string) => {
    const value = params[name];
    return value === undefined ? match : String(value);
  });
}

/** Traduction hors React (client HTTP, utilitaires). Dans les composants, préférer `useT()`. */
export function translate(key: TranslationKey, params?: TranslateParams, lang: Lang = currentLang): string {
  return interpolate(DICTS[lang][key], params);
}

/** Traduction avec pluriel : `<base>_one` si la règle de la langue renvoie « one », sinon `<base>_other`. */
export function translatePlural(base: PluralBase, count: number, params?: TranslateParams, lang: Lang = currentLang): string {
  const category = new Intl.PluralRules(lang).select(count);
  const key: TranslationKey = category === "one" ? `${base}_one` : `${base}_other`;
  return interpolate(DICTS[lang][key], { count, ...params });
}

export interface I18nContextValue {
  lang: Lang;
  setLang: (lang: Lang) => void;
  /** Traduit une clé typée. */
  t: (key: TranslationKey, params?: TranslateParams) => string;
  /** Traduit avec pluriel (`{count}` est injecté automatiquement). */
  tp: (base: PluralBase, count: number, params?: TranslateParams) => string;
  /** Code BCP-47 pour Intl / toLocaleDateString. */
  locale: string;
}

export const I18nContext = createContext<I18nContextValue>({
  lang: currentLang,
  setLang: setGlobalLang,
  t: (key, params) => translate(key, params),
  tp: (base, count, params) => translatePlural(base, count, params),
  locale: currentLang === "fr" ? "fr-FR" : "en-GB",
});

/** Hook de traduction : `const { t, lang } = useT();`. */
export function useT(): I18nContextValue {
  return useContext(I18nContext);
}

export function localeFor(lang: Lang): string {
  return lang === "fr" ? "fr-FR" : "en-GB";
}

export function dictFor(lang: Lang): Record<TranslationKey, string> {
  return DICTS[lang];
}
