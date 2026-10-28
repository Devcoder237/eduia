import { useRef, useState } from "react";
import type { FormEvent } from "react";
import { useT } from "../i18n";
import { Alert, Button, TextField } from "../components/ui";
import { BrandMark } from "../components/Brand";
import { LangSwitch, ThemeSwitch } from "../components/Switches";
import { ApiError, authApi, errorMessage } from "../services";
import { passwordProblem } from "../utils/validation";

interface ResetPasswordPageProps {
  /** Jeton lu dans l'adresse (`#/reset?token=…`) ; vide si le lien est incomplet. */
  token: string;
  onDone: () => void;
  onRequestNew: () => void;
}

/** Écran ouvert depuis le lien reçu par e-mail : choix d'un nouveau mot de passe. */
export default function ResetPasswordPage({ token, onDone, onRequestNew }: ResetPasswordPageProps) {
  const { t } = useT();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(false);
  const submitting = useRef(false);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submitting.current) return;
    setError(null);
    const problems: Record<string, string> = {};
    const pwdKey = passwordProblem(password);
    if (pwdKey) problems.password = t(pwdKey);
    if (confirm !== password) problems.confirm = t("reset.mismatch");
    setFields(problems);
    if (Object.keys(problems).length > 0) return;
    submitting.current = true;
    setLoading(true);
    try {
      await authApi.resetPassword({ token, new_password: password });
      setDone(true);
    } catch (e) {
      if (e instanceof ApiError && e.status === 400) setExpired(true);
      else if (e instanceof ApiError && e.fields) setFields(e.fields);
      setError(errorMessage(e));
    } finally {
      submitting.current = false;
      setLoading(false);
    }
  };

  const invalidLink = token.length < 10 || expired;

  return (
    <div className="auth">
      <div className="auth__tools"><LangSwitch /><ThemeSwitch /></div>
      <main className="auth__box" id="main">
        <div className="auth__brand">
          <BrandMark size={60} />
          <h1 className="auth__title">EduIA</h1>
        </div>
        <h2 className="auth__subtitle">{t("reset.title")}</h2>

        {done ? (
          <div className="auth__form">
            <Alert tone="success">{t("reset.done")}</Alert>
            <Button size="lg" fullWidth onClick={onDone}>{t("forgot.backToLogin")} →</Button>
          </div>
        ) : invalidLink ? (
          <div className="auth__form">
            <Alert>{error ?? t("reset.invalid")}</Alert>
            <Button size="lg" fullWidth onClick={onRequestNew}>{t("reset.requestNew")}</Button>
          </div>
        ) : (
          <form className="auth__form" onSubmit={(e) => void onSubmit(e)} noValidate aria-label={t("reset.title")}>
            <p className="muted">{t("reset.intro")}</p>
            <TextField label={t("reset.newPassword")} type="password" value={password} onChange={setPassword} autoComplete="new-password" required error={fields.password ?? fields.new_password} hint={t("auth.passwordHint")} />
            <TextField label={t("reset.confirm")} type="password" value={confirm} onChange={setConfirm} autoComplete="new-password" required error={fields.confirm} />
            {error && <Alert>{error}</Alert>}
            <Button type="submit" size="lg" fullWidth loading={loading}>
              {loading ? t("auth.pending") : `${t("reset.submit")} →`}
            </Button>
          </form>
        )}
      </main>
    </div>
  );
}
