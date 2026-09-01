"use client";

import { useMemo, useState } from "react";
import { AxisBottom, AxisLeft } from "@visx/axis";
import { curveMonotoneX } from "@visx/curve";
import { GridRows } from "@visx/grid";
import { Group } from "@visx/group";
import { ParentSize } from "@visx/responsive";
import { scaleLinear, scalePoint } from "@visx/scale";
import { AreaClosed, LinePath } from "@visx/shape";
import { useThemeColors } from "@/lib/themeColors";
import evergreenData from "@/data/evergreen.json";

/* Section 8's due-diligence figure: does pattern age explain the cohort
   decline? Left: how fast a hit collects its lifetime favorites (stock).
   Right: what patterns still earn per year, by age and measurement
   period (flow). ~20 aggregate points, so plain SVG throughout. */

interface StockRow {
  age: number;
  q25: number;
  median: number;
  q75: number;
  n: number;
}
interface FlowSeries {
  period: string;
  points: { age: string; gain: number; n: number }[];
}

const STOCK: StockRow[] = evergreenData.stock;
const FLOW: FlowSeries[] = evergreenData.flow;
const AGE_LABELS = ["0–2", "2–5", "5–10", "10+"];

const MARGIN = { top: 16, right: 96, bottom: 40, left: 48 };
const PANEL_H = 340;

function StockPanel({ width }: { width: number }) {
  const theme = useThemeColors();
  const innerW = width - MARGIN.left - MARGIN.right;
  const innerH = PANEL_H - MARGIN.top - MARGIN.bottom;
  const [hover, setHover] = useState<StockRow | null>(null);

  const xScale = useMemo(
    () => scaleLinear({ domain: [0, 14], range: [0, innerW] }),
    [innerW],
  );
  const yScale = useMemo(
    () => scaleLinear({ domain: [0, 100], range: [innerH, 0] }),
    [innerH],
  );

  if (width < 10) return null;
  const c = theme.chart[0];

  return (
    <svg width={width} height={PANEL_H} role="img"
      aria-label="Median share of a hit pattern's lifetime favorites already collected at each age: 52% by year one, 84% by year five.">
      <Group left={MARGIN.left} top={MARGIN.top}>
        <GridRows scale={yScale} width={innerW} stroke={theme.role.muted} strokeOpacity={0.18} />
        <AreaClosed
          data={STOCK}
          x={(d) => xScale(d.age)}
          y0={(d) => yScale(d.q25)}
          y1={(d) => yScale(d.q75)}
          yScale={yScale}
          fill={c}
          opacity={0.15}
          curve={curveMonotoneX}
        />
        <LinePath
          data={STOCK}
          x={(d) => xScale(d.age)}
          y={(d) => yScale(d.median)}
          stroke={c}
          strokeWidth={2.5}
          curve={curveMonotoneX}
        />
        {STOCK.map((d) => (
          <circle key={d.age} cx={xScale(d.age)} cy={yScale(d.median)}
            r={hover?.age === d.age ? 4.5 : 3} fill={c}
            stroke="var(--background)" strokeWidth={1}
            onMouseEnter={() => setHover(d)}
            onMouseLeave={() => setHover(null)} />
        ))}
        {[{ age: 1, dy: 16 }, { age: 5, dy: 26 }].map(({ age, dy }) => {
          const row = STOCK.find((d) => d.age === age);
          if (!row) return null;
          return (
            <text key={age} x={xScale(age) + 8} y={yScale(row.median) + dy}
              fontSize={11} fontWeight={600} fill={c}>
              {Math.round(row.median)}% by year {age}
            </text>
          );
        })}
        {hover && (
          <text x={xScale(hover.age)} y={yScale(hover.q75) - 8}
            fontSize={10} textAnchor="middle" fill={theme.role.muted}>
            age {hover.age}: {hover.median}% (middle half {hover.q25}–{hover.q75}%, n={hover.n})
          </text>
        )}
        <AxisLeft scale={yScale} numTicks={5} tickFormat={(v) => `${v}%`}
          stroke={theme.role.muted} tickStroke={theme.role.muted}
          tickLabelProps={{ fill: theme.role.muted, fontSize: 11, textAnchor: "end", dx: -4 }} />
        <AxisBottom top={innerH} scale={xScale}
          tickValues={[0, 2, 4, 6, 8, 10, 12, 14]}
          tickFormat={(v) => String(v)}
          stroke={theme.role.muted} tickStroke={theme.role.muted}
          tickLabelProps={{ fill: theme.role.muted, fontSize: 11, textAnchor: "middle" }} />
        <text x={innerW / 2} y={innerH + 34} fontSize={11} textAnchor="middle"
          fill={theme.role.muted}>
          pattern age (years)
        </text>
      </Group>
    </svg>
  );
}

function FlowPanel({ width }: { width: number }) {
  const theme = useThemeColors();
  const innerW = width - MARGIN.left - MARGIN.right;
  const innerH = PANEL_H - MARGIN.top - MARGIN.bottom;
  const [hover, setHover] = useState<{ period: string; age: string; gain: number; n: number } | null>(null);

  const periodColor: Record<string, string> = {
    "2011–2015": theme.chart[2],
    "2016–2020": theme.chart[1],
    "2021–2026": theme.chartContrast[0],
  };

  const xScale = useMemo(
    () => scalePoint({ domain: AGE_LABELS, range: [0, innerW], padding: 0.3 }),
    [innerW],
  );
  const yScale = useMemo(
    () => scaleLinear({ domain: [0, 560], range: [innerH, 0] }),
    [innerH],
  );

  if (width < 10) return null;

  return (
    <svg width={width} height={PANEL_H} role="img"
      aria-label="Median favorites gained per year by pattern age, for three measurement periods. Every age group earned less in later periods: fresh patterns fell from roughly 508 favorites per year in 2011 to 2015 down to 323 in 2021 to 2026.">
      <Group left={MARGIN.left} top={MARGIN.top}>
        <GridRows scale={yScale} width={innerW} stroke={theme.role.muted} strokeOpacity={0.18} />
        {FLOW.map((s) => {
          const c = periodColor[s.period] ?? theme.role.muted;
          const last = s.points[s.points.length - 1];
          return (
            <Group key={s.period}>
              <LinePath
                data={s.points}
                x={(d) => xScale(d.age) ?? 0}
                y={(d) => yScale(d.gain)}
                stroke={c}
                strokeWidth={2.5}
                curve={curveMonotoneX}
              />
              {s.points.map((d) => (
                <circle key={d.age} cx={xScale(d.age)} cy={yScale(d.gain)}
                  r={hover?.period === s.period && hover?.age === d.age ? 4.5 : 3}
                  fill={c} stroke="var(--background)" strokeWidth={1}
                  onMouseEnter={() => setHover({ period: s.period, ...d })}
                  onMouseLeave={() => setHover(null)} />
              ))}
              <text x={(xScale(last.age) ?? 0) + 10} y={yScale(last.gain) + 4}
                fontSize={11} fontWeight={600} fill={c}>
                {s.period}
              </text>
            </Group>
          );
        })}
        {hover && (
          <text x={xScale(hover.age)} y={yScale(hover.gain) - 12}
            fontSize={10} textAnchor="middle" fill={theme.role.muted}>
            {hover.period}, age {hover.age}: {hover.gain}/yr (n={hover.n})
          </text>
        )}
        <AxisLeft scale={yScale} numTicks={6}
          stroke={theme.role.muted} tickStroke={theme.role.muted}
          tickLabelProps={{ fill: theme.role.muted, fontSize: 11, textAnchor: "end", dx: -4 }} />
        <AxisBottom top={innerH} scale={xScale}
          stroke={theme.role.muted} tickStroke={theme.role.muted}
          tickLabelProps={{ fill: theme.role.muted, fontSize: 11, textAnchor: "middle" }} />
        <text x={innerW / 2} y={innerH + 34} fontSize={11} textAnchor="middle"
          fill={theme.role.muted}>
          pattern age at measurement (years)
        </text>
      </Group>
    </svg>
  );
}

export default function EvergreenCurves() {
  return (
    <figure id="evergreen-chart" className="w-full">
      <figcaption className="mb-3">
        <h2 className="text-lg font-semibold">
          Do old patterns explain the gap? Measured, and no
        </h2>
        <p className="text-sm" style={{ color: "var(--muted)" }}>
          Archived Ravelry pages let six winners' catalogs be replayed through
          time. Left: a hit collects half its lifetime favorites in year one
          (median, with the middle half of patterns shaded). Right: what
          patterns still earn per year as they age — every age group earned
          less in each later period.
        </p>
      </figcaption>
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <div>
          <div className="h-[340px] w-full">
            <ParentSize>{({ width }) => <StockPanel width={width} />}</ParentSize>
          </div>
          <p className="mt-1 text-center text-xs" style={{ color: "var(--muted)" }}>
            share of lifetime favorites already collected
          </p>
        </div>
        <div>
          <div className="h-[340px] w-full">
            <ParentSize>{({ width }) => <FlowPanel width={width} />}</ParentSize>
          </div>
          <p className="mt-1 text-center text-xs" style={{ color: "var(--muted)" }}>
            median favorites gained per year, by measurement period
          </p>
        </div>
      </div>
      <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
        Source: 95 Wayback Machine captures of six designer pages, 2010–2026,
        joined to full catalogs (4,456 pattern-date observations). Cells with
        fewer than 15 observations omitted.
      </p>
    </figure>
  );
}
