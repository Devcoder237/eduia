import type { ReactNode } from "react";
import { useT } from "../../i18n";

export type AlertTone = "error" | "success" | "warning" | "info";

export function Alert({ tone = "error", children, onRetry }: { tone?: AlertTone; children: ReactNode; onRetry?: (() => void) | undefined }) {
  const { t } = useT();
  const icon = tone === "error" ? "⚠️" : tone === "success" ? "✅" : tone === "warning" ? "💡" : "ℹ️";
  return (
    <div className={`ui-alert ui-alert--${tone}`} role={tone === "error" ? "alert" : "status"}>
      <span aria-hidden="true">{icon}</span>
      <div className="ui-alert__body">{children}</div>
      {onRetry && (
        <button type="button" className="ui-alert__retry" onClick={onRetry}>
          {t("common.retry")}
        </button>
      )}
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  const { t } = useT();
  return (
    <div className="ui-loading" role="status" aria-live="polite">
      <span className="ui-spinner" aria-hidden="true" />
      <span>{label ?? t("common.loading")}</span>
    </div>
  );
}

export function Skeleton({ lines = 3 }: { lines?: number }) {
  const { t } = useT();
  return (
    <div className="ui-skeleton" role="status" aria-label={t("common.loading")}>
      {Array.from({ length: lines }, (_, i) => (
        <span key={i} className="ui-skeleton__line" style={{ width: `${92 - ((i * 17) % 40)}%` }} />
      ))}
    </div>
  );
}

export function EmptyState({ icon, title, children }: { icon: string; title: string; children?: ReactNode }) {
  return (
    <div className="ui-empty">
      <div className="ui-empty__icon" aria-hidden="true">{icon}</div>
      <h2 className="ui-empty__title">{title}</h2>
      {children && <div className="ui-empty__text">{children}</div>}
    </div>
  );
}

export function ProgressBar({ value, label, color }: { value: number; label: string; color?: string | undefined }) {
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100);
  return (
    <div className="ui-progress" role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct}>
      <div className="ui-progress__bar" style={{ width: `${pct}%`, ...(color ? { background: color } : {}) }} />
    </div>
  );
}

export function Chip({ children, color }: { children: ReactNode; color?: string | undefined }) {
  return (
    <span className="ui-chip" style={color ? { background: color, color: "#FFFFFF", borderColor: color } : undefined}>
      {children}
    </span>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string | undefined; actions?: ReactNode }) {
  return (
    <header className="ui-pageheader">
      <div>
        <h1 className="ui-pageheader__title">{title}</h1>
        {subtitle && <p className="ui-pageheader__sub">{subtitle}</p>}
      </div>
      {actions && <div className="ui-pageheader__actions">{actions}</div>}
    </header>
  );
}
