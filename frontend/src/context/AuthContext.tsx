import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  ApiError, LOGOUT_EVENT, authApi, hasTokens, isAbortError,
  type LoginInput, type RegisterInput, type UserOut,
} from "../services";

/** `loading` = vérification de la session ; `unavailable` = serveur injoignable au démarrage. */
export type AuthStatus = "loading" | "anonymous" | "authenticated" | "unavailable";

export interface AuthContextValue {
  status: AuthStatus;
  user: UserOut | null;
  /** Prénom (ou pseudo) pour les salutations. */
  firstName: string;
  login: (data: LoginInput) => Promise<void>;
  register: (data: RegisterInput) => Promise<void>;
  logout: () => void;
  /** Relit le profil (après un changement de rôle, par exemple). */
  reload: () => Promise<void>;
  /** Marque la session comme terminée (compte supprimé, tous appareils déconnectés). */
  endSession: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>(() => (hasTokens() ? "loading" : "anonymous"));
  const [user, setUser] = useState<UserOut | null>(null);
  const [attempt, setAttempt] = useState(0);

  // Vérification de la session au démarrage (le client HTTP rafraîchit le jeton tout seul sur 401).
  useEffect(() => {
    if (!hasTokens()) {
      setStatus("anonymous");
      return undefined;
    }
    const controller = new AbortController();
    setStatus("loading");
    authApi
      .getMe(controller.signal)
      .then((me) => {
        setUser(me);
        setStatus("authenticated");
      })
      .catch((error: unknown) => {
        if (isAbortError(error)) return;
        if (error instanceof ApiError && error.status === 401) {
          setUser(null);
          setStatus("anonymous");
          return;
        }
        console.warn("[auth] Serveur injoignable au démarrage.", error);
        setStatus("unavailable");
      });
    return () => controller.abort();
  }, [attempt]);

  // Le client HTTP émet cet évènement quand le rafraîchissement du jeton échoue définitivement.
  useEffect(() => {
    const onLogout = () => {
      setUser(null);
      setStatus("anonymous");
    };
    window.addEventListener(LOGOUT_EVENT, onLogout);
    return () => window.removeEventListener(LOGOUT_EVENT, onLogout);
  }, []);

  const loadUser = useCallback(async () => {
    const me = await authApi.getMe();
    setUser(me);
    setStatus("authenticated");
  }, []);

  const login = useCallback(
    async (data: LoginInput) => {
      await authApi.login(data);
      await loadUser();
    },
    [loadUser],
  );

  const register = useCallback(
    async (data: RegisterInput) => {
      await authApi.register(data);
      await authApi.login({ email: data.email, password: data.password });
      await loadUser();
    },
    [loadUser],
  );

  const endSession = useCallback(() => {
    authApi.logout();
    setUser(null);
    setStatus("anonymous");
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      firstName: user?.full_name?.trim().split(/\s+/)[0] || user?.username || "",
      login,
      register,
      logout: endSession,
      reload: loadUser,
      endSession,
    }),
    [status, user, login, register, endSession, loadUser],
  );

  // `attempt` est exposé via un second hook pour relancer la vérification (écran « serveur indisponible »).
  return (
    <AuthContext.Provider value={value}>
      <RetryContext.Provider value={() => setAttempt((n) => n + 1)}>{children}</RetryContext.Provider>
    </AuthContext.Provider>
  );
}

const RetryContext = createContext<() => void>(() => undefined);

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth doit être utilisé à l'intérieur de <AuthProvider>.");
  return ctx;
}

/** Relance la vérification de session (bouton « Réessayer »). */
export function useRetryAuth(): () => void {
  return useContext(RetryContext);
}
