import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useT, type TranslationKey } from "../i18n";
import { SUBJECTS } from "../theme";
import { LangSwitch, ThemeSwitch } from "../components/Switches";
import "../styles/landing.css";

/* Jeu d'icônes SVG (style Lucide, MIT) : trait 1,75, currentColor → s'adapte au thème. */
const ICON: Record<string, ReactNode> = {
  arrow:     <><path d="M5 12h14" /><path d="m12 5 7 7-7 7" /></>,
  check:     <path d="M20 6 9 17l-5-5" />,
  spark:     <path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z" />,
  chat:      <path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z" />,
  pencil:    <><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" /></>,
  target:    <><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="5" /><circle cx="12" cy="12" r="1.4" /></>,
  compass:   <><circle cx="12" cy="12" r="9" /><polygon points="15.8 8.2 13.4 13.4 8.2 15.8 10.6 10.6" /></>,
  trending:  <><path d="M16 7h6v6" /><path d="m22 7-8.5 8.5-5-5L2 17" /></>,
  cap:       <><path d="M21 10.3 12 6 3 10.3l9 4.2 9-4.2Z" /><path d="M21 10.3V16" /><path d="M6.5 12.4V16c0 1.4 2.5 2.6 5.5 2.6s5.5-1.2 5.5-2.6v-3.6" /></>,
  scroll:    <><path d="M15 2H7a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V6Z" /><path d="M15 2v4h4" /><path d="M9 12h6" /><path d="M9 16h6" /></>,
  building:  <><path d="M4 22V6l8-4 8 4v16" /><path d="M4 22h16" /><path d="M9 22v-5h6v5" /><path d="M9 9h.01" /><path d="M15 9h.01" /><path d="M9 13h.01" /><path d="M15 13h.01" /></>,
  users:     <><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" /></>,
  menu:      <><path d="M4 6h16" /><path d="M4 12h16" /><path d="M4 18h16" /></>,
  close:     <><path d="M18 6 6 18" /><path d="m6 6 12 12" /></>,
  layers:    <><path d="m12 2 9 4.5-9 4.5-9-4.5L12 2Z" /><path d="m3 12 9 4.5 9-4.5" /><path d="m3 17 9 4.5 9-4.5" /></>,
  book:      <><path d="M12 7v13" /><path d="M3 18V5a1 1 0 0 1 1-1h4a4 4 0 0 1 4 3 4 4 0 0 1 4-3h4a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-5a3 3 0 0 0-3 2 3 3 0 0 0-3-2H4a1 1 0 0 1-1-1Z" /></>,
  clock:     <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  infinity:  <path d="M12 12c-1.8-2.4-3.6-3.6-5.5-3.6a3.6 3.6 0 1 0 0 7.2c1.9 0 3.7-1.2 5.5-3.6Zm0 0c1.8 2.4 3.6 3.6 5.5 3.6a3.6 3.6 0 0 0 0-7.2c-1.9 0-3.7 1.2-5.5 3.6Z" />,
  brain:     <><path d="M9 4a3 3 0 0 0-3 3 3 3 0 0 0-1 5.8V16a3 3 0 0 0 4 2.8" /><path d="M9 4a2.5 2.5 0 0 1 3 2.5V19a2 2 0 0 1-3 1.7" /><path d="M15 4a3 3 0 0 1 3 3 3 3 0 0 1 1 5.8V16a3 3 0 0 1-4 2.8" /><path d="M15 4a2.5 2.5 0 0 0-3 2.5" /></>,
  route:     <><circle cx="6" cy="19" r="2.4" /><circle cx="18" cy="5" r="2.4" /><path d="M8.5 19H14a4 4 0 0 0 0-8h-4a4 4 0 0 1 0-8h5.5" /></>,
  refresh:   <><path d="M3 12a9 9 0 0 1 15-6.7L21 8" /><path d="M21 3v5h-5" /><path d="M21 12a9 9 0 0 1-15 6.7L3 16" /><path d="M3 21v-5h5" /></>,
};


function Ico({ name, size = 22 }: { name: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {ICON[name]}
    </svg>
  );
}

function LogoMark({ size = 34 }: { size?: number }) {
  return (
    <span className="lp-logo" style={{ width: size, height: size }} aria-hidden="true">
      <svg width={size * 0.6} height={size * 0.6} viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" strokeWidth={1.9} strokeLinecap="round" strokeLinejoin="round">
        {ICON.cap}
      </svg>
    </span>
  );
}

/** Révélation au défilement : ajoute `.reveal-in` aux éléments `.reveal` quand ils deviennent visibles. */
function useReveal() {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const root = ref.current;
    if (!root) return undefined;
    const els = Array.from(root.querySelectorAll<HTMLElement>(".reveal"));
    if (!window.IntersectionObserver || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      els.forEach((el) => el.classList.add("reveal-in"));
      return undefined;
    }
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) { e.target.classList.add("reveal-in"); io.unobserve(e.target); }
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -8% 0px" });
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);
  return ref;
}

interface CopyItem { ico: string; t: TranslationKey; d: TranslationKey }

const AUDIENCES: CopyItem[] = [
  { ico: "cap", t: "landing.aud1.t", d: "landing.aud1.d" },
  { ico: "scroll", t: "landing.aud2.t", d: "landing.aud2.d" },
  { ico: "building", t: "landing.aud3.t", d: "landing.aud3.d" },
  { ico: "users", t: "landing.aud4.t", d: "landing.aud4.d" },
];
const FEATURES: CopyItem[] = [
  { ico: "spark", t: "landing.feat1.t", d: "landing.feat1.d" },
  { ico: "chat", t: "landing.feat2.t", d: "landing.feat2.d" },
  { ico: "pencil", t: "landing.feat3.t", d: "landing.feat3.d" },
  { ico: "target", t: "landing.feat4.t", d: "landing.feat4.d" },
  { ico: "compass", t: "landing.feat5.t", d: "landing.feat5.d" },
  { ico: "trending", t: "landing.feat6.t", d: "landing.feat6.d" },
];
const PEDAGOGY: CopyItem[] = [
  { ico: "book", t: "landing.ped1.t", d: "landing.ped1.d" },
  { ico: "brain", t: "landing.ped2.t", d: "landing.ped2.d" },
  { ico: "route", t: "landing.ped3.t", d: "landing.ped3.d" },
  { ico: "refresh", t: "landing.ped4.t", d: "landing.ped4.d" },
];
const STATS: { ico: string; n: string; l: TranslationKey; d: TranslationKey }[] = [
  { ico: "layers", n: "4", l: "landing.stat1.l", d: "landing.stat1.d" },
  { ico: "book", n: "8", l: "landing.stat2.l", d: "landing.stat2.d" },
  { ico: "clock", n: "24/7", l: "landing.stat3.l", d: "landing.stat3.d" },
  { ico: "infinity", n: "∞", l: "landing.stat4.l", d: "landing.stat4.d" },
];
const EXAMS = ["CEP", "BEPC", "Probatoire", "BAC", "GCE O/A Level", "LMD"];

export default function LandingPage({ onStart, onLogin, onLegal, serverWaking }: { onStart: () => void; onLogin: () => void; onLegal: () => void; serverWaking: boolean }) {
  const { t } = useT();
  const [menuOpen, setMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const rootRef = useReveal();

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const navLinks: { href: string; label: TranslationKey }[] = [
    { href: "#fonctionnalites", label: "landing.nav.features" },
    { href: "#public", label: "landing.nav.audience" },
    { href: "#matieres", label: "landing.nav.subjects" },
    { href: "#pedagogie", label: "landing.nav.pedagogy" },
  ];

  return (
    <div className="lp-root" ref={rootRef}>
      <a href="#main-landing" className="skip-link">{t("nav.skip")}</a>
      <header className={`lp-nav${scrolled ? " lp-nav-scrolled" : ""}`}>
        <div className="lp-nav-in">
          <a href="#top" className="lp-brand" onClick={() => setMenuOpen(false)}>
            <LogoMark size={34} />
            <span className="lp-brand-name">EduIA</span>
            <span className="lp-brand-tag">CM</span>
          </a>
          <nav className="lp-nav-links" aria-label={t("nav.main")}>
            {navLinks.map(({ href, label }) => <a key={href} href={href}>{t(label)}</a>)}
          </nav>
          <div className="lp-nav-actions">
            <LangSwitch />
            <ThemeSwitch />
            <button type="button" className="lp-btn lp-btn-ghost" onClick={onLogin}>{t("auth.login")}</button>
            <button type="button" className="lp-btn lp-btn-primary lp-hide-sm" onClick={onStart}>{t("landing.start")} <Ico name="arrow" size={16} /></button>
            <button type="button" className="lp-icon-btn lp-show-sm" aria-label={t("landing.menu")} aria-expanded={menuOpen} onClick={() => setMenuOpen((o) => !o)}>
              <Ico name={menuOpen ? "close" : "menu"} size={22} />
            </button>
          </div>
        </div>
        {menuOpen && (
          <div className="lp-mobile-menu">
            {navLinks.map(({ href, label }) => <a key={href} href={href} onClick={() => setMenuOpen(false)}>{t(label)}</a>)}
            <div className="lp-mobile-tools"><LangSwitch /><ThemeSwitch /></div>
            <button type="button" className="lp-btn lp-btn-primary" onClick={() => { setMenuOpen(false); onStart(); }}>{t("landing.startFree")} <Ico name="arrow" size={16} /></button>
          </div>
        )}
      </header>

      <main id="main-landing" tabIndex={-1}>
        <section className="lp-hero" id="top">
          <div className="lp-hero-photo" aria-hidden="true" />
          <div className="lp-hero-scrim" aria-hidden="true" />
          <div className="lp-hero-inner">
            <div className="lp-badge lp-anim" style={{ ["--d" as string]: "0ms" }}><span className="lp-badge-dot" /> {t("landing.badge")} 🇨🇲</div>
            <h1 className="lp-h1 lp-anim" style={{ ["--d" as string]: "70ms" }}>{t("landing.h1.pre")} <em>{t("landing.h1.em")}</em> {t("landing.h1.post")}</h1>
            <p className="lp-lead lp-anim" style={{ ["--d" as string]: "150ms" }}>{t("landing.lead.pre")} <strong>{t("landing.lead.strong")}</strong> {t("landing.lead.post")}</p>
            {serverWaking && <p className="lp-wake lp-anim" role="status">⏳ {t("landing.serverWaking")}</p>}
            <div className="lp-hero-cta lp-anim" style={{ ["--d" as string]: "230ms" }}>
              <button type="button" className="lp-btn lp-btn-primary lp-btn-lg" onClick={onStart}>{t("landing.startFree")} <Ico name="arrow" size={18} /></button>
              <button type="button" className="lp-btn lp-btn-outline lp-btn-lg" onClick={onLogin}>{t("landing.haveAccount")}</button>
            </div>
            <div className="lp-hero-proof lp-anim" style={{ ["--d" as string]: "320ms" }}>
              <span className="lp-proof-label">{t("landing.covers")}</span>
              {EXAMS.map((e) => <span className="lp-proof-pill" key={e}>{e}</span>)}
            </div>
          </div>
          <a href="#fonctionnalites" className="lp-scrollcue" aria-label={t("landing.discover")}><span /> {t("landing.discover")}</a>
        </section>

        <section className="lp-section lp-stats-sec" aria-label={t("landing.statsLabel")}>
          <div className="lp-grid lp-grid-4 lp-stagger">
            {STATS.map(({ ico, n, l, d }) => (
              <div className="lp-stat reveal" key={l}>
                <span className="lp-stat-ico"><Ico name={ico} size={20} /></span>
                <div className="lp-stat-n">{n}</div>
                <div className="lp-stat-l">{t(l)}</div>
                <div className="lp-stat-d">{t(d)}</div>
              </div>
            ))}
          </div>
        </section>

        <section className="lp-section" id="public">
          <div className="lp-head">
            <div className="lp-eyebrow reveal">{t("landing.aud.eyebrow")}</div>
            <h2 className="lp-h2 reveal">{t("landing.aud.title")}</h2>
            <p className="lp-section-sub reveal">{t("landing.aud.sub")}</p>
          </div>
          <div className="lp-grid lp-grid-2 lp-stagger lp-mt">
            {AUDIENCES.map(({ ico, t: title, d }) => (
              <article className="lp-card lp-card-lg reveal" key={title}>
                <span className="lp-card-ico"><Ico name={ico} size={24} /></span>
                <h3 className="lp-card-t">{t(title)}</h3>
                <p className="lp-card-d">{t(d)}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="lp-section lp-band" id="fonctionnalites">
          <div className="lp-head">
            <div className="lp-eyebrow reveal">{t("landing.feat.eyebrow")}</div>
            <h2 className="lp-h2 reveal">{t("landing.feat.title")}</h2>
          </div>
          <div className="lp-grid lp-grid-3 lp-stagger lp-mt">
            {FEATURES.map(({ ico, t: title, d }) => (
              <article className="lp-card reveal" key={title}>
                <span className="lp-card-ico"><Ico name={ico} size={22} /></span>
                <h3 className="lp-card-t">{t(title)}</h3>
                <p className="lp-card-d">{t(d)}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="lp-section" id="matieres">
          <div className="lp-head">
            <div className="lp-eyebrow reveal">{t("landing.subj.eyebrow")}</div>
            <h2 className="lp-h2 reveal">{t("landing.subj.title")}</h2>
            <p className="lp-section-sub reveal">{t("landing.subj.sub")}</p>
          </div>
          <ul className="lp-subjects lp-stagger lp-mt">
            {SUBJECTS.map((s) => (
              <li className="lp-subject reveal" key={s.id}>
                <span className="lp-subject-mono" style={{ background: s.color }} aria-hidden="true">{t(s.labelKey).charAt(0)}</span>
                {t(s.labelKey)}
              </li>
            ))}
          </ul>
        </section>

        <section className="lp-section lp-band" id="pedagogie">
          <div className="lp-head">
            <div className="lp-eyebrow reveal">{t("landing.ped.eyebrow")}</div>
            <h2 className="lp-h2 reveal">{t("landing.ped.title")}</h2>
            <p className="lp-section-sub reveal">{t("landing.ped.sub")}</p>
          </div>
          <div className="lp-grid lp-grid-2 lp-stagger lp-mt">
            {PEDAGOGY.map(({ ico, t: title, d }, i) => (
              <article className="lp-pedago reveal" key={title}>
                <span className="lp-pedago-num" aria-hidden="true">{String(i + 1).padStart(2, "0")}</span>
                <div>
                  <div className="lp-pedago-head">
                    <span className="lp-pedago-ico"><Ico name={ico} size={20} /></span>
                    <h3 className="lp-card-t">{t(title)}</h3>
                  </div>
                  <p className="lp-card-d">{t(d)}</p>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="lp-section">
          <div className="lp-cta reveal">
            <div className="lp-cta-glow" aria-hidden="true" />
            <h2 className="lp-cta-h">{t("landing.cta.title")}</h2>
            <p className="lp-cta-p">{t("landing.cta.text")}</p>
            <div className="lp-hero-cta lp-center">
              <button type="button" className="lp-btn lp-btn-primary lp-btn-lg" onClick={onStart}>{t("landing.cta.start")} <Ico name="arrow" size={18} /></button>
              <button type="button" className="lp-btn lp-btn-outline lp-btn-lg" onClick={onLogin}>{t("auth.login")}</button>
            </div>
          </div>
        </section>
      </main>

      <footer className="lp-footer">
        <div className="lp-footer-in">
          <div className="lp-footer-grid">
            <div className="lp-footer-brand">
              <a href="#top" className="lp-brand"><LogoMark size={30} /><span className="lp-brand-name">EduIA</span></a>
              <p className="lp-footer-blurb">{t("landing.footer.blurb")}</p>
              <p className="lp-footer-made">{t("landing.footer.made")} 🇨🇲</p>
            </div>
            <div className="lp-footer-col">
              <div className="lp-footer-h">{t("landing.footer.product")}</div>
              <a href="#fonctionnalites">{t("landing.nav.features")}</a>
              <a href="#matieres">{t("landing.nav.subjects")}</a>
              <a href="#pedagogie">{t("landing.nav.pedagogy")}</a>
              <button type="button" className="lp-footer-link" onClick={onStart}>{t("landing.start")}</button>
            </div>
            <div className="lp-footer-col">
              <div className="lp-footer-h">{t("landing.footer.audience")}</div>
              <a href="#public">{t("landing.aud1.t")}</a>
              <a href="#public">{t("landing.aud2.t")}</a>
              <a href="#public">{t("landing.aud3.t")}</a>
              <a href="#public">{t("landing.aud4.t")}</a>
            </div>
            <div className="lp-footer-col">
              <div className="lp-footer-h">{t("landing.footer.access")}</div>
              <button type="button" className="lp-footer-link" onClick={onLogin}>{t("auth.login")}</button>
              <button type="button" className="lp-footer-link" onClick={onStart}>{t("auth.createAccount")}</button>
            </div>
          </div>
          <div className="lp-footer-bottom">
            <span>© {new Date().getFullYear()} EduIA — {t("landing.footer.rights")}</span>
            <button type="button" className="lp-footer-link" onClick={onLegal}>{t("legal.link")}</button>
            <span>{t("landing.footer.tagline")}</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
