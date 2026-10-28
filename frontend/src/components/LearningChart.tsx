export type ChartPoint = { label: string; value: number; weight?: number };

/**
 * Graphique en ligne (SVG pur, pas de dépendance externe) générique :
 * une évolution de valeur (0-1) dans le temps, avec un poids optionnel par
 * point qui contrôle la taille du marqueur (ex: nombre de questions cette
 * semaine-là, ou juste 1 pour un point d'historique de maîtrise unitaire).
 * Réutilisé à la fois pour "progression hebdomadaire" et "évolution de la
 * maîtrise d'un concept" -- même logique de rendu, données différentes.
 */
export default function LearningChart({
  data, color = "var(--accent)", lastLabel, ariaLabel, emptyLabel,
}: { data: ChartPoint[]; color?: string; lastLabel: string; ariaLabel: string; emptyLabel: string }) {
  const W = 640, H = 200, PAD_L = 46, PAD_R = 14, PAD_T = 14, PAD_B = 28;
  const plotW = W - PAD_L - PAD_R;
  const plotH = H - PAD_T - PAD_B;

  const hasData = data.some(d => (d.weight ?? 1) > 0);
  const maxWeight = Math.max(1, ...data.map(d => d.weight ?? 1));

  const xFor = (i: number) => PAD_L + (data.length <= 1 ? plotW / 2 : (i / (data.length - 1)) * plotW);
  const yFor = (value: number) => PAD_T + plotH - value * plotH;

  const last = Math.max(0, data.length - 1);
  const linePoints = data.map((d, i) => `${xFor(i)},${yFor(d.value)}`).join(" ");
  const areaPoints = `${xFor(0)},${PAD_T + plotH} ${linePoints} ${xFor(last)},${PAD_T + plotH}`;

  const gridLines = [0, 0.25, 0.5, 0.75, 1];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }} role="img" aria-label={ariaLabel}>
      {gridLines.map(g => (
        <g key={g}>
          <line x1={PAD_L} x2={W - PAD_R} y1={yFor(g)} y2={yFor(g)} stroke="var(--line)" strokeWidth={1} strokeDasharray={g === 0 ? "" : "3,3"} />
          <text x={PAD_L - 8} y={yFor(g) + 3} textAnchor="end" fontSize={11} fill="var(--ink-soft)">{Math.round(g * 100)} %</text>
        </g>
      ))}

      {!hasData ? (
        <text x={W / 2} y={H / 2} textAnchor="middle" fontSize={13} fill="var(--ink-soft)">{emptyLabel}</text>
      ) : (
        <>
          <polygon points={areaPoints} fill={color} opacity={0.08} />
          <polyline points={linePoints} fill="none" stroke={color} strokeWidth={2.2} strokeLinejoin="round" strokeLinecap="round" />
          {data.map((d, i) => {
            const w = d.weight ?? 1;
            const r = w === 0 ? 0 : 2.5 + (w / maxWeight) * 4.5;
            return w === 0 ? null : (
              <g key={i}>
                <circle cx={xFor(i)} cy={yFor(d.value)} r={r} fill={color} stroke="var(--cream)" strokeWidth={1.5} />
                <title>{`${d.label} — ${Math.round(d.value * 100)}%`}</title>
              </g>
            );
          })}
        </>
      )}

      {data.map((d, i) => (
        (data.length <= 8 || i % Math.ceil(data.length / 8) === 0 || i === data.length - 1) && (
          <text key={i} x={xFor(i)} y={H - 8} textAnchor={i === last && data.length > 1 ? "end" : "middle"} fontSize={11} fill="var(--ink-soft)">
            {i === data.length - 1 ? lastLabel : d.label}
          </text>
        )
      ))}
    </svg>
  );
}
