"use client";

import { useEffect, useMemo, useState } from "react";
import { AxisBottom, AxisLeft } from "@visx/axis";
import { curveStepAfter } from "@visx/curve";
import { GridRows } from "@visx/grid";
import { Group } from "@visx/group";
import { ParentSize } from "@visx/responsive";
import { scaleBand, scaleLinear } from "@visx/scale";
import { LinePath } from "@visx/shape";
import { TooltipWithBounds, useTooltip } from "@visx/tooltip";
import { useThemeColors } from "@/lib/themeColors";
import { useVariant } from "@/lib/variant";
import mkalData from "@/data/mkal.json";
import { ROWS, type MkalRow } from "./MkalParticipation";

/* What happened to the projects cast on during each MKAL: finished on
   time (by clue 4 + 1 week), finished within 90 days of clue 1, finished
   later, still open, or abandoned (frogged or hibernating). Click a year
   to see its finishing curve: the cumulative share finished by day N. */

type Outcome = "on_time" | "within_90" | "later" | "open" | "abandoned";

const ON_TIME_DAYS: number = mkalData.meta.on_time_days;
const NINETY: number = mkalData.meta.ninety_days;

const TOKEN: Record<Outcome, string> = {
  on_time: "--ramp-1", within_90: "--ramp-2", later: "--ramp-3",
  open: "--ramp-tail-1", abandoned: "--highlight",
};

const OUTCOMES: { key: Outcome; label: string; short: string }[] = [
  { key: "on_time", label: `finished on time (by clue 4 + 1 week, day ${ON_TIME_DAYS})`, short: "on time" },
  { key: "within_90", label: `finished within ${NINETY} days of clue 1`, short: `≤ ${NINETY} days` },
  { key: "later", label: "finished later, or finished with no date logged", short: "later" },
  // abandoned sits between the ramp and the grey: light teal next to grey is
  // the one pair the validator flags, saffron separates cleanly from both
  { key: "abandoned", label: "abandoned (frogged or hibernating)", short: "abandoned" },
  { key: "open", label: "still in progress", short: "still open" },
];

function counts(d: MkalRow): Record<Outcome, number> {
  const o = d.outcomes;
  return { on_time: o.on_time, within_90: o.within_90, later: o.later + o.undated, open: o.open, abandoned: o.abandoned };
}

const MARGIN = { top: 16, right: 24, bottom: 40, left: 48 };
const BAR_H = 340;
const CURVE_H = 300;
const CURVE_MARGIN = { top: 20, right: 24, bottom: 44, left: 48 };
const fmt = (n: number) => n.toLocaleString("en-US");
const pct = (x: number) => `${Math.round(100 * x)}%`;

function Bars({ width, mode, selected, onSelect, colors }: {
  width: number; mode: "share" | "count"; selected: number;
  onSelect: (y: number) => void; colors: Record<Outcome, string>;
}) {
  const theme = useThemeColors();
  const { showTooltip, hideTooltip, tooltipData, tooltipLeft, tooltipTop } = useTooltip<MkalRow>();
  const innerW = width - MARGIN.left - MARGIN.right;
  const innerH = BAR_H - MARGIN.top - MARGIN.bottom;

  const xScale = useMemo(
    () => scaleBand<number>({ domain: ROWS.map((d) => d.year), range: [0, innerW], padding: 0.22 }),
    [innerW],
  );
  const yMax = mode === "share" ? 1 : Math.ceil(Math.max(...ROWS.map((d) => d.projects)) / 1000) * 1000;
  const yScale = useMemo(() => scaleLinear({ domain: [0, yMax], range: [innerH, 0] }), [innerH, yMax]);
  if (width < 10) return null;
  const bw = Math.min(24, xScale.bandwidth());
  const pad = (xScale.bandwidth() - bw) / 2;

  return (
    <div className="relative">
      <svg width={width} height={BAR_H} role="img"
        aria-label={`Outcomes of projects cast on during each Westknits MKAL: on-time finishes fell from roughly a third in the early years to around ten to fifteen percent since 2020, while the share finished at all stayed between about 55 and 85 percent. 2018, 2022 and 2023 have the most abandoned projects.`}>
        <Group left={MARGIN.left} top={MARGIN.top}>
          <GridRows scale={yScale} width={innerW} stroke={theme.role.muted} strokeOpacity={0.18} />
          {ROWS.map((d) => {
            const x = (xScale(d.year) ?? 0) + pad;
            const c = counts(d);
            const total = mode === "share" ? d.projects : 1;
            const active = tooltipData?.year === d.year;
            const isSel = selected === d.year;
            let acc = 0;
            return (
              <Group key={d.year}
                onPointerEnter={() => showTooltip({ tooltipData: d,
                  tooltipLeft: MARGIN.left + x + bw / 2, tooltipTop: MARGIN.top + yScale(mode === "share" ? 1 : d.projects) })}
                onPointerLeave={hideTooltip}
                onClick={() => onSelect(d.year)}
                style={{ cursor: "pointer" }}>
                {OUTCOMES.map((o) => {
                  const v = c[o.key] / total;
                  const y0 = acc; acc += v;
                  const top = yScale(acc), bottom = yScale(y0);
                  return (
                    <rect key={o.key} x={x} y={top} width={bw}
                      height={Math.max(0, bottom - top - (o.key === "on_time" ? 0 : 2))}
                      fill={colors[o.key]} opacity={active || isSel ? 1 : 0.85} />
                  );
                })}
                {d.censored && (
                  <rect x={x} y={yScale(acc)} width={bw} height={innerH - yScale(acc)}
                    fill="none" stroke={theme.role.muted} strokeDasharray="3 3" />
                )}
                {isSel && (
                  <rect x={x - 3} y={yScale(acc) - 3} width={bw + 6} height={innerH - yScale(acc) + 6}
                    fill="none" stroke="var(--foreground)" strokeWidth={1.5} rx={3} />
                )}
              </Group>
            );
          })}
          <AxisLeft scale={yScale} numTicks={5}
            tickFormat={(v) => (mode === "share" ? pct(Number(v)) : Number(v) >= 1000 ? `${Number(v) / 1000}k` : String(v))}
            stroke={theme.role.muted} tickStroke={theme.role.muted}
            tickLabelProps={{ fill: theme.role.muted, fontSize: 11, textAnchor: "end", dx: -4 }} />
          <AxisBottom top={innerH} scale={xScale}
            tickValues={ROWS.map((d) => d.year).filter((y) => y % 2 === 1)}
            tickFormat={(v) => String(v)}
            stroke={theme.role.muted} tickStroke={theme.role.muted}
            tickLabelProps={{ fill: theme.role.muted, fontSize: 11, textAnchor: "middle" }} />
        </Group>
      </svg>
      {tooltipData && (() => {
        const c = counts(tooltipData);
        return (
          <TooltipWithBounds left={tooltipLeft} top={tooltipTop} className="pointer-events-none"
            style={{ position: "absolute", background: "var(--background)", color: "var(--foreground)",
              border: "1px solid var(--muted)", borderRadius: 6, padding: "8px 10px", fontSize: 12, lineHeight: 1.5 }}>
            <div className="font-semibold">{tooltipData.year} · {tooltipData.name.replace(/^MKAL \d+: /, "")}</div>
            <div>{fmt(tooltipData.projects)} projects cast on during the KAL</div>
            {OUTCOMES.map((o) => (
              <div key={o.key} style={{ color: colors[o.key] }}>
                {pct(c[o.key] / tooltipData.projects)} {o.short} ({fmt(c[o.key])})
              </div>
            ))}
            <div style={{ color: theme.role.muted }}>
              finished at all: {pct((c.on_time + c.within_90 + c.later) / tooltipData.projects)}
              {tooltipData.censored && " · still running"}
            </div>
          </TooltipWithBounds>
        );
      })()}
    </div>
  );
}

function Curve({ width, selected, colors }: { width: number; selected: number; colors: Record<Outcome, string> }) {
  const theme = useThemeColors();
  const innerW = width - CURVE_MARGIN.left - CURVE_MARGIN.right;
  const innerH = CURVE_H - CURVE_MARGIN.top - CURVE_MARGIN.bottom;
  const maxDay = 180;
  const xScale = useMemo(() => scaleLinear({ domain: [0, maxDay], range: [0, innerW] }), [innerW]);
  const yScale = useMemo(() => scaleLinear({ domain: [0, 1], range: [innerH, 0] }), [innerH]);
  if (width < 10) return null;
  const row = ROWS.find((d) => d.year === selected) ?? ROWS[ROWS.length - 2];
  const pts = (r: MkalRow) => r.curve.slice(0, maxDay + 1).map((v, i) => ({ day: i, v }));
  const onTime = row.curve[ON_TIME_DAYS];
  const ninety = row.curve[NINETY];
  const ever = (counts(row).on_time + counts(row).within_90 + counts(row).later) / row.projects;

  return (
    <svg width={width} height={CURVE_H} role="img"
      aria-label={`Cumulative share of ${row.year} KAL projects finished by day after clue 1: ${pct(onTime)} by day ${ON_TIME_DAYS}, ${pct(ninety)} by day ${NINETY}, ${pct(ever)} ever.`}>
      <Group left={CURVE_MARGIN.left} top={CURVE_MARGIN.top}>
        <GridRows scale={yScale} width={innerW} stroke={theme.role.muted} strokeOpacity={0.18} />
        {/* clue drops */}
        {[0, 7, 14, 21].map((d) => (
          <line key={d} x1={xScale(d)} x2={xScale(d)} y1={0} y2={innerH}
            stroke={theme.role.muted} strokeDasharray="2 3" strokeWidth={1} />
        ))}
        <text x={xScale(21) + 4} y={12} fontSize={10} fill={theme.role.muted}>clue 4</text>
        {/* on-time and 90-day marks */}
        {[{ d: ON_TIME_DAYS, v: onTime, c: colors.on_time, l: "on time" },
          { d: NINETY, v: ninety, c: colors.within_90, l: `${NINETY} days` }].map((m) => (
          <Group key={m.d}>
            <line x1={xScale(m.d)} x2={xScale(m.d)} y1={yScale(m.v)} y2={innerH} stroke={m.c} strokeWidth={1.5} />
            <circle cx={xScale(m.d)} cy={yScale(m.v)} r={4.5} fill={m.c} stroke="var(--background)" strokeWidth={1.5} />
            <text x={xScale(m.d) + 8} y={yScale(m.v) - 8} fontSize={11} fontWeight={600} fill={m.c}
              stroke="var(--background)" strokeWidth={4} paintOrder="stroke">
              {pct(m.v)} {m.l}
            </text>
          </Group>
        ))}
        {/* every other year, faint, for context */}
        {ROWS.filter((r) => !r.censored && r.year !== row.year).map((r) => (
          <LinePath key={r.year} data={pts(r)} x={(p) => xScale(p.day)} y={(p) => yScale(p.v)}
            stroke={theme.role.muted} strokeOpacity={0.25} strokeWidth={1} curve={curveStepAfter} />
        ))}
        <LinePath data={pts(row)} x={(p) => xScale(p.day)} y={(p) => yScale(p.v)}
          stroke="var(--foreground)" strokeWidth={2.5} curve={curveStepAfter} />
        <text x={innerW} y={yScale(row.curve[maxDay]) - 8} fontSize={11} fontWeight={600}
          textAnchor="end" fill="var(--foreground)"
          stroke="var(--background)" strokeWidth={4} paintOrder="stroke">
          {row.year}: {pct(row.curve[maxDay])} by day {maxDay}, {pct(ever)} ever
        </text>
        <AxisLeft scale={yScale} numTicks={5} tickFormat={(v) => pct(Number(v))}
          stroke={theme.role.muted} tickStroke={theme.role.muted}
          tickLabelProps={{ fill: theme.role.muted, fontSize: 11, textAnchor: "end", dx: -4 }} />
        <AxisBottom top={innerH} scale={xScale} tickValues={[0, 28, 60, 90, 120, 150, 180]}
          tickFormat={(v) => String(v)}
          stroke={theme.role.muted} tickStroke={theme.role.muted}
          tickLabelProps={{ fill: theme.role.muted, fontSize: 11, textAnchor: "middle" }} />
        <text x={innerW / 2} y={innerH + 34} fontSize={11} textAnchor="middle" fill={theme.role.muted}>
          days since clue 1 (grey: every other year)
        </text>
      </Group>
    </svg>
  );
}

export default function MkalOutcomes() {
  const theme = useThemeColors();
  const article = useVariant() === "article";
  const [mode, setMode] = useState<"share" | "count">("share");
  const lastComplete = ROWS.filter((r) => !r.censored).at(-1)?.year ?? ROWS[0].year;
  const [selected, setSelected] = useState<number>(lastComplete);
  // ?year=2014 pre-selects a curve (for the screenshot pipeline)
  useEffect(() => {
    const y = Number(new URLSearchParams(window.location.search).get("year"));
    if (ROWS.some((r) => r.year === y)) setSelected(y);
  }, []);
  // ordinal ramp for the finished tiers, grey for open, one warm slot for abandoned
  const colors = Object.fromEntries(
    (Object.keys(TOKEN) as Outcome[]).map((k) => [k, theme.resolve(TOKEN[k])]),
  ) as Record<Outcome, string>;
  const sel = ROWS.find((d) => d.year === selected);

  return (
    <figure id="mkal-outcomes" className="w-full">
      <div id="mkal-outcomes-bars">
      <figcaption className="mb-3">
        <h2 className="text-lg font-semibold">Did they finish?</h2>
        <p className="text-sm" style={{ color: "var(--muted)" }}>
          What became of the projects cast on during each MKAL. On time means
          finished within a week of the last clue.{!article && " Click a year to see its finishing curve."}
        </p>
      </figcaption>

      <div className="mb-2 flex flex-wrap items-center gap-x-5 gap-y-1 text-xs" style={{ color: "var(--muted)" }}>
        {OUTCOMES.map((o) => (
          <span key={o.key} className="inline-flex items-center gap-1.5">
            <i className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: `var(${TOKEN[o.key]})` }} /> {o.label}
          </span>
        ))}
        {!article && <span className="ml-auto inline-flex overflow-hidden rounded border" style={{ borderColor: "var(--muted)" }}>
          {(["share", "count"] as const).map((m) => (
            <button key={m} type="button" onClick={() => setMode(m)}
              className="px-2 py-0.5"
              style={{ background: mode === m ? "var(--foreground)" : "transparent",
                color: mode === m ? "var(--background)" : "var(--muted)" }}>
              {m === "share" ? "share" : "projects"}
            </button>
          ))}
        </span>}
      </div>

      <ParentSize>{({ width }) => (
        <Bars width={width} mode={mode} selected={article ? -1 : selected} onSelect={setSelected} colors={colors} />
      )}</ParentSize>
      </div>

      {/* margin (not padding) keeps the bars' axis labels out of the screenshot clip (PAD = 24px) */}
      <div id="mkal-finish-curve" className={article ? "mt-14" : "mt-6"}>
      <h3 className="text-sm font-semibold">
        Finishing curve, {sel?.year} {sel?.name.replace(/^MKAL \d+: /, "")}
      </h3>
      <p className="mb-1 text-xs" style={{ color: "var(--muted)" }}>
        Share of that year's KAL projects finished by each day after clue 1.
        Projects finished without a logged date never appear on the curve, so it is a floor.
      </p>
      <ParentSize>{({ width }) => <Curve width={width} selected={selected} colors={colors} />}</ParentSize>
      </div>

      {!article && <details className="mt-3 text-xs">
        <summary className="cursor-pointer" style={{ color: "var(--muted)" }}>Table view</summary>
        <table className="mt-2 w-full tabular-nums" style={{ borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ color: "var(--muted)" }}>
              <th className="py-1 text-left font-medium">year</th>
              <th className="py-1 text-right font-medium">projects</th>
              {OUTCOMES.map((o) => <th key={o.key} className="py-1 text-right font-medium">{o.short}</th>)}
              <th className="py-1 text-right font-medium">finished at all</th>
            </tr>
          </thead>
          <tbody>
            {ROWS.map((d) => { const c = counts(d); return (
              <tr key={d.year} style={{ borderTop: "1px solid color-mix(in srgb, var(--muted) 30%, transparent)" }}>
                <td className="py-1">{d.year}{d.censored ? " (running)" : ""}</td>
                <td className="py-1 text-right">{fmt(d.projects)}</td>
                {OUTCOMES.map((o) => <td key={o.key} className="py-1 text-right">{pct(c[o.key] / d.projects)}</td>)}
                <td className="py-1 text-right">{pct((c.on_time + c.within_90 + c.later) / d.projects)}</td>
              </tr>); })}
          </tbody>
        </table>
      </details>}

      {!article && (
        <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
          Source: Ravelry projects started between a week before and four weeks after
          clue 1, status and dates as logged by the knitter, {mkalData.meta.generated}.
          The current year is still running (dashed). Abandoned = marked frogged or hibernating.
        </p>
      )}
    </figure>
  );
}
