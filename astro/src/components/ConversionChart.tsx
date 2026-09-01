"use client";

import { useMemo, useState } from "react";
import { AxisBottom, AxisLeft } from "@visx/axis";
import { curveMonotoneX } from "@visx/curve";
import { GridRows } from "@visx/grid";
import { Group } from "@visx/group";
import { ParentSize } from "@visx/responsive";
import { scaleLinear } from "@visx/scale";
import { AreaClosed, LinePath } from "@visx/shape";
import { useThemeColors } from "@/lib/themeColors";
import conversionData from "@/data/conversion.json";

/* Attention decoupling from making: projects per 100 favorites, by the
   year a pattern was published. Recent years are shaded — young
   patterns' projects lag their favorites, so the tail overstates the
   decline and shouldn't be read literally. */

interface ConvRow {
  year: number;
  n: number;
  q25: number;
  median: number;
  q75: number;
}

const ROWS: ConvRow[] = conversionData.rows;
const LAG_FROM: number = conversionData.meta.lag_from;

const MARGIN = { top: 20, right: 24, bottom: 40, left: 48 };
const CHART_H = 380;

function Chart({ width }: { width: number }) {
  const theme = useThemeColors();
  const [hover, setHover] = useState<ConvRow | null>(null);
  const innerW = width - MARGIN.left - MARGIN.right;
  const innerH = CHART_H - MARGIN.top - MARGIN.bottom;

  const xScale = useMemo(
    () => scaleLinear({ domain: [2007, 2026], range: [0, innerW] }),
    [innerW],
  );
  const yScale = useMemo(
    () => scaleLinear({ domain: [0, 16], range: [innerH, 0] }),
    [innerH],
  );

  if (width < 10) return null;
  const c = theme.chartContrast[0];

  return (
    <svg width={width} height={CHART_H} role="img"
      aria-label="Projects per 100 favorites by publication year: about 8.5 for patterns published in 2007, halved by 2014, around 3.5 since. Years after 2023 are shaded because young patterns are still converting.">
      <Group left={MARGIN.left} top={MARGIN.top}>
        <GridRows scale={yScale} width={innerW} stroke={theme.role.muted} strokeOpacity={0.18} />

        {/* still-converting zone: young patterns' projects lag */}
        <rect x={xScale(LAG_FROM - 0.5)} y={0}
          width={xScale(2026) - xScale(LAG_FROM - 0.5)} height={innerH}
          fill={theme.role.muted} opacity={0.1} />
        <text x={xScale(LAG_FROM - 0.35)} y={14} fontSize={10}
          fill={theme.role.muted}>
          still converting —
        </text>
        <text x={xScale(LAG_FROM - 0.35)} y={27} fontSize={10}
          fill={theme.role.muted}>
          young patterns lag
        </text>

        <AreaClosed
          data={ROWS}
          x={(d) => xScale(d.year)}
          y0={(d) => yScale(d.q25)}
          y1={(d) => yScale(d.q75)}
          yScale={yScale}
          fill={c}
          opacity={0.14}
          curve={curveMonotoneX}
        />
        <LinePath
          data={ROWS}
          x={(d) => xScale(d.year)}
          y={(d) => yScale(d.median)}
          stroke={c}
          strokeWidth={2.5}
          curve={curveMonotoneX}
        />
        {ROWS.map((d) => (
          <circle key={d.year} cx={xScale(d.year)} cy={yScale(d.median)}
            r={hover?.year === d.year ? 4.5 : 3} fill={c}
            stroke="var(--background)" strokeWidth={1}
            onMouseEnter={() => setHover(d)}
            onMouseLeave={() => setHover(null)} />
        ))}

        {(() => {
          const y07 = ROWS.find((d) => d.year === 2007);
          const y22 = ROWS.find((d) => d.year === 2022);
          return (
            <>
              {y07 && (
                <text x={xScale(2007) + 8} y={yScale(y07.median) - 10}
                  fontSize={11} fontWeight={600} fill={c}>
                  2007: {Math.round(y07.median)} of 100 admirers cast on
                </text>
              )}
              {y22 && (
                <text x={xScale(2022) - 8} y={yScale(y22.median) - 14}
                  fontSize={11} fontWeight={600} fill={c} textAnchor="end">
                  2022: {y22.median} of 100
                </text>
              )}
            </>
          );
        })()}

        {hover && (
          <text x={xScale(hover.year)} y={yScale(hover.q75) - 8}
            fontSize={10} textAnchor="middle" fill={theme.role.muted}>
            {hover.year}: median {hover.median} per 100 (middle half {hover.q25}–{hover.q75}, n={hover.n})
          </text>
        )}

        <AxisLeft scale={yScale} numTicks={5}
          stroke={theme.role.muted} tickStroke={theme.role.muted}
          tickLabelProps={{ fill: theme.role.muted, fontSize: 11, textAnchor: "end", dx: -4 }} />
        <AxisBottom top={innerH} scale={xScale}
          tickValues={[2008, 2012, 2016, 2020, 2024]}
          tickFormat={(v) => String(v)}
          stroke={theme.role.muted} tickStroke={theme.role.muted}
          tickLabelProps={{ fill: theme.role.muted, fontSize: 11, textAnchor: "middle" }} />
        <text x={innerW / 2} y={innerH + 34} fontSize={11} textAnchor="middle"
          fill={theme.role.muted}>
          year the pattern was published
        </text>
      </Group>
    </svg>
  );
}

export default function ConversionChart() {
  return (
    <figure id="conversion-chart" className="w-full">
      <figcaption className="mb-3">
        <h2 className="text-lg font-semibold">The share of admirers who cast on</h2>
        <p className="text-sm" style={{ color: "var(--muted)" }}>
          Of every 100 users who favorited a pattern, how many started a
          project? Median across patterns by publication year, with the middle
          half of patterns shaded.
        </p>
      </figcaption>
      <div className="h-[380px] w-full">
        <ParentSize>{({ width }) => <Chart width={width} />}</ParentSize>
      </div>
      <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
        Source: full catalogs of the 18 rule-selected designers, patterns with
        100+ favorites (n per year: 83–795). Recent years shaded: projects
        accumulate more slowly than favorites, so young patterns' rates are
        not yet comparable.
      </p>
    </figure>
  );
}
