import { useCallback, useEffect, useState } from "react";

/**
 * Routeur minimal basé sur le hash (`#/tutor?session=…`) : fonctionne sur n'importe quel
 * hébergement statique sans règle de réécriture, le bouton « précédent » du navigateur
 * fonctionne, et chaque écran a une adresse partageable.
 */

export const PAGES = [
  "landing", "login", "tutor", "exercise", "quiz", "exam", "progress",
  "history", "studyplans", "teacher", "admin", "settings", "legal", "reset",
] as const;
export type Page = (typeof PAGES)[number];

export const PUBLIC_PAGES: readonly Page[] = ["landing", "login", "legal", "reset"];

export interface Route {
  page: Page;
  params: Record<string, string>;
}

export function isPage(value: string): value is Page {
  return (PAGES as readonly string[]).includes(value);
}

export function parseHash(hash: string): Route {
  const raw = hash.replace(/^#\/?/, "");
  const [path = "", query = ""] = raw.split("?");
  const name = path.split("/")[0] ?? "";
  const params: Record<string, string> = {};
  new URLSearchParams(query).forEach((value, key) => {
    params[key] = value;
  });
  return { page: isPage(name) ? name : "landing", params };
}

export function toHash(page: Page, params?: Record<string, string>): string {
  const query = params && Object.keys(params).length > 0 ? `?${new URLSearchParams(params).toString()}` : "";
  return `#/${page}${query}`;
}

export function useRoute(): Route & { navigate: (page: Page, params?: Record<string, string>) => void; replace: (page: Page) => void } {
  const [route, setRoute] = useState<Route>(() => parseHash(window.location.hash));

  useEffect(() => {
    const onChange = () => setRoute(parseHash(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);

  const navigate = useCallback((page: Page, params?: Record<string, string>) => {
    window.location.hash = toHash(page, params);
    window.scrollTo(0, 0);
  }, []);

  const replace = useCallback((page: Page) => {
    window.history.replaceState(null, "", toHash(page));
    setRoute({ page, params: {} });
  }, []);

  return { ...route, navigate, replace };
}
