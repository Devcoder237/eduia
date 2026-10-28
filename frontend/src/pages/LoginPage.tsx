import { useRef, useState } from "react";
import type { FormEvent } from "react";
import { useT } from "../i18n";
import { useAuth } from "../context/AuthContext";
import { Alert, Button, TextField } from "../components/ui";
import { BrandMark } from "../components/Brand";
import { LangSwitch, ThemeSwitch } from "../components/Switches";
import { ApiError, authApi, errorMessage } from "../services";
import { emailProblem, passwordProblem, usernameProblem } from "../utils/validation";

type Mode = "login" | "register";

interface LoginPageProps {
  onHome: () => void;
  onLegal: () => void;
  initialMode?: Mode;
  /** Ouvre directement le formulaire « mot de passe oublié » (lien d'un jeton expiré). */
  initialForgot?: boolean;
}

export default function LoginPage({ onHome, onLegal, initialMode = "login", initialForgot = false }: LoginPageProps) {
  const { t } = useT();
  const auth = useAuth();
  const [mode, setMode] = useState<Mode>(initialMode);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [username, setUsername] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const submitting = useRef(false);
  const [forgot, setForgot] = useState(initialForgot);
  const [forgotSent, setForgotSent] = useState(false);

  const switchMode = (next: Mode) => {
    setMode(next);
    setError(null);
    setFields({});
  };

  const openForgot = () => {
    setForgot(true);
    setForgotSent(false);
    setError(null);
    setFields({});
  };

  const closeForgot = () => {
    setForgot(false);
    setForgotSent(false);
    setError(null);
    setFields({});
  };

  const onForgotSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submitting.current) return;
    setError(null);
    const emailKey = emailProblem(email);
    if (emailKey) {
      setFields({ email: t(emailKey) });
      return;
    }
    setFields({});
    submitting.current = true;
    setLoading(true);
    try {
      await authApi.forgotPassword(email.trim().toLowerCase());
      setForgotSent(true); // même écran que le compte existe ou non : on ne révèle rien
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      submitting.current = false;
      setLoading(false);
    }
  };

  const validate = (): Record<string, string> => {
    const problems: Record<string, string> = {};
    const emailKey = emailProblem(email);
    if (emailKey) problems.email = t(emailKey);
    if (mode === "register") {
      const userKey = usernameProblem(username);
      if (userKey) problems.username = t(userKey);
      const pwdKey = passwordProblem(password);
      if (pwdKey) problems.password = t(pwdKey);
    } else if (password === "") {
      problems.password = t("validation.required");
    }
    return problems;
  };

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submitting.current) return; // anti double-soumission
    setError(null);
    const problems = validate();
    setFields(problems);
    if (Object.keys(problems).length > 0) return;
    submitting.current = true;
    setLoading(true);
    try {
      if (mode === "login") await auth.login({ email: email.trim().toLowerCase(), password });
      else await auth.register({ email: email.trim().toLowerCase(), username: username.trim(), password, ...(fullName.trim() ? { full_name: fullName.trim() } : {}) });
    } catch (e) {
      if (e instanceof ApiError && e.fields) setFields(e.fields);
      setError(errorMessage(e));
    } finally {
      submitting.current = false;
      setLoading(false);
    }
  };

  return (
    <div className="auth">
      <div className="auth__tools"><LangSwitch /><ThemeSwitch /></div>
      <main className="auth__box" id="main">
        <button type="button" className="ui-btn ui-btn--ghost ui-btn--sm" onClick={onHome}>{t("auth.backHome")}</button>
        <div className="auth__brand">
          <BrandMark size={60} />
          <h1 className="auth__title">EduIA</h1>
          <p className="muted">{t("auth.tagline")}</p>
        </div>

        {forgot ? (
          <section aria-labelledby="forgot-title">
            <h2 id="forgot-title" className="auth__subtitle">{t("forgot.title")}</h2>
            {forgotSent ? (
              <div className="auth__form">
                <Alert tone="success">{t("forgot.sent")}</Alert>
                <p className="muted">{t("forgot.sentHelp")}</p>
                <Button size="lg" fullWidth onClick={closeForgot}>{t("forgot.backToLogin")}</Button>
              </div>
            ) : (
              <form className="auth__form" onSubmit={(e) => void onForgotSubmit(e)} noValidate aria-label={t("forgot.title")}>
                <p className="muted">{t("forgot.intro")}</p>
                <TextField label={t("auth.email")} type="email" value={email} onChange={setEmail} autoComplete="email" inputMode="email" required error={fields.email} placeholder="vous@exemple.com" />
                {error && <Alert>{error}</Alert>}
                <Button type="submit" size="lg" fullWidth loading={loading}>
                  {loading ? t("auth.pending") : `${t("forgot.send")} →`}
                </Button>
                {loading && <p className="muted" role="status">{t("auth.coldStartHint")}</p>}
                <button type="button" className="link-btn" onClick={closeForgot}>{t("forgot.backToLogin")}</button>
              </form>
            )}
          </section>
        ) : (
        <>
        <div className="seg seg--wide" role="tablist" aria-label={t("auth.modeLabel")}>
          {(["login", "register"] as const).map((m) => (
            <button key={m} type="button" role="tab" aria-selected={mode === m} className={`seg__btn${mode === m ? " is-active" : ""}`} onClick={() => switchMode(m)}>
              {m === "login" ? t("auth.login") : t("auth.register")}
            </button>
          ))}
        </div>

        <form className="auth__form" onSubmit={(e) => void onSubmit(e)} noValidate aria-label={mode === "login" ? t("auth.login") : t("auth.register")}>
          {mode === "register" && (
            <>
              <TextField label={t("auth.fullName")} value={fullName} onChange={setFullName} autoComplete="name" maxLength={100} placeholder={t("auth.fullNamePlaceholder")} />
              <TextField label={t("auth.username")} value={username} onChange={setUsername} autoComplete="username" maxLength={50} required error={fields.username} />
            </>
          )}
          <TextField label={t("auth.email")} type="email" value={email} onChange={setEmail} autoComplete="email" inputMode="email" required error={fields.email} placeholder="vous@exemple.com" />
          <TextField
            label={t("auth.password")}
            type="password"
            value={password}
            onChange={setPassword}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            required
            error={fields.password}
            hint={mode === "register" ? t("auth.passwordHint") : undefined}
          />
          {error && <Alert>{error}</Alert>}
          <Button type="submit" size="lg" fullWidth loading={loading}>
            {loading ? t("auth.pending") : mode === "login" ? `${t("auth.login")} →` : `${t("auth.createAccount")} →`}
          </Button>
          {loading && <p className="muted" role="status">{t("auth.coldStartHint")}</p>}
          {mode === "login" && <button type="button" className="link-btn" onClick={openForgot}>{t("forgot.link")}</button>}
        </form>
        </>
        )}
        <p className="muted auth__legal">
          {t("auth.legalNote")}{" "}
          <button type="button" className="link-btn" onClick={onLegal}>{t("legal.link")}</button>
        </p>
      </main>
    </div>
  );
}
