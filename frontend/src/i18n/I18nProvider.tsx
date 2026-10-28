import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  I18nContext, dictFor, getLang, localeFor, setGlobalLang,
  type I18nContextValue, type Lang, type PluralBase, type TranslateParams, type TranslationKey,
} from "./index";

function applyParams(template: string, params?: TranslateParams): string {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (match, name: string) => {
    const value = params[name];
    return value === undefined ? match : String(value);
  });
}

/**
 * Fournit la langue courante à l'arbre React et met à jour `document.documentElement.lang`.
 * La langue est lue depuis localStorage (repli : langue du navigateur) et persistée à chaque changement.
 */
export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => getLang());

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = useCallback((next: Lang) => {
    setGlobalLang(next);
    setLangState(next);
  }, []);

  const value = useMemo<I18nContextValue>(() => {
    const dict = dictFor(lang);
    const rules = new Intl.PluralRules(lang);
    return {
      lang,
      setLang,
      locale: localeFor(lang),
      t: (key: TranslationKey, params?: TranslateParams) => applyParams(dict[key], params),
      tp: (base: PluralBase, count: number, params?: TranslateParams) => {
        const key: TranslationKey = rules.select(count) === "one" ? `${base}_one` : `${base}_other`;
        return applyParams(dict[key], { count, ...params });
      },
    };
  }, [lang, setLang]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}
