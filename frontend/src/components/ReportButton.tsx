import { useState } from "react";
import { sendReport, type ReportReason } from "../services";
import { Alert, Button, Drawer, SelectField, TextArea } from "./ui";
import { useT } from "../i18n";

const REASONS: readonly ReportReason[] = ["wrong", "inappropriate", "confusing", "other"];

/** Bouton « Signaler » sous une réponse du tuteur : ouvre une feuille avec motif et commentaire. */
export function ReportButton({ excerpt }: { excerpt: string }) {
  const { t } = useT();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState<ReportReason>("wrong");
  const [comment, setComment] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "done" | "error">("idle");

  const close = () => {
    setOpen(false);
    if (state === "done") { setState("idle"); setComment(""); }
  };

  const submit = async () => {
    if (state === "sending") return;
    setState("sending");
    try {
      await sendReport({ reason, excerpt, comment });
      setState("done");
    } catch {
      setState("error");
    }
  };

  return (
    <>
      <button type="button" className="bubble__speak" onClick={() => setOpen(true)} aria-label={t("report.open")} title={t("report.open")}>
        <span aria-hidden="true">🚩</span>
      </button>
      <Drawer open={open} onClose={close} title={t("report.title")} side="bottom">
        {state === "done" ? (
          <>
            <Alert tone="success">{t("report.thanks")}</Alert>
            <Button onClick={close}>{t("common.close")}</Button>
          </>
        ) : (
          <>
            <p className="muted">{t("report.intro")}</p>
            <SelectField
              label={t("report.reason")}
              value={reason}
              onChange={(v) => setReason(REASONS.find((r) => r === v) ?? "other")}
              options={REASONS.map((r) => ({ value: r, label: t(`report.reason.${r}`) }))}
            />
            <TextArea label={t("report.comment")} value={comment} onChange={setComment} rows={3} maxLength={500} />
            {state === "error" && <Alert onRetry={() => void submit()}>{t("report.failed")}</Alert>}
            <Button onClick={() => void submit()} loading={state === "sending"}>{t("report.send")}</Button>
          </>
        )}
      </Drawer>
    </>
  );
}
