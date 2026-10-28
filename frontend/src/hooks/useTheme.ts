import { useCallback, useEffect, useState } from "react";
import { readPref, writePref } from "../utils/storage";

export type Theme = "light" | "dark";
const THEME_KEY = "eduia_theme";

function initialTheme(): Theme {
  const stored = readPref(THEME_KEY);
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/** Thème clair/sombre : préférence enregistrée, sinon réglage du système. */
export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(initialTheme);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", theme === "dark" ? "#1E1C18" : "#FAF9F5");
  }, [theme]);

  const setTheme = useCallback((next: Theme) => {
    setThemeState(next);
    writePref(THEME_KEY, next);
  }, []);

  const toggle = useCallback(() => setTheme(theme === "light" ? "dark" : "light"), [theme, setTheme]);
  return { theme, setTheme, toggle };
}
