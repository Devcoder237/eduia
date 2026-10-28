import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useT, type TranslationKey } from "../i18n";
import { useAuth } from "../context/AuthContext";
import type { Page } from "../lib/router";
import { BrandMark } from "../components/Brand";
import { LangSwitch, ThemeSwitch } from "../components/Switches";
import { Drawer } from "../components/ui";
import { useOnline } from "../hooks/useOnline";

interface NavItem {
  page: Page;
  icon: string;
  labelKey: TranslationKey;
}

const PRIMARY: readonly NavItem[] = [
  { page: "tutor", icon: "💬", labelKey: "nav.tutor" },
  { page: "exercise", icon: "✏️", labelKey: "nav.exercise" },
  { page: "quiz", icon: "🎯", labelKey: "nav.quiz" },
  { page: "progress", icon: "📊", labelKey: "nav.progress" },
];

const SECONDARY: readonly NavItem[] = [
  { page: "exam", icon: "⏱️", labelKey: "nav.exam" },
  { page: "studyplans", icon: "🗓️", labelKey: "nav.studyplans" },
  { page: "history", icon: "🕘", labelKey: "nav.history" },
];

export interface AppLayoutProps {
  page: Page;
  onNavigate: (page: Page) => void;
  children: ReactNode;
}

/**
 * Mise en page connectée, mobile d'abord :
 *  - < 1024 px : en-tête compact + barre de navigation basse (4 destinations + « Plus ») ;
 *  - >= 1024 px : navigation horizontale dans l'en-tête, pas de barre basse.
 * Les zones sûres (encoche, barre de gestes) sont respectées via env(safe-area-inset-*).
 */
export function AppLayout({ page, onNavigate, children }: AppLayoutProps) {
  const { t } = useT();
  const { user, logout } = useAuth();
  const [moreOpen, setMoreOpen] = useState(false);

  const secondary = useMemo<NavItem[]>(() => {
    const items = [...SECONDARY];
    if (user?.is_teacher) items.push({ page: "teacher", icon: "🏫", labelKey: "nav.teacher" });
    if (user?.is_admin) items.push({ page: "admin", icon: "🛠️", labelKey: "nav.admin" });
    items.push({ page: "settings", icon: "⚙️", labelKey: "nav.settings" });
    return items;
  }, [user?.is_teacher, user?.is_admin]);

  const moreActive = secondary.some((item) => item.page === page);
  const online = useOnline();
  const go = (target: Page) => {
    setMoreOpen(false);
    onNavigate(target);
  };

  return (
    <div className="app">
      <a href="#main" className="skip-link">{t("nav.skip")}</a>
      <header className="app-header">
        <button type="button" className="app-brand" onClick={() => go("landing")} aria-label={t("nav.home")}>
          <BrandMark size={30} />
          <span className="app-brand__name">EduIA</span>
        </button>

        <nav className="app-nav" aria-label={t("nav.main")}>
          {[...PRIMARY, ...SECONDARY].map((item) => (
            <button key={item.page} type="button" className={`app-nav__link${page === item.page ? " is-active" : ""}`} aria-current={page === item.page ? "page" : undefined} onClick={() => go(item.page)}>
              <span aria-hidden="true">{item.icon}</span> {t(item.labelKey)}
            </button>
          ))}
          {user?.is_teacher && (
            <button type="button" className={`app-nav__link${page === "teacher" ? " is-active" : ""}`} onClick={() => go("teacher")}>🏫 {t("nav.teacher")}</button>
          )}
          {user?.is_admin && (
            <button type="button" className={`app-nav__link${page === "admin" ? " is-active" : ""}`} onClick={() => go("admin")}>🛠️ {t("nav.admin")}</button>
          )}
        </nav>

        <div className="app-header__actions">
          <LangSwitch />
          <ThemeSwitch />
          <button type="button" className={`ui-iconbtn app-settings${page === "settings" ? " is-active" : ""}`} onClick={() => go("settings")} aria-label={t("nav.settings")} title={t("nav.settings")}>
            <span aria-hidden="true">⚙️</span>
          </button>
          <button type="button" className="ui-btn ui-btn--ghost ui-btn--sm app-logout" onClick={logout}>{t("nav.logout")}</button>
        </div>
      </header>

      {!online && <div className="offline-banner" role="status">📡 {t("app.offline")}</div>}
      <main id="main" className="app-main" tabIndex={-1}>{children}</main>

      <nav className="bottom-nav" aria-label={t("nav.main")}>
        {PRIMARY.map((item) => (
          <button key={item.page} type="button" className={`bottom-nav__item${page === item.page ? " is-active" : ""}`} aria-current={page === item.page ? "page" : undefined} onClick={() => go(item.page)}>
            <span className="bottom-nav__icon" aria-hidden="true">{item.icon}</span>
            <span className="bottom-nav__label">{t(item.labelKey)}</span>
          </button>
        ))}
        <button type="button" className={`bottom-nav__item${moreActive ? " is-active" : ""}`} aria-haspopup="dialog" aria-expanded={moreOpen} onClick={() => setMoreOpen(true)}>
          <span className="bottom-nav__icon" aria-hidden="true">⋯</span>
          <span className="bottom-nav__label">{t("nav.more")}</span>
        </button>
      </nav>

      <Drawer open={moreOpen} onClose={() => setMoreOpen(false)} title={t("nav.more")} side="bottom">
        <ul className="more-list">
          {secondary.map((item) => (
            <li key={item.page}>
              <button type="button" className={`more-list__item${page === item.page ? " is-active" : ""}`} onClick={() => go(item.page)}>
                <span aria-hidden="true">{item.icon}</span> {t(item.labelKey)}
              </button>
            </li>
          ))}
        </ul>
        <div className="more-tools">
          <LangSwitch />
          <ThemeSwitch />
        </div>
        <button type="button" className="ui-btn ui-btn--secondary ui-btn--md ui-btn--full" onClick={() => { setMoreOpen(false); logout(); }}>
          {t("nav.logout")}
        </button>
      </Drawer>
    </div>
  );
}
