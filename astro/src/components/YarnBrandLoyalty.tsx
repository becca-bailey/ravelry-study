"use client";

import { useMemo, useState } from "react";
import { AxisBottom } from "@visx/axis";
import { localPoint } from "@visx/event";
import { Group } from "@visx/group";
import { ParentSize } from "@visx/responsive";
import { scaleBand, scaleLinear } from "@visx/scale";
import { TooltipWithBounds, useTooltip } from "@visx/tooltip";
import { useThemeColors } from "@/lib/themeColors";
import { useVariant } from "@/lib/variant";
import brandData from "@/data/yarn_brands.json";

/* Which brands knitters come back to. For every panel project that used a
   brand, the same knitter's next few panel projects with a linked yarn:
   did any of them use the brand again? The return rate counts only later
   projects on a different pattern; the base rate is how often any
   knitter's next few contain the brand. The gap between the two dots is
   loyalty beyond availability. Each knitter is weighted once. Only panel
   projects are seen, so "next" means the next panel projects. */

interface Period { period: string; return_rate: number | null; base_rate: number | null; users: number }
interface Row { id: number; name: string; users: number; transitions: number; return_rate: number; base_rate: number; lift: number; next_same_share: number; periods: Period[] }

const ROWS: Row[] = (brandData.loyalty.rows as Row[]).slice().sort((a, b) => b.return_rate - a.return_rate);
const META = brandData.loyalty.meta;
const SHOW = 24;
const WINDOW: number = META.window;

const ROW_H = 22;
const MARGIN = { top: 8, right: 24, bottom: 36, left: 150 };

const pct = (v: number, d = 0) => `${(100 * v).toFixed(d)}%`;
const fmt = (n: number) => n.toLocaleString("en-US");

function Chart({ width, rows, article }: { width: number; rows: Row[]; article: boolean }) {
  const theme = useThemeColors();
  const { showTooltip, hideTooltip, tooltipData, tooltipLeft, tooltipTop } = useTooltip<Row>();
  const innerW = width - MARGIN.left - MARGIN.right;
  const innerH = rows.length * ROW_H;
  const xMax = useMemo(() => Math.ceil(Math.max(...rows.map((r) => r.return_rate)) * 20) / 20, [rows]);
  const x = useMemo(() => scaleLinear({ domain: [0, xMax], range: [0, Math.max(1, innerW)] }), [xMax, innerW]);
  const y = useMemo(() => scaleBand<string>({ domain: rows.map((r) => r.name), range: [0, innerH], padding: 0.3 }), [rows, innerH]);
  if (width < 10) return null;
  const ink = theme.resolve("--primary");
  const grey = theme.role.muted;
  const mid = (name: string) => (y(name) ?? 0) + y.bandwidth() / 2;

  return (
    <div className="relative">
      <svg width={width} height={innerH + MARGIN.top + MARGIN.bottom} role="img"
        aria-label={`Share of knitters whose next ${WINDOW} projects on another pattern include the brand, against the base rate, for ${rows.length} brands with at least ${fmt(META.min_users)} knitters, sorted by return rate.`}>
        <Group left={MARGIN.left} top={MARGIN.top}>
          {x.ticks(5).map((t) => (
            <line key={t} x1={x(t)} x2={x(t)} y1={0} y2={innerH} stroke={grey} strokeOpacity={0.18} />
          ))}
          {rows.map((r) => {
            const cy = mid(r.name);
            const active = tooltipData?.id === r.id;
            return (
              <Group key={r.id}
                onPointerMove={(e) => { const p = localPoint(e); if (p) showTooltip({ tooltipData: r, tooltipLeft: p.x, tooltipTop: p.y }); }}
                onPointerLeave={hideTooltip} style={{ cursor: article ? undefined : "default" }}>
                <rect x={-MARGIN.left} y={y(r.name)} width={width} height={y.bandwidth()} fill="transparent" />
                <text x={-10} y={cy + 4} fontSize={11.5} textAnchor="end" fill="var(--foreground)" fontWeight={active ? 600 : 400}>
                  {r.name}
                </text>
                <line x1={x(r.base_rate)} x2={x(r.return_rate)} y1={cy} y2={cy} stroke={grey} strokeOpacity={0.5} strokeWidth={2} />
                <circle cx={x(r.base_rate)} cy={cy} r={4} fill="var(--background)" stroke={grey} strokeWidth={1.5} />
                <circle cx={x(r.return_rate)} cy={cy} r={5} fill={ink} />
                {(active || r === rows[0]) && (
                  <text x={x(r.return_rate) + 9} y={cy + 4} fontSize={11} fill="var(--foreground)" fontWeight={600}>
                    {pct(r.return_rate)}
                  </text>
                )}
              </Group>
            );
          })}
          <AxisBottom top={innerH} scale={x} numTicks={5} tickFormat={(v) => pct(Number(v))}
            stroke={grey} tickStroke={grey} tickLabelProps={{ fill: grey, fontSize: 11, textAnchor: "middle" }} />
          <text x={innerW} y={innerH + 32} fontSize={11} textAnchor="end" fill={grey}>
            share whose next {WINDOW} projects (on another pattern) include the brand
          </text>
        </Group>
      </svg>

      <div className="mt-1 flex flex-wrap gap-x-5 gap-y-1 text-xs" style={{ color: "var(--muted)" }}>
        <span className="inline-flex items-center gap-1.5">
          <i className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: ink }} /> after a project with the brand
        </span>
        <span className="inline-flex items-center gap-1.5">
          <i className="inline-block h-2.5 w-2.5 rounded-full border" style={{ borderColor: grey, borderWidth: 1.5 }} /> any knitter's next {WINDOW}{" "}
        </span>
      </div>

      {tooltipData && (
        <TooltipWithBounds left={tooltipLeft} top={tooltipTop} className="pointer-events-none"
          style={{ position: "absolute", background: "var(--background)", color: "var(--foreground)",
            border: "1px solid var(--muted)", borderRadius: 6, padding: "8px 10px", fontSize: 12, lineHeight: 1.5, maxWidth: 280 }}>
          <div className="font-semibold">{tooltipData.name}</div>
          <div>{pct(tooltipData.return_rate, 1)} use it again within their next {WINDOW} projects on another pattern, against {pct(tooltipData.base_rate, 1)} for any knitter ({tooltipData.lift.toFixed(1)}×)</div>
          <div style={{ color: grey }}>{fmt(tooltipData.users)} knitters · {pct(tooltipData.next_same_share)} made the same pattern next</div>
          <div className="mt-1.5 border-t pt-1.5 tabular-nums" style={{ borderColor: "color-mix(in srgb, var(--muted) 30%, transparent)" }}>
            {tooltipData.periods.map((p) => (
              <div key={p.period} className="flex justify-between gap-4">
                <span style={{ color: grey }}>{p.period}</span>
                <span>{p.return_rate === null ? "–" : `${pct(p.return_rate)} vs ${pct(p.base_rate ?? 0)}`}</span>
              </div>
            ))}
          </div>
        </TooltipWithBounds>
      )}
    </div>
  );
}

export default function YarnBrandLoyalty() {
  const article = useVariant() === "article";
  const [all, setAll] = useState(false);
  const rows = all ? ROWS : ROWS.slice(0, SHOW);
  const kp = ROWS.find((r) => r.name === "Knit Picks");

  return (
    <figure id="yarn-brand-loyalty" className={article ? "w-full" : "w-full rounded-lg p-4"}
      style={article ? undefined : { background: "var(--surface-figure)" }}>
      <figcaption className="mb-3">
        <h2 className="text-lg font-semibold">Which brands knitters come back to</h2>
        <p className="text-sm" style={{ color: "var(--muted)" }}>
          After a project with a brand, how often the same knitter used it again within their
          next {WINDOW} projects on another pattern, against how often any knitter's next {WINDOW}{" "}
          include it. Brands with at least {fmt(META.min_users)} knitters, sorted by return rate.
          {!article && " Hover a brand for its numbers by period."}
        </p>
      </figcaption>
      <ParentSize>{({ width }) => <Chart width={width} rows={rows} article={article} />}</ParentSize>
      {!article && ROWS.length > SHOW && (
        <button type="button" onClick={() => setAll(!all)} className="mt-2 rounded-full border px-2.5 py-0.5 text-xs"
          style={{ borderColor: "color-mix(in srgb, var(--muted) 40%, transparent)", color: "var(--muted)" }}>
          {all ? `show the top ${SHOW}` : `show all ${ROWS.length} brands`}
        </button>
      )}

      {!article && <details className="mt-3 text-xs">
        <summary className="cursor-pointer" style={{ color: "var(--muted)" }}>Table view</summary>
        <div className="overflow-x-auto">
          <table className="mt-2 w-full tabular-nums" style={{ borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ color: "var(--muted)" }}>
                <th className="py-1 text-left font-medium">brand</th>
                <th className="py-1 text-right font-medium">knitters</th>
                <th className="py-1 text-right font-medium">return</th>
                <th className="py-1 text-right font-medium">base</th>
                <th className="py-1 text-right font-medium">ratio</th>
                {META.periods.map((p) => <th key={p} className="py-1 text-right font-medium">{p}</th>)}
              </tr>
            </thead>
            <tbody>
              {ROWS.map((r) => (
                <tr key={r.id} style={{ borderTop: "1px solid color-mix(in srgb, var(--muted) 30%, transparent)" }}>
                  <td className="py-1">{r.name}</td>
                  <td className="py-1 text-right">{fmt(r.users)}</td>
                  <td className="py-1 text-right">{pct(r.return_rate, 1)}</td>
                  <td className="py-1 text-right">{pct(r.base_rate, 1)}</td>
                  <td className="py-1 text-right">{r.lift.toFixed(1)}×</td>
                  {r.periods.map((p) => <td key={p.period} className="py-1 text-right">{p.return_rate === null ? "–" : pct(p.return_rate)}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>}

      {!article && (
        <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
          {fmt(META.projects)} projects by {fmt(META.knitters)} knitters that were followed by at least one
          project on another pattern, each knitter weighted once; later projects on the same
          pattern ({pct(META.next_same_share)} of next projects) do not count as a return. Only
          projects on the panel's patterns are seen, so "next" means the next panel projects
          with a linked yarn.
          {kp && <> Knit Picks has the highest return rate of any large brand, {pct(kp.return_rate)}, and it
          held through 2021 after the 2017 sale while its base rate fell, so the decline up to
          then is fewer new knitters picking it up. The last period is lower for every brand:
          those knitters have had less time for a next project.</>}
        </p>
      )}
    </figure>
  );
}
