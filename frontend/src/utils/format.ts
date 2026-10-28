/** Formatage de dates, durées et pourcentages (toujours dans la langue active). */

export function formatTime(iso: string, locale: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
}

export function formatDate(iso: string, locale: string, options?: Intl.DateTimeFormatOptions): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString(locale, options ?? { day: "numeric", month: "short", year: "numeric" });
}

export function formatDateTime(iso: string, locale: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString(locale, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

/** 0.734 → « 73 % » (valeur bornée à 0–100). */
export function percent(ratio: number): string {
  const bounded = Math.min(1, Math.max(0, Number.isFinite(ratio) ? ratio : 0));
  return `${Math.round(bounded * 100)} %`;
}

/** 754 → « 12:34 ». */
export function formatClock(totalSeconds: number): string {
  const safe = Math.max(0, Math.floor(totalSeconds));
  const minutes = Math.floor(safe / 60);
  const seconds = safe % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

/** Identifiant d'idempotence : généré une fois par action de l'utilisateur. */
export function newRequestId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

/** Date « calendaire » (AAAA-MM-JJ) sans décalage de fuseau horaire. */
export function formatDateOnly(dateOnly: string, locale: string): string {
  const date = new Date(`${dateOnly.slice(0, 10)}T12:00:00`);
  if (Number.isNaN(date.getTime())) return dateOnly;
  return date.toLocaleDateString(locale, { day: "2-digit", month: "short" });
}

/** Nombre de jours (calendaires, heure locale) entre aujourd'hui et la date donnée. */
export function daysUntil(iso: string, now: Date = new Date()): number {
  const target = new Date(iso);
  if (Number.isNaN(target.getTime())) return 0;
  const a = new Date(target.getFullYear(), target.getMonth(), target.getDate()).getTime();
  const b = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  return Math.round((a - b) / 86_400_000);
}

/** Date locale du jour au format AAAA-MM-JJ, décalée de `offsetDays`. */
export function localIsoDate(offsetDays = 0, now: Date = new Date()): string {
  const d = new Date(now.getFullYear(), now.getMonth(), now.getDate() + offsetDays);
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}
