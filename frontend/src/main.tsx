import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/components.css";
import "katex/dist/katex.min.css";
import App from "./App";
import { I18nProvider } from "./i18n/I18nProvider";
import { initMonitoring } from "./lib/monitoring";
import { registerServiceWorker } from "./lib/pwa";

initMonitoring();

const container = document.getElementById("root");
if (!container) throw new Error("Élément #root introuvable dans index.html.");

createRoot(container).render(
  <StrictMode>
    <I18nProvider>
      <App />
    </I18nProvider>
  </StrictMode>,
);

registerServiceWorker();
