import type { ReactNode } from "react";

export interface CardProps {
  children: ReactNode;
  /** Titre (rendu en h2 par défaut ; ajuster `as` pour respecter la hiérarchie). */
  title?: string;
  as?: "h2" | "h3";
  className?: string;
  /** Liseré coloré décoratif en haut de la carte. */
  accent?: string;
}

export function Card({ children, title, as = "h2", className = "", accent }: CardProps) {
  const Heading = as;
  return (
    <section className={`ui-card ${className}`.trim()} style={accent ? { borderTopColor: accent, borderTopWidth: 4 } : undefined}>
      {title && <Heading className="ui-card__title">{title}</Heading>}
      {children}
    </section>
  );
}
