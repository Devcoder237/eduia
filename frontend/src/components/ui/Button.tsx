import type { ReactNode } from "react";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

export interface ButtonProps {
  children: ReactNode;
  onClick?: (() => void) | undefined;
  type?: "button" | "submit";
  variant?: ButtonVariant;
  size?: "md" | "lg" | "sm";
  disabled?: boolean;
  /** Affiche un indicateur et bloque le clic (l'accessibilité est assurée par `aria-busy`). */
  loading?: boolean;
  fullWidth?: boolean;
  /** Libellé accessible quand le contenu est une icône seule. */
  ariaLabel?: string;
  /** Fond personnalisé (ex. couleur d'une matière : texte blanc, contraste >= 4,5:1). */
  accent?: string;
  pressed?: boolean;
  title?: string;
}

/** Bouton accessible : cible tactile >= 44 px, état de chargement, focus visible. */
export function Button({
  children,
  onClick,
  type = "button",
  variant = "primary",
  size = "md",
  disabled = false,
  loading = false,
  fullWidth = false,
  ariaLabel,
  accent,
  pressed,
  title,
}: ButtonProps) {
  const className = ["ui-btn", `ui-btn--${variant}`, `ui-btn--${size}`, fullWidth ? "ui-btn--full" : ""].join(" ").trim();
  const style = accent && variant === "primary" ? { background: accent, color: "#FFFFFF" } : undefined;
  return (
    <button
      type={type}
      className={className}
      style={style}
      onClick={onClick}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      aria-label={ariaLabel}
      aria-pressed={pressed}
      title={title}
    >
      {loading && <span className="ui-spinner ui-spinner--inline" aria-hidden="true" />}
      {children}
    </button>
  );
}
