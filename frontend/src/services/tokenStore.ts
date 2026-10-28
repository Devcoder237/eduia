/**
 * Stockage des jetons d'authentification.
 * - Écriture « traversante » : mémoire + localStorage.
 * - Si le stockage est indisponible (navigation privée stricte, quota, politique du navigateur),
 *   on garde les jetons en mémoire pour la durée de l'onglet et on le journalise.
 */

const ACCESS_KEY = "eduia_token";
const REFRESH_KEY = "eduia_refresh_token";

let memoryAccess: string | null = null;
let memoryRefresh: string | null = null;

function readStorage(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch (error) {
    console.warn(`[tokenStore] Lecture impossible de « ${key} » (stockage indisponible).`, error);
    return null;
  }
}

function writeStorage(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch (error) {
    console.warn(`[tokenStore] Écriture impossible de « ${key} » : jeton conservé en mémoire seulement.`, error);
  }
}

function removeStorage(key: string): void {
  try {
    window.localStorage.removeItem(key);
  } catch (error) {
    console.warn(`[tokenStore] Suppression impossible de « ${key} ».`, error);
  }
}

export function getAccessToken(): string | null {
  return memoryAccess ?? readStorage(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  return memoryRefresh ?? readStorage(REFRESH_KEY);
}

export function setTokens(access: string, refresh: string): void {
  memoryAccess = access;
  memoryRefresh = refresh;
  writeStorage(ACCESS_KEY, access);
  writeStorage(REFRESH_KEY, refresh);
}

export function clearTokens(): void {
  memoryAccess = null;
  memoryRefresh = null;
  removeStorage(ACCESS_KEY);
  removeStorage(REFRESH_KEY);
}

export function hasTokens(): boolean {
  return getAccessToken() !== null || getRefreshToken() !== null;
}
