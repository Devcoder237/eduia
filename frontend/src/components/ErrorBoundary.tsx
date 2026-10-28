import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";
import { translate } from "../i18n";

interface State {
  failed: boolean;
}

/** Filet de sécurité : une erreur de rendu n'affiche jamais une page blanche. */
export class ErrorBoundary extends Component<{ children?: ReactNode }, State> {
  override state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  override componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("[ErrorBoundary] Erreur de rendu.", error, info.componentStack);
    window.dispatchEvent(new CustomEvent("eduia:render-error", { detail: error }));
  }

  override render(): ReactNode {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="fullscreen-msg" role="alert">
        <h1>{translate("error.boundaryTitle")}</h1>
        <p>{translate("error.boundaryText")}</p>
        <button type="button" className="ui-btn ui-btn--primary ui-btn--md" onClick={() => window.location.reload()}>
          {translate("error.reload")}
        </button>
      </div>
    );
  }
}
