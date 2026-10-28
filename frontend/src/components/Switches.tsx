import { useLangLocked } from "../lib/langLock";
import { useT, LANGS, type Lang } from "../i18n";
import { useTheme } from "../hooks/useTheme";

export function LangSwitch() {
  const { lang, setLang, t } = useT();
  const locked = useLangLocked();
  return (
    <div className="seg" role="group" aria-label={t("settings.language")}>
      {LANGS.map((code: Lang) => (
        <button
          key={code}
          type="button"
          className={`seg__btn${lang === code ? " is-active" : ""}`}
          aria-pressed={lang === code}
          disabled={locked && lang !== code}
          title={locked ? t("lang.lockedExam") : undefined}
          onClick={() => setLang(code)}
          lang={code}
        >
          {code.toUpperCase()}
        </button>
      ))}
    </div>
  );
}

export function ThemeSwitch() {
  const { theme, toggle } = useTheme();
  const { t } = useT();
  return (
    <button type="button" className="ui-iconbtn" onClick={toggle} aria-label={theme === "dark" ? t("theme.toLight") : t("theme.toDark")} title={theme === "dark" ? t("theme.toLight") : t("theme.toDark")}>
      <span aria-hidden="true">{theme === "dark" ? "☀️" : "🌙"}</span>
    </button>
  );
}
