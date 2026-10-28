import { useT } from "../i18n";
import { BrandMark } from "./Brand";
import { Button } from "./ui";

/**
 * Écran d'attente « le serveur se réveille ». L'hébergement gratuit met l'API en veille après
 * 15 minutes sans trafic : le premier appel peut prendre ≈ 30 s. On l'explique honnêtement,
 * avec un compteur et une barre de progression (estimation sur 45 s), plutôt qu'un spinner muet.
 */
export function WakeScreen({ elapsedSec, down, onRetry }: { elapsedSec: number; down: boolean; onRetry: () => void }) {
  const { t } = useT();
  const progress = Math.min(0.95, elapsedSec / 45);
  return (
    <main className="wake" aria-live="polite">
      <div className="wake__card">
        <div className={down ? "" : "wake__pulse"}><BrandMark size={64} /></div>
        {down ? (
          <>
            <h1 className="wake__title">{t("wake.downTitle")}</h1>
            <p className="wake__text">{t("wake.downText")}</p>
            <Button onClick={onRetry} size="lg">{t("common.retry")}</Button>
          </>
        ) : (
          <>
            <h1 className="wake__title">{t("wake.title")}</h1>
            <p className="wake__text">{t("wake.text")}</p>
            <div className="ui-progress" role="progressbar" aria-label={t("wake.title")} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress * 100)}>
              <div className="ui-progress__bar" style={{ width: `${Math.round(progress * 100)}%` }} />
            </div>
            <p className="wake__meta">{t("wake.elapsed", { seconds: elapsedSec })}{elapsedSec > 40 ? ` · ${t("wake.almost")}` : ""}</p>
          </>
        )}
      </div>
    </main>
  );
}
