import { useState } from "react";
import { useT } from "../i18n";
import { useAuth } from "../context/AuthContext";
import { useJoinedClassrooms } from "../hooks/useClassrooms";
import { Alert, Button, Card, Drawer, PageHeader, Skeleton, TextField } from "../components/ui";
import { LangSwitch, ThemeSwitch } from "../components/Switches";
import { authApi, classroomApi, errorMessage } from "../services";
import { passwordProblem } from "../utils/validation";
import { formatDate } from "../utils/format";
import type { Page } from "../lib/router";

type Msg = { tone: "success" | "error"; text: string } | null;

export default function SettingsPage({ onNavigate }: { onNavigate: (page: Page) => void }) {
  const { t, locale } = useT();
  const { user, endSession, logout } = useAuth();
  const joined = useJoinedClassrooms();

  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [pwdMsg, setPwdMsg] = useState<Msg>(null);
  const [saving, setSaving] = useState(false);

  const [code, setCode] = useState("");
  const [joinMsg, setJoinMsg] = useState<Msg>(null);
  const [joining, setJoining] = useState(false);

  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deletePwd, setDeletePwd] = useState("");
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [logoutAllError, setLogoutAllError] = useState<string | null>(null);

  const changePassword = async () => {
    setPwdMsg(null);
    if (!current || !next) { setPwdMsg({ tone: "error", text: t("settings.fillAll") }); return; }
    const problem = passwordProblem(next);
    if (problem) { setPwdMsg({ tone: "error", text: t(problem) }); return; }
    if (next !== confirm) { setPwdMsg({ tone: "error", text: t("settings.mismatch") }); return; }
    setSaving(true);
    try {
      await authApi.changePassword({ current_password: current, new_password: next });
      setPwdMsg({ tone: "success", text: t("settings.passwordChanged") });
      setCurrent(""); setNext(""); setConfirm("");
    } catch (e) {
      setPwdMsg({ tone: "error", text: errorMessage(e) });
    } finally {
      setSaving(false);
    }
  };

  const join = async () => {
    setJoinMsg(null);
    if (code.trim().length < 4) { setJoinMsg({ tone: "error", text: t("settings.codeInvalid") }); return; }
    setJoining(true);
    try {
      const res = await classroomApi.join(code.trim().toUpperCase());
      setJoinMsg({ tone: "success", text: res.already_member ? t("settings.alreadyMember", { name: res.classroom_name }) : t("settings.joinedOk", { name: res.classroom_name }) });
      setCode("");
      joined.reload();
    } catch (e) {
      setJoinMsg({ tone: "error", text: errorMessage(e, t("settings.codeInvalid")) });
    } finally {
      setJoining(false);
    }
  };

  const leave = async (id: string) => {
    try {
      await classroomApi.leave(id);
      joined.reload();
    } catch (e) {
      setJoinMsg({ tone: "error", text: errorMessage(e) });
    }
  };

  const logoutEverywhere = async () => {
    setLogoutAllError(null);
    try {
      await authApi.logoutAll();
      endSession();
    } catch (e) {
      setLogoutAllError(errorMessage(e));
    }
  };

  const deleteAccount = async () => {
    setDeleting(true);
    setDeleteError(null);
    try {
      await authApi.deleteAccount(deletePwd);
      endSession();
      onNavigate("landing");
    } catch (e) {
      setDeleteError(errorMessage(e));
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="page page--narrow">
      <PageHeader title={t("settings.title")} subtitle={t("settings.subtitle")} />

      <Card title={`👤 ${t("settings.account")}`}>
        {user ? (
          <dl className="dl">
            <div><dt>{t("settings.name")}</dt><dd>{user.full_name || "—"}</dd></div>
            <div><dt>{t("auth.username")}</dt><dd>{user.username}</dd></div>
            <div><dt>{t("auth.email")}</dt><dd>{user.email}</dd></div>
          </dl>
        ) : <Skeleton lines={3} />}
      </Card>

      <Card title={`🏫 ${t("settings.classes")}`}>
        <p className="muted">{t("settings.classesHint")}</p>
        <div className="inline-form">
          <TextField label={t("settings.inviteCode")} value={code} onChange={(v) => setCode(v.toUpperCase())} maxLength={8} placeholder="ABC123" autoComplete="off" />
          <Button loading={joining} onClick={() => void join()}>{t("settings.join")}</Button>
        </div>
        {joinMsg && <Alert tone={joinMsg.tone}>{joinMsg.text}</Alert>}
        {joined.loading && <Skeleton lines={1} />}
        {(joined.data ?? []).length > 0 && (
          <ul className="stack">
            {(joined.data ?? []).map((c) => (
              <li key={c.id} className="recap">
                <span className="recap__q"><strong>{c.name}</strong> <span className="muted">· {t("settings.since", { date: formatDate(c.joined_at, locale) })}</span></span>
                <Button size="sm" variant="secondary" onClick={() => void leave(c.id)}>{t("settings.leave")}</Button>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title={`🔒 ${t("settings.password")}`}>
        <TextField label={t("settings.currentPassword")} type="password" value={current} onChange={setCurrent} autoComplete="current-password" />
        <TextField label={t("settings.newPassword")} type="password" value={next} onChange={setNext} autoComplete="new-password" hint={t("auth.passwordHint")} />
        <TextField label={t("settings.confirmPassword")} type="password" value={confirm} onChange={setConfirm} autoComplete="new-password" />
        {pwdMsg && <Alert tone={pwdMsg.tone}>{pwdMsg.text}</Alert>}
        <Button loading={saving} onClick={() => void changePassword()}>{t("settings.update")}</Button>
      </Card>

      <Card title={`🎨 ${t("settings.appearance")}`}>
        <div className="rubric__row"><span>{t("settings.theme")}</span><ThemeSwitch /></div>
        <div className="rubric__row"><span>{t("settings.language")}</span><LangSwitch /></div>
      </Card>

      <Card title={`🚪 ${t("settings.session")}`}>
        {logoutAllError && <Alert>{logoutAllError}</Alert>}
        <div className="actions">
          <Button variant="secondary" onClick={logout}>{t("nav.logout")}</Button>
          <Button variant="secondary" onClick={() => void logoutEverywhere()}>{t("settings.logoutAll")}</Button>
        </div>
        <p className="muted">{t("settings.logoutAllHint")}</p>
      </Card>

      <Card title={`📄 ${t("legal.title")}`}>
        <Button variant="secondary" onClick={() => onNavigate("legal")}>{t("legal.link")}</Button>
      </Card>

      <Card title={`⚠️ ${t("settings.danger")}`} className="danger-zone">
        <p>{t("settings.deleteHint")}</p>
        <Button variant="danger" onClick={() => setDeleteOpen(true)}>{t("settings.delete")}</Button>
      </Card>

      <Drawer open={deleteOpen} onClose={() => setDeleteOpen(false)} title={t("settings.deleteTitle")} side="bottom">
        <p>{t("settings.deleteConfirm")}</p>
        <TextField label={t("settings.confirmWithPassword")} type="password" value={deletePwd} onChange={setDeletePwd} autoComplete="current-password" />
        {deleteError && <Alert>{deleteError}</Alert>}
        <div className="actions">
          <Button variant="danger" loading={deleting} disabled={!deletePwd} onClick={() => void deleteAccount()}>{t("settings.deleteForever")}</Button>
          <Button variant="ghost" onClick={() => setDeleteOpen(false)}>{t("common.cancel")}</Button>
        </div>
      </Drawer>
    </div>
  );
}
