import { useSyncExternalStore } from "react";

/**
 * Verrou du sélecteur de langue pendant un examen blanc : les questions sont générées une à une,
 * changer de langue en cours d'épreuve mélangerait les deux langues. Le verrou est levé à la fin.
 */
let locked = false;
const listeners = new Set<() => void>();

export function setLangLocked(value: boolean): void {
  if (locked === value) return;
  locked = value;
  listeners.forEach((notify) => notify());
}

export function isLangLocked(): boolean {
  return locked;
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Vrai tant que la langue ne doit pas être changée. */
export function useLangLocked(): boolean {
  return useSyncExternalStore(subscribe, isLangLocked, isLangLocked);
}
