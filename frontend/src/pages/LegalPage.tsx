import { useT, type TranslationKey } from "../i18n";
import { Button } from "../components/ui";
import { BrandMark } from "../components/Brand";
import { LangSwitch, ThemeSwitch } from "../components/Switches";

const SECTIONS: readonly { title: TranslationKey; body: TranslationKey }[] = [
  { title: "legal.s1.t", body: "legal.s1.b" },
  { title: "legal.s2.t", body: "legal.s2.b" },
  { title: "legal.s3.t", body: "legal.s3.b" },
  { title: "legal.s4.t", body: "legal.s4.b" },
  { title: "legal.s5.t", body: "legal.s5.b" },
  { title: "legal.s6.t", body: "legal.s6.b" },
  { title: "legal.s7.t", body: "legal.s7.b" },
  { title: "legal.s8.t", body: "legal.s8.b" },
];

/** Conditions d'utilisation et politique de confidentialité (accessible sans connexion). */
export default function LegalPage({ onBack }: { onBack: () => void }) {
  const { t } = useT();
  const contact = import.meta.env.VITE_CONTACT_EMAIL;
  return (
    <div className="legal">
      <header className="legal__bar">
        <Button variant="ghost" size="sm" onClick={onBack}>← {t("common.back")}</Button>
        <span className="legal__tools"><LangSwitch /><ThemeSwitch /></span>
      </header>
      <main id="main" className="page page--narrow">
        <div className="legal__brand"><BrandMark size={40} /><h1 className="ui-pageheader__title">{t("legal.title")}</h1></div>
        <p className="muted">{t("legal.updated")}</p>
        {SECTIONS.map((s) => (
          <section key={s.title} className="legal__section">
            <h2 className="sub">{t(s.title)}</h2>
            <p>{t(s.body)}</p>
          </section>
        ))}
        {contact ? <p className="muted">{t("legal.contact", { email: contact })}</p> : null}
      </main>
    </div>
  );
}
