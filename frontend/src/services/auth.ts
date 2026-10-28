import { AI_TIMEOUT_MS, request, requestVoid } from "./http";
import { clearTokens, hasTokens, setTokens } from "./tokenStore";

export interface UserOut {
  id: string;
  email: string;
  username: string;
  full_name: string | null;
  is_active: boolean;
  created_at: string;
  is_admin: boolean;
  is_teacher: boolean;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface RegisterInput {
  email: string;
  username: string;
  password: string;
  full_name?: string;
}

export interface LoginInput {
  email: string;
  password: string;
}

export interface PasswordChangedResponse {
  status: string;
  tokens: TokenResponse;
}

export interface ChangePasswordInput {
  current_password: string;
  new_password: string;
}

export interface StatusResponse {
  status: string;
}

export interface ResetPasswordInput {
  token: string;
  new_password: string;
}

export const authApi = {
  /** Demande un lien de réinitialisation. La réponse est identique que le compte existe ou non. */
  forgotPassword: (email: string, signal?: AbortSignal) =>
    request<StatusResponse>("/auth/forgot-password", {
      method: "POST",
      body: { email },
      auth: false,
      timeoutMs: AI_TIMEOUT_MS,
      ...(signal ? { signal } : {}),
    }),

  /** Définit un nouveau mot de passe grâce au lien reçu par e-mail (usage unique). */
  resetPassword: (data: ResetPasswordInput, signal?: AbortSignal) =>
    request<StatusResponse>("/auth/reset-password", { method: "POST", body: data, auth: false, ...(signal ? { signal } : {}) }),

  register: (data: RegisterInput, signal?: AbortSignal) =>
    request<UserOut>("/auth/register", { method: "POST", body: data, auth: false, ...(signal ? { signal } : {}) }),

  /** Connecte l'utilisateur et enregistre les deux jetons. */
  login: async (data: LoginInput, signal?: AbortSignal): Promise<TokenResponse> => {
    const result = await request<TokenResponse>("/auth/login", {
      method: "POST",
      body: data,
      auth: false,
      timeoutMs: AI_TIMEOUT_MS, // premier appel possible sur un serveur qui se réveille
      ...(signal ? { signal } : {}),
    });
    setTokens(result.access_token, result.refresh_token);
    return result;
  },

  getMe: (signal?: AbortSignal) => request<UserOut>("/auth/me", signal ? { signal } : {}),

  /** Change le mot de passe : les anciens jetons sont révoqués, les nouveaux sont enregistrés. */
  changePassword: async (data: ChangePasswordInput): Promise<void> => {
    const result = await request<PasswordChangedResponse>("/auth/password", { method: "PUT", body: data });
    setTokens(result.tokens.access_token, result.tokens.refresh_token);
  },

  /** Révoque tous les jetons de l'utilisateur (tous appareils), puis purge le stockage local. */
  logoutAll: async (): Promise<void> => {
    try {
      await requestVoid("/auth/logout-all", { method: "POST" });
    } finally {
      clearTokens();
    }
  },

  /** Suppression définitive du compte et de toutes les données (confirmée par le mot de passe). */
  deleteAccount: async (password: string): Promise<void> => {
    await requestVoid("/auth/me", { method: "DELETE", body: { password } });
    clearTokens();
  },

  /** Déconnexion locale : purge des jetons. */
  logout: (): void => clearTokens(),

  isAuthenticated: (): boolean => hasTokens(),
};
