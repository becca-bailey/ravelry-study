"use client";

import { useMemo, useState } from "react";
import { AxisBottom, AxisLeft } from "@visx/axis";
import { GridRows } from "@visx/grid";
import { Group } from "@visx/group";
import { ParentSize } from "@visx/responsive";
import { scaleBand, scaleLinear } from "@visx/scale";
import { TooltipWithBounds, useTooltip } from "@visx/tooltip";
import { useThemeColors } from "@/lib/themeColors";
import { useVariant } from "@/lib/variant";
import mkalData from "@/data/mkal.json";

/* Who cast on during each Westknits MKAL: distinct Ravelry knitters whose
   project started between a week before and four weeks after clue 1,
   split into first-timers and returning participants. Knitters who made
   the shawl after the event are not counted — that afterlife is the
   story of a pattern, not of the KAL. */

export interface MkalRow {
  year: number;
  name: string;
  clue1: string;
  kal_end: string;
  knitters: number;
  first_timers: number;
  returning: number;
  projects: number;
  outcomes: Record<"on_time" | "within_90" | "later" | "undated" | "open" | "abandoned", number>;
  curve: number[];
  censored: boolean;
}

export const ROWS: MkalRow[] = mkalData.rows as MkalRow[];

const MARGIN = { top: 28, right: 24, bottom: 44, left: 48 };
const CHART_H = 360;

const fmt = (n: number) => n.toLocaleString("en-US");

function Chart({ width }: { width: number }) {
  const theme = useThemeColors();
  const { showTooltip, hideTooltip, tooltipData, tooltipLeft, tooltipTop } =
    useTooltip<MkalRow>();
  const [pinned, setPinned] = useState<number | null>(null);
  const innerW = width - MARGIN.left - MARGIN.right;
  const innerH = CHART_H - MARGIN.top - MARGIN.bottom;

  const xScale = useMemo(
    () => scaleBand<number>({ domain: ROWS.map((d) => d.year), range: [0, innerW], padding: 0.22 }),
    [innerW],
  );
  const yMax = useMemo(() => Math.ceil(Math.max(...ROWS.map((d) => d.knitters)) / 1000) * 1000, []);
  const yScale = useMemo(() => scaleLinear({ domain: [0, yMax], range: [innerH, 0] }), [innerH, yMax]);

  if (width < 10) return null;
  // two-step ordinal pair of the arcade hue: first MKAL dark, returning light
  const cFirst = theme.resolve("--mkal-finish-2");
  const cReturn = theme.resolve("--mkal-finish-3");
  const bw = Math.min(24, xScale.bandwidth());
  const pad = (xScale.bandwidth() - bw) / 2;
  const peak = ROWS.reduce((a, b) => (b.knitters > a.knitters ? b : a));

  const show = (d: MkalRow) =>
    showTooltip({
      tooltipData: d,
      tooltipLeft: MARGIN.left + (xScale(d.year) ?? 0) + xScale.bandwidth() / 2,
      tooltipTop: MARGIN.top + yScale(d.knitters),
    });

  return (
    <div className="relative">
      <svg width={width} height={CHART_H} role="img"
        aria-label={`Knitters who cast on during each Westknits MKAL, 2011 to ${ROWS[ROWS.length - 1].year}, split into first-timers and returning participants. Around one to two thousand a year through 2018, a jump in 2019, a peak of ${fmt(peak.knitters)} in ${peak.year}, then a gradual decline.`}>
        <Group left={MARGIN.left} top={MARGIN.top}>
          <GridRows scale={yScale} width={innerW} stroke={theme.role.muted} strokeOpacity={0.18} />

          {ROWS.map((d) => {
            const x = (xScale(d.year) ?? 0) + pad;
            const active = tooltipData?.year === d.year || pinned === d.year;
            const yTop = yScale(d.knitters);
            const yMid = yScale(d.first_timers);
            return (
              <Group key={d.year}
                onPointerEnter={() => show(d)}
                onPointerLeave={hideTooltip}
                onClick={() => setPinned(pinned === d.year ? null : d.year)}
                style={{ cursor: "pointer" }}>
                {/* returning on top, first-timers at the baseline */}
                <rect x={x} y={yTop} width={bw} height={Math.max(0, yMid - yTop - 2)}
                  fill={cReturn} opacity={active ? 1 : 0.85} rx={3} />
                <rect x={x} y={yMid} width={bw} height={innerH - yMid}
                  fill={cFirst} opacity={active ? 1 : 0.85} />
                {d.censored && (
                  <rect x={x} y={yTop} width={bw} height={innerH - yTop}
                    fill="none" stroke={theme.role.muted} strokeDasharray="3 3" />
                )}
                {(active || d.year === peak.year) && (
                  <text x={x + bw / 2} y={yTop - 6} fontSize={11} fontWeight={600}
                    textAnchor="middle" fill="var(--foreground)">
                    {fmt(d.knitters)}
                  </text>
                )}
              </Group>
            );
          })}

          <AxisLeft scale={yScale} numTicks={6}
            tickFormat={(v) => (Number(v) >= 1000 ? `${Number(v) / 1000}k` : String(v))}
            stroke={theme.role.muted} tickStroke={theme.role.muted}
            tickLabelProps={{ fill: theme.role.muted, fontSize: 11, textAnchor: "end", dx: -4 }} />
          <AxisBottom top={innerH} scale={xScale}
            tickValues={ROWS.map((d) => d.year).filter((y) => y % 2 === 1)}
            tickFormat={(v) => String(v)}
            stroke={theme.role.muted} tickStroke={theme.role.muted}
            tickLabelProps={{ fill: theme.role.muted, fontSize: 11, textAnchor: "middle" }} />
        </Group>
      </svg>

      <div className="mt-1 flex flex-wrap gap-x-5 gap-y-1 text-xs" style={{ color: "var(--muted)" }}>
        <span className="inline-flex items-center gap-1.5">
          <i className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: "var(--mkal-finish-2)" }} /> first MKAL
        </span>
        <span className="inline-flex items-center gap-1.5">
          <i className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: "var(--mkal-finish-3)" }} /> returning
        </span>
        <span className="inline-flex items-center gap-1.5">
          <i className="inline-block h-2.5 w-2.5 rounded-sm border border-dashed" style={{ borderColor: theme.role.muted }} /> in progress at collection
        </span>
      </div>

      {tooltipData && (
        <TooltipWithBounds left={tooltipLeft} top={tooltipTop} className="pointer-events-none"
          style={{ position: "absolute", background: "var(--background)", color: "var(--foreground)",
            border: "1px solid var(--muted)", borderRadius: 6, padding: "8px 10px", fontSize: 12, lineHeight: 1.5 }}>
          <div className="font-semibold">{tooltipData.year} · {tooltipData.name.replace(/^MKAL \d+: /, "")}</div>
          <div>{fmt(tooltipData.knitters)} knitters cast on during the KAL</div>
          <div style={{ color: cFirst }}>{fmt(tooltipData.first_timers)} first MKAL ({Math.round(100 * tooltipData.first_timers / tooltipData.knitters)}%)</div>
          <div style={{ color: cReturn }}>{fmt(tooltipData.returning)} returning</div>
          <div style={{ color: theme.role.muted }}>clue 1: {tooltipData.clue1}</div>
        </TooltipWithBounds>
      )}
    </div>
  );
}

export default function MkalParticipation() {
  const article = useVariant() === "article";
  return (
    <figure id="mkal-participation" className="w-full">
      <figcaption className="mb-3">
        <h2 className="text-lg font-semibold">Who cast on during the MKAL</h2>
        <p className="text-sm" style={{ color: "var(--muted)" }}>
          Ravelry knitters who started a project between a week before and four
          weeks after clue 1 of each Westknits MKAL, split by whether it was
          their first.{!article && " Hover or tap a year for the numbers."}
        </p>
      </figcaption>
      <ParentSize>{({ width }) => <Chart width={width} />}</ParentSize>
      {!article && <details className="mt-3 text-xs">
        <summary className="cursor-pointer" style={{ color: "var(--muted)" }}>Table view</summary>
        <table className="mt-2 w-full tabular-nums" style={{ borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ color: "var(--muted)" }}>
              <th className="py-1 text-left font-medium">year</th>
              <th className="py-1 text-left font-medium">shawl</th>
              <th className="py-1 text-left font-medium">clue 1</th>
              <th className="py-1 text-right font-medium">knitters</th>
              <th className="py-1 text-right font-medium">first MKAL</th>
              <th className="py-1 text-right font-medium">returning</th>
            </tr>
          </thead>
          <tbody>
            {ROWS.map((d) => (
              <tr key={d.year} style={{ borderTop: "1px solid color-mix(in srgb, var(--muted) 30%, transparent)" }}>
                <td className="py-1">{d.year}{d.censored ? " (running)" : ""}</td>
                <td className="py-1">{d.name.replace(/^MKAL \d+: /, "")}</td>
                <td className="py-1">{d.clue1}</td>
                <td className="py-1 text-right">{fmt(d.knitters)}</td>
                <td className="py-1 text-right">{fmt(d.first_timers)} ({Math.round(100 * d.first_timers / d.knitters)}%)</td>
                <td className="py-1 text-right">{fmt(d.returning)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>}

      {!article && (
        <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
          Source: every Ravelry project linked to each MKAL pattern, {mkalData.meta.generated}.
          Knitters who made the shawl after the event are not counted; that afterlife
          is large for the early designs (Exploration Station, 2014: about 1,100
          during the KAL, 7,600 ever). "First MKAL" means no earlier KAL-window
          cast-on in this series.
        </p>
      )}
    </figure>
  );
}
