import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { useT } from "../../i18n";

export interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  /** `bottom` = feuille montante (mobile) ; `left` = tiroir latéral. */
  side?: "left" | "bottom";
}

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Tiroir modal accessible : rôle dialog, Échap pour fermer, piégeage du focus,
 * restitution du focus à l'élément déclencheur, défilement de l'arrière-plan bloqué.
 */
export function Drawer({ open, onClose, title, children, side = "left" }: DrawerProps) {
  const { t } = useT();
  const panelRef = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!open) return undefined;
    const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const panel = panelRef.current;
    const first = panel?.querySelector<HTMLElement>(FOCUSABLE);
    (first ?? panel)?.focus();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab" || !panel) return;
      const items = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (items.length === 0) return;
      const firstItem = items[0];
      const lastItem = items[items.length - 1];
      if (!firstItem || !lastItem) return;
      if (event.shiftKey && document.activeElement === firstItem) {
        event.preventDefault();
        lastItem.focus();
      } else if (!event.shiftKey && document.activeElement === lastItem) {
        event.preventDefault();
        firstItem.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previousOverflow;
      previouslyFocused?.focus();
    };
  }, [open]);

  if (!open) return null;
  return (
    <div className="ui-drawer-root">
      <div className="ui-drawer-backdrop" onClick={onClose} aria-hidden="true" />
      <div ref={panelRef} className={`ui-drawer ui-drawer--${side}`} role="dialog" aria-modal="true" aria-label={title} tabIndex={-1}>
        <div className="ui-drawer__head">
          <h2 className="ui-drawer__title">{title}</h2>
          <button type="button" className="ui-iconbtn" onClick={onClose} aria-label={t("common.close")}>✕</button>
        </div>
        <div className="ui-drawer__body">{children}</div>
      </div>
    </div>
  );
}
