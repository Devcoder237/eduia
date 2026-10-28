import { getLang, translate } from "../i18n";
import { clearTokens, getAccessToken, getRefreshToken, setTokens } from "./tokenStore";

/**
 * Origine du backend, sans slash final et sans `/api` (ex. https://eduia-api.onrender.com).
 * Vide = même origine (proxy de développement Vite, ou reverse-proxy en production).
 * Aucune valeur par défaut codée en dur : la configuration vient de `VITE_API_URL`.
 */
export function normalizeBase(raw: string | undefined): string {
  const value = (raw ?? "").trim();
  if (value === "") return "";
  return value.replace(/\/+$/, "").replace(/\/api$/, "").replace(/\/+$/, "");
}

export const API_BASE_URL: string = normalizeBase(import.meta.env.VITE_API_URL);

/** Délai par défaut (ms). */
export const DEFAULT_TIMEOUT_MS = 30_000;
/** Délai pour la génération IA, le streaming et l'envoi de fichiers (ms). */
export const AI_TIMEOUT_MS = 60_000;
/** Événement émis (sur `window`) quand la session n'est plus récupérable. */
export const LOGOUT_EVENT = "eduia:logout";

const MAX_RETRIES = 2;
const BASE_BACKOFF_MS = 500;
const RETRYABLE_STATUS: readonly number[] = [502, 503, 504];
const NO_REFRESH_PATHS: readonly string[] = ["/auth/login", "/auth/register", "/auth/refresh"];

/** Erreur renvoyée par l'API (ou par le réseau : `status === 0`). */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;
  readonly fields?: Record<string, string>;
  readonly retryAfter?: number;

  constructor(status: number, detail: string, extra: { fields?: Record<string, string>; retryAfter?: number } = {}) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    if (extra.fields !== undefined) this.fields = extra.fields;
    if (extra.retryAfter !== undefined) this.retryAfter = extra.retryAfter;
  }
}

/** Délai maximal dépassé (status 0). */
export class RequestTimeoutError extends ApiError {
  constructor() {
    super(0, translate("error.timeout"));
    this.name = "RequestTimeoutError";
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

/** Vrai si l'erreur provient d'une annulation volontaire (AbortController). */
export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

/** Message affichable à l'utilisateur pour n'importe quelle erreur. */
export function errorMessage(error: unknown, fallback?: string): string {
  if (error instanceof ApiError) return error.detail;
  if (error instanceof Error && error.message !== "") return error.message;
  return fallback ?? translate("error.generic");
}

export type QueryValue = string | number | boolean | null | undefined;

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  /** Paramètres de requête (toujours encodés via URLSearchParams). */
  query?: Record<string, QueryValue>;
  /** Corps JSON. */
  body?: unknown;
  /** Corps multipart (envoi de fichier). */
  formData?: FormData;
  /** POST/PUT idempotent : autorise les nouvelles tentatives. Les GET sont toujours rejouables. */
  retry?: boolean;
  /** Délai maximal en ms (défaut 30 s ; utiliser AI_TIMEOUT_MS pour l'IA, le streaming, l'upload). */
  timeoutMs?: number;
  /** Signal d'annulation de l'appelant. */
  signal?: AbortSignal;
  /** Faux = pas d'en-tête Authorization ni de rafraîchissement (login, register). */
  auth?: boolean;
}

export function buildQuery(query?: Record<string, QueryValue>): string {
  if (!query) return "";
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null) continue;
    params.set(key, String(value));
  }
  const text = params.toString();
  return text === "" ? "" : `?${text}`;
}

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException("Aborted", "AbortError"));
      return;
    }
    const timer = window.setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      window.clearTimeout(timer);
      reject(new DOMException("Aborted", "AbortError"));
    };
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

async function toApiError(response: Response): Promise<ApiError> {
  let detail = "";
  let fields: Record<string, string> | undefined;
  try {
    const body: unknown = await response.json();
    if (isRecord(body)) {
      if (typeof body.detail === "string") detail = body.detail;
      if (isRecord(body.fields)) {
        const collected: Record<string, string> = {};
        for (const [name, message] of Object.entries(body.fields)) {
          if (typeof message === "string") collected[name] = message;
        }
        if (Object.keys(collected).length > 0) fields = collected;
      }
    }
  } catch (error) {
    // Corps absent ou non JSON (ex. page d'erreur d'un proxy) : on retombe sur un message générique.
    console.warn("[http] Corps d'erreur illisible.", error);
  }
  if (detail === "") detail = translate("error.http", { status: response.status });
  const header = response.headers.get("Retry-After");
  const parsed = header === null ? NaN : Number.parseInt(header, 10);
  const extra: { fields?: Record<string, string>; retryAfter?: number } = {};
  if (fields) extra.fields = fields;
  if (Number.isFinite(parsed) && parsed >= 0) extra.retryAfter = parsed;
  return new ApiError(response.status, detail, extra);
}

interface Attempt {
  response: Response;
  /** Libère minuteur ET lien avec le signal de l'appelant (à appeler une fois la réponse entièrement consommée). */
  release: () => void;
  /** Arrête seulement le minuteur (flux SSE : l'annulation par l'appelant reste active). */
  clearTimer: () => void;
  /** Vrai si l'annulation provient du délai maximal. */
  timedOut: () => boolean;
}

/** Un seul aller-retour réseau avec délai maximal et annulation combinée. */
async function sendOnce(path: string, options: RequestOptions, token: string | null): Promise<Attempt> {
  const controller = new AbortController();
  let timedOut = false;
  const timer = window.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, options.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  const external = options.signal;
  const onExternalAbort = () => controller.abort();
  if (external) {
    if (external.aborted) controller.abort();
    else external.addEventListener("abort", onExternalAbort, { once: true });
  }
  const clearTimer = () => window.clearTimeout(timer);
  const release = () => {
    clearTimer();
    external?.removeEventListener("abort", onExternalAbort);
  };

  // La langue choisie voyage sur CHAQUE requête : le serveur génère contenus et erreurs dans cette langue.
  const headers: Record<string, string> = { Accept: "application/json", "Accept-Language": getLang() };
  let body: BodyInit | undefined;
  if (options.formData) {
    body = options.formData;
  } else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }
  if (token) headers.Authorization = `Bearer ${token}`;

  try {
    const init: RequestInit = { method: options.method ?? "GET", headers, signal: controller.signal };
    if (body !== undefined) init.body = body;
    const response = await fetch(`${API_BASE_URL}/api${path}${buildQuery(options.query)}`, init);
    return { response, release, clearTimer, timedOut: () => timedOut };
  } catch (error) {
    release();
    if (timedOut) throw new RequestTimeoutError();
    if (external?.aborted || isAbortError(error)) throw new DOMException("Aborted", "AbortError");
    throw new ApiError(0, translate("error.network"));
  }
}

interface RefreshPayload {
  access_token: string;
  refresh_token: string;
}

function isRefreshPayload(value: unknown): value is RefreshPayload {
  return isRecord(value) && typeof value.access_token === "string" && typeof value.refresh_token === "string";
}

type RefreshOutcome = "ok" | "invalid" | "unavailable";
let refreshInFlight: Promise<RefreshOutcome> | null = null;

async function performRefresh(): Promise<RefreshOutcome> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return "invalid";
  try {
    const attempt = await sendOnce("/auth/refresh", { method: "POST", body: { refresh_token: refreshToken }, auth: false }, null);
    try {
      if (!attempt.response.ok) {
        // 5xx / 429 : le serveur est momentanément indisponible, ce n'est pas la preuve que le jeton est mort.
        return attempt.response.status >= 500 || attempt.response.status === 429 ? "unavailable" : "invalid";
      }
      const payload: unknown = await attempt.response.json();
      if (!isRefreshPayload(payload)) return "invalid";
      setTokens(payload.access_token, payload.refresh_token);
      return "ok";
    } finally {
      attempt.release();
    }
  } catch (error) {
    console.warn("[http] Rafraîchissement du jeton impossible.", error);
    return "unavailable";
  }
}

/** Mutualise le rafraîchissement : N requêtes 401 simultanées ne déclenchent qu'un seul POST /auth/refresh. */
function refreshOnce(): Promise<RefreshOutcome> {
  if (!refreshInFlight) {
    refreshInFlight = performRefresh().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

function emitLogout(): void {
  clearTokens();
  window.dispatchEvent(new Event(LOGOUT_EVENT));
}

function canRetry(options: RequestOptions): boolean {
  return (options.method ?? "GET") === "GET" || options.retry === true;
}

/**
 * Exécute la requête (retries, intercepteur 401) et renvoie la réponse OK non consommée.
 * L'appelant DOIT appeler `release()` quand il a fini de lire le corps.
 */
async function execute(path: string, options: RequestOptions): Promise<Attempt> {
  const useAuth = options.auth !== false;
  const mayRefresh = useAuth && !NO_REFRESH_PATHS.includes(path);
  let refreshed = false;
  let retries = 0;

  for (;;) {
    let attempt: Attempt;
    try {
      attempt = await sendOnce(path, options, useAuth ? getAccessToken() : null);
    } catch (error) {
      if (isApiError(error) && error.status === 0 && canRetry(options) && !(error instanceof RequestTimeoutError) && retries < MAX_RETRIES) {
        await sleep(BASE_BACKOFF_MS * 2 ** retries, options.signal);
        retries += 1;
        continue;
      }
      throw error;
    }

    const { response } = attempt;
    if (response.ok) return attempt;

    if (response.status === 401 && mayRefresh && !refreshed) {
      attempt.release();
      refreshed = true;
      const outcome = await refreshOnce();
      if (outcome === "ok") continue;
      if (outcome === "invalid") {
        emitLogout();
        throw new ApiError(401, translate("error.sessionExpired"));
      }
      throw new ApiError(401, translate("error.network"));
    }

    if (RETRYABLE_STATUS.includes(response.status) && canRetry(options) && retries < MAX_RETRIES) {
      attempt.release();
      await sleep(BASE_BACKOFF_MS * 2 ** retries, options.signal);
      retries += 1;
      continue;
    }

    const error = await toApiError(response);
    attempt.release();
    throw error;
  }
}

/** Appel JSON typé. La forme de la réponse est celle déclarée par le contrat API (frontière de confiance unique). */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const attempt = await execute(path, options);
  try {
    const data: unknown = await attempt.response.json();
    return data as T;
  } catch (error) {
    if (attempt.timedOut()) throw new RequestTimeoutError();
    if (isAbortError(error) || options.signal?.aborted) throw new DOMException("Aborted", "AbortError");
    throw new ApiError(attempt.response.status, translate("error.badResponse"));
  } finally {
    attempt.release();
  }
}

/** Appel sans corps de réponse exploitable (204, ou réponse ignorée). */
export async function requestVoid(path: string, options: RequestOptions = {}): Promise<void> {
  const attempt = await execute(path, options);
  try {
    if (attempt.response.status !== 204) await attempt.response.arrayBuffer();
  } finally {
    attempt.release();
  }
}

/**
 * Ouvre une réponse en flux (SSE). Le délai maximal ne couvre que l'obtention des en-têtes ;
 * ensuite seul le signal de l'appelant peut interrompre la lecture. Lève ApiError si !ok.
 */
export async function requestStream(path: string, options: RequestOptions): Promise<Response> {
  const attempt = await execute(path, options);
  attempt.clearTimer();
  return attempt.response;
}
