import type { TranslationKey } from "../i18n";

/** Règles identiques à celles du serveur (le serveur reste l'autorité ; ceci n'évite que des allers-retours). */
export const PASSWORD_MIN = 8;
export const PASSWORD_MAX_BYTES = 72;

export function passwordProblem(value: string): TranslationKey | null {
  if (value.length < PASSWORD_MIN) return "validation.passwordShort";
  if (new TextEncoder().encode(value).length > PASSWORD_MAX_BYTES) return "validation.passwordLong";
  if (!/\p{Lu}/u.test(value)) return "validation.passwordUpper";
  if (!/\d/.test(value)) return "validation.passwordDigit";
  return null;
}

const USERNAME_RE = /^[A-Za-z0-9_.-]+$/;

export function usernameProblem(value: string): TranslationKey | null {
  if (value.length < 3 || value.length > 50) return "validation.usernameLength";
  if (!USERNAME_RE.test(value)) return "validation.usernameChars";
  return null;
}

export function emailProblem(value: string): TranslationKey | null {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim()) ? null : "validation.email";
}
