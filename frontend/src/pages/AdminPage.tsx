import { useT } from "../i18n";
import { useAdminStats } from "../hooks/useAdminStats";
import { Alert, Card, EmptyState, PageHeader, Skeleton } from "../components/ui";
import { getLevel, getSubject } from "../theme";

function Bar({ label, count, max, color }: { label: string; count: number; max: number; color: string }) {
  const pct = max > 0 ? Math.max(4, Math.round((count / max) * 100)) : 0;
  return (
    <li className="bar">
      <span className="bar__label">{label}</span>
      <span className="bar__track" aria-hidden="true"><span className="bar__fill" style={{ width: `${pct}%`, background: color }} /></span>
      <strong className="bar__value">{count}</strong>
    </li>
  );
}

export default function AdminPage() {
  const { t } = useT();
  const stats = useAdminStats();
  if (stats.loading) return <div className="page"><PageHeader title={t("admin.title")} /><Skeleton lines={5} /></div>;
  const s = stats.data;
  if (stats.error || !s) {
    return <div className="page"><EmptyState icon="🔒" title={t("admin.denied")}><Alert onRetry={stats.reload}>{stats.error ?? t("admin.deniedText")}</Alert></EmptyState></div>;
  }

  const maxSubject = Math.max(1, ...s.subject_popularity.map((x) => x.count));
  const maxLevel = Math.max(1, ...s.level_distribution.map((x) => x.count));
  const maxSignup = Math.max(1, ...s.signups_by_day.map((x) => x.count));
  const kpis = [
    { label: t("admin.users"), value: s.total_users, icon: "👥" },
    { label: t("admin.active"), value: s.active_users_7d, icon: "🟢" },
    { label: t("admin.sessions"), value: s.total_sessions, icon: "💬" },
    { label: t("admin.messages"), value: s.total_messages, icon: "✉️" },
    { label: t("admin.exercises"), value: s.total_exercises, icon: "✏️" },
    { label: t("admin.quizzes"), value: s.total_quiz_attempts, icon: "🎯" },
  ];

  return (
    <div className="page">
      <PageHeader title={t("admin.title")} subtitle={t("admin.subtitle")} />
      <div className="tiles">
        {kpis.map((k) => <div key={k.label} className="tile"><span aria-hidden="true">{k.icon}</span><strong>{k.value}</strong><span>{k.label}</span></div>)}
      </div>
      <div className="grid-2">
        <Card title={`📐 ${t("admin.popularSubjects")}`}>
          {s.subject_popularity.length === 0 ? <p className="muted">{t("admin.noData")}</p> : (
            <ul className="bars">{s.subject_popularity.map((x) => <Bar key={x.subject} label={`${getSubject(x.subject).icon} ${t(getSubject(x.subject).labelKey)}`} count={x.count} max={maxSubject} color={getSubject(x.subject).color} />)}</ul>
          )}
        </Card>
        <Card title={`🎓 ${t("admin.levels")}`}>
          {s.level_distribution.length === 0 ? <p className="muted">{t("admin.noData")}</p> : (
            <ul className="bars">{s.level_distribution.map((x) => <Bar key={x.level} label={`${getLevel(x.level).icon} ${t(getLevel(x.level).labelKey)}`} count={x.count} max={maxLevel} color={getLevel(x.level).color} />)}</ul>
          )}
        </Card>
      </div>
      <Card title={`📈 ${t("admin.signups")}`}>
        <div className="spark" role="img" aria-label={t("admin.signupsAlt", { n: s.signups_by_day.reduce((a, d) => a + d.count, 0) })}>
          {s.signups_by_day.map((d) => <span key={d.date} className="spark__bar" title={`${d.date}: ${d.count}`} style={{ height: `${Math.max(4, (d.count / maxSignup) * 100)}%`, opacity: d.count > 0 ? 1 : 0.25 }} />)}
        </div>
        <p className="rubric__row muted"><span>{s.signups_by_day[0]?.date}</span><span>{s.signups_by_day.at(-1)?.date}</span></p>
      </Card>
    </div>
  );
}
