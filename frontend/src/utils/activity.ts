import type { Page } from "../lib/router";

/** Modules suivis (identiques à ceux acceptés par le serveur). */
export type ActivityModule = "tutor" | "quiz" | "exercise" | "exam" | "other";

/** Un signal est envoyé toutes les 30 s d'activité réelle. */
export const BEAT_EVERY_S = 30;
/** Sans clic, frappe, toucher ni défilement pendant 60 s, l'élève est considéré inactif. */
export const IDLE_LIMIT_MS = 60_000;
/** Maximum accepté par le serveur pour un seul signal. */
export const MAX_BEAT_S = 60;

const MODULE_BY_PAGE: Partial<Record<Page, ActivityModule>> = {
  tutor: "tutor",
  quiz: "quiz",
  exercise: "exercise",
  exam: "exam",
  progress: "other",
  history: "other",
  studyplans: "other",
  settings: "other",
  teacher: "other",
  admin: "other",
};

/** Module compté pour une page ; `null` pour les pages publiques (rien n'est mesuré). */
export function moduleForPage(page: Page): ActivityModule | null {
  return MODULE_BY_PAGE[page] ?? null;
}

/**
 * Compte les secondes réellement actives : onglet visible ET interaction récente.
 * Le temps passé onglet caché, ou sans aucune interaction depuis plus d'une minute, n'est pas compté.
 */
export class ActiveTimeCounter {
  private pending = 0;

  /** À appeler chaque seconde. Renvoie `true` quand assez de temps s'est accumulé pour un signal. */
  tick(visible: boolean, sinceInteractionMs: number): boolean {
    if (visible && sinceInteractionMs < IDLE_LIMIT_MS) this.pending += 1;
    return this.pending >= BEAT_EVERY_S;
  }

  /** Retire (et renvoie) les secondes à envoyer, au plus `MAX_BEAT_S`. */
  take(): number {
    const seconds = Math.min(this.pending, MAX_BEAT_S);
    this.pending -= seconds;
    return seconds;
  }

  /** Remet des secondes non envoyées (échec réseau) sans dépasser le plafond d'un signal. */
  restore(seconds: number): void {
    this.pending = Math.min(this.pending + seconds, MAX_BEAT_S);
  }
}