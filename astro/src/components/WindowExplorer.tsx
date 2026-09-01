"use client";

import { useMemo } from "react";
import { AxisBottom, AxisLeft } from "@visx/axis";
import { curveMonotoneX } from "@visx/curve";
import { GridRows } from "@visx/grid";
import { Group } from "@visx/group";
import { ParentSize } from "@visx/responsive";
import { scaleLinear } from "@visx/scale";
import { LinePath } from "@visx/shape";
import { TooltipWithBounds, useTooltip } from "@visx/tooltip";
import { bisector, extent } from "d3-array";
import { localPoint } from "@visx/event";
import { useThemeColors } from "@/lib/themeColors";
import windowData from "@/data/window.json";

export interface CohortRow {
  year: number;
  n: number;
  floor: number;
  middle: number;
}

const ROWS: CohortRow[] = windowData.rows;

const MARGIN = { top: 24, right: 168, bottom: 40, left: 48 };
const bisectYear = bisector<CohortRow, number>((d) => d.year).center;

/* Annotation layers, in story order:
   - the golden age: 2007–2014, the decade the floor held at ~60%
   - the break: 2015, the year the blog-and-RSS ecosystem finished dying
   - the window: 2016, one generous year of the new Instagram algorithm */
const GOLDEN_AGE = { from: 2007, to: 2014.5 };
const FLICKER = { from: 2015.5, to: 2016.5 };
const MARKERS = [
  { year: 2013.5, label: "Google Reader shuts down (Jul 2013)" },
  { year: 2016, label: "Instagram's algorithm arrives" },
];

function Chart({ width, height }: { width: number; height: number }) {
  const theme = useThemeColors();
  const { showTooltip, hideTooltip, tooltipData, tooltipLeft, tooltipTop } =
    useTooltip<CohortRow>();
  const innerW = width - MARGIN.left - MARGIN.right;
  const innerH = height - MARGIN.top - MARGIN.bottom;

  const xScale = useMemo(() => {
    const [min, max] = extent(ROWS, (d) => d.year) as [number, number];
    return scaleLinear({ domain: [min, max], range: [0, innerW] });
  }, [innerW]);

  const yScale = useMemo(
    () => scaleLinear({ domain: [0, 70], range: [innerH, 0] }),
    [innerH],
  );

  const series = [
    {
      key: "floor" as const,
      label: "reached 100+ fans",
      sub: "a modest audience",
      color: theme.chart[0],
    },
    {
      key: "middle" as const,
      label: "reached 500–5,000 fans",
      sub: "the middle",
      color: theme.chartContrast[0],
    },
  ];

  const tickValues = useMemo(() => {
    const t: number[] = [];
    for (let y = 2008; y <= 2024; y += 4) t.push(y);
    return t;
  }, []);

  const onMove = (event: React.PointerEvent<SVGRectElement>) => {
    const point = localPoint(event);
    if (!point) return;
    const year = xScale.invert(point.x - MARGIN.left);
    const row = ROWS[bisectYear(ROWS, year)];
    if (!row) return;
    showTooltip({
      tooltipData: row,
      tooltipLeft: MARGIN.left + xScale(row.year),
      tooltipTop: MARGIN.top + yScale(row.floor),
    });
  };

  if (width < 10) return null;

  return (
    <div className="relative">
      <svg width={width} height={height} role="img"
        aria-label="Share of each entering cohort of Ravelry designers reaching 100+ fans (a modest audience) and 500 to 5,000 fans (the middle), 2007 to 2024. Both lines hold steady through 2014, break in 2015, rebound in 2016, then fall.">
        <Group left={MARGIN.left} top={MARGIN.top}>
          {/* golden age background */}
          <rect
            x={xScale(GOLDEN_AGE.from)}
            width={xScale(GOLDEN_AGE.to) - xScale(GOLDEN_AGE.from)}
            y={0}
            height={innerH}
            fill={theme.role.warning}
            opacity={0.16}
          />
          {/* the 2016 flicker */}
          <rect
            x={xScale(FLICKER.from)}
            width={xScale(FLICKER.to) - xScale(FLICKER.from)}
            y={0}
            height={innerH}
            fill={theme.chart[2]}
            opacity={0.18}
          />

          <GridRows scale={yScale} width={innerW} stroke={theme.role.muted} strokeOpacity={0.18} />

          {/* event markers */}
          {MARKERS.map((m) => (
            <Group key={m.year}>
              <line
                x1={xScale(m.year)}
                x2={xScale(m.year)}
                y1={0}
                y2={innerH}
                stroke={theme.role.muted}
                strokeDasharray="5 4"
                strokeWidth={1}
              />
              <text
                x={xScale(m.year) + 4}
                y={m.year < 2016 ? 34 : 52}
                fontSize={10}
                fill={theme.role.muted}
              >
                {m.label}
              </text>
            </Group>
          ))}

          {series.map((s) => (
            <Group key={s.key}>
              <LinePath
                data={ROWS}
                x={(d) => xScale(d.year)}
                y={(d) => yScale(d[s.key])}
                stroke={s.color}
                strokeWidth={2.5}
                curve={curveMonotoneX}
              />
              {ROWS.map((d) => (
                <circle
                  key={d.year}
                  cx={xScale(d.year)}
                  cy={yScale(d[s.key])}
                  r={tooltipData?.year === d.year ? 4.5 : 3}
                  fill={s.color}
                  stroke="var(--background)"
                  strokeWidth={1}
                />
              ))}
              {/* direct label at line end — no detached legend to decode.
                  Clamped so a line ending near 0% keeps its label on-chart. */}
              {(() => {
                const labelY = Math.min(
                  yScale(ROWS[ROWS.length - 1][s.key]) + 4,
                  innerH - 18,
                );
                return (
                  <>
                    <text x={innerW + 10} y={labelY} fontSize={12} fontWeight={600} fill={s.color}>
                      {s.label}
                    </text>
                    <text x={innerW + 10} y={labelY + 14} fontSize={10} fill={theme.role.muted}>
                      {s.sub}
                    </text>
                  </>
                );
              })()}
            </Group>
          ))}

          <AxisLeft
            scale={yScale}
            numTicks={7}
            tickFormat={(v) => `${v}%`}
            stroke={theme.role.muted}
            tickStroke={theme.role.muted}
            tickLabelProps={{ fill: theme.role.muted, fontSize: 11, textAnchor: "end", dx: -4 }}
          />
          <AxisBottom
            top={innerH}
            scale={xScale}
            tickValues={tickValues}
            tickFormat={(v) => String(v)}
            stroke={theme.role.muted}
            tickStroke={theme.role.muted}
            tickLabelProps={{ fill: theme.role.muted, fontSize: 11, textAnchor: "middle" }}
          />

          <rect
            width={innerW}
            height={innerH}
            fill="transparent"
            onPointerMove={onMove}
            onPointerLeave={hideTooltip}
          />
        </Group>
      </svg>

      {tooltipData && (
        <TooltipWithBounds
          left={tooltipLeft}
          top={tooltipTop}
          className="pointer-events-none"
          style={{
            position: "absolute",
            background: "var(--background)",
            color: "var(--foreground)",
            border: "1px solid var(--muted)",
            borderRadius: 6,
            padding: "8px 10px",
            fontSize: 12,
            lineHeight: 1.5,
          }}
        >
          <div className="font-semibold">{tooltipData.year} cohort</div>
          <div style={{ color: theme.chart[0] }}>
            {tooltipData.floor}% reached 100+ fans
          </div>
          <div style={{ color: theme.chartContrast[0] }}>
            {tooltipData.middle}% reached 500–5,000 fans
          </div>
          <div style={{ color: theme.role.muted }}>{tooltipData.n} designers sampled</div>
        </TooltipWithBounds>
      )}
    </div>
  );
}

export default function WindowExplorer() {
  return (
    <figure id="window-chart" className="w-full">
      <figcaption className="mb-3">
        <h2 className="text-lg font-semibold">The window of opportunity, measured</h2>
        <p className="text-sm" style={{ color: "var(--muted)" }}>
          Share of each entering cohort of Ravelry designers (5+ published patterns) to
          find an audience — steady for a decade, broken in 2015, briefly generous in
          2016, closing since.
        </p>
      </figcaption>
      <div className="h-[440px] w-full">
        <ParentSize>{({ width, height }) => <Chart width={width} height={height} />}</ParentSize>
      </div>
      <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
        Source: Ravelry pattern registry, random sample of all entering cohorts
        2007–2024 (N=3,130 designers). Fan counts (Ravelry's designer-level follow, distinct from
        pattern favorites) as of August 2026.
      </p>
    </figure>
  );
}
