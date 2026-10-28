/** Accès tolérant au localStorage (indisponible en navigation privée stricte, quota, politique du navigateur). */

export function readPref(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch (error) {
    console.warn(`[storage] Lecture impossible de « ${key} ».`, error);
    return null;
  }
}

export function writePref(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch (error) {
    console.warn(`[storage] Écriture impossible de « ${key} ».`, error);
  }
}
