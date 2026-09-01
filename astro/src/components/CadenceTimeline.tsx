"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AxisBottom } from "@visx/axis";
import { ParentSize } from "@visx/responsive";
import { scaleLinear } from "@visx/scale";
import { TooltipWithBounds, useTooltip } from "@visx/tooltip";
import { quadtree } from "d3-quadtree";
import { useThemeColors } from "@/lib/themeColors";
import cadenceData from "@/data/cadence.json";

/* The flagship chart: every pattern released by the 18 rule-selected
   designers, one dot per pattern, sized by favorites. ~4.9k dots, so
   the dot layer is Canvas 2D; axes, labels, and milestones stay SVG
   (visx) on top, sharing the same scales. */

interface Designer {
  name: string;
  badges: string;
  patterns: [string, number, string][]; // ["YYYY-MM", favorites, pattern name]
}

const DESIGNERS: Designer[] = cadenceData.designers as Designer[];
const MILESTONES: [number, string][] = cadenceData.milestones as [number, string][];

const MARGIN = { top: 148, right: 24, bottom: 36, left: 176 }; // top holds the vertical milestone labels
const ROW_H = 34;
const X_MIN = 2005;
const X_MAX = 2026.7;

interface Dot {
  x: number; // screen px
  y: number;
  r: number;
  designer: string;
  month: string;
  favorites: number;
  pattern: string;
}

/** Deterministic PRNG so jitter is identical across renders and screenshots. */
function mulberry32(seed: number) {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function decimalYear(month: string): number {
  const [y, m] = month.split("-").map(Number);
  return y + (m - 0.5) / 12;
}

function Chart({ width }: { width: number }) {
  const theme = useThemeColors();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [dots, setDots] = useState<Dot[]>([]);
  const { showTooltip, hideTooltip, tooltipData, tooltipLeft, tooltipTop } =
    useTooltip<Dot>();

  const innerW = width - MARGIN.left - MARGIN.right;
  const innerH = DESIGNERS.length * ROW_H;
  const height = innerH + MARGIN.top + MARGIN.bottom;

  const xScale = useMemo(
    () => scaleLinear({ domain: [X_MIN, X_MAX], range: [0, innerW] }),
    [innerW],
  );
  const rowY = (i: number) => i * ROW_H + ROW_H / 2;

  // draw the dot layer whenever geometry or theme changes
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || innerW <= 0) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = innerW * dpr;
    canvas.height = innerH * dpr;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, innerW, innerH);
    ctx.globalAlpha = 0.55;

    const rand = mulberry32(2);
    const next: Dot[] = [];
    DESIGNERS.forEach((d, i) => {
      ctx.fillStyle = theme.chart[i % theme.chart.length];
      for (const [month, favorites, pattern] of d.patterns) {
        const x = xScale(decimalYear(month));
        const y = rowY(i) + (rand() * 2 - 1) * (ROW_H * 0.32);
        const r = 1.5 + Math.sqrt(favorites) * 0.028;
        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fill();
        next.push({ x, y, r, designer: d.name, month, favorites, pattern });
      }
    });
    setDots(next);
  }, [innerW, innerH, xScale, theme]);

  const tree = useMemo(
    () =>
      quadtree<Dot>()
        .x((d) => d.x)
        .y((d) => d.y)
        .addAll(dots),
    [dots],
  );

  const onMove = (event: React.PointerEvent<SVGRectElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const px = event.clientX - rect.left;
    const py = event.clientY - rect.top;
    const hit = tree.find(px, py, 10);
    if (!hit) return hideTooltip();
    showTooltip({
      tooltipData: hit,
      tooltipLeft: MARGIN.left + hit.x,
      tooltipTop: MARGIN.top + hit.y,
    });
  };

  if (width < 10) return null;

  return (
    <div className="relative" style={{ height }}>
      <canvas
        ref={canvasRef}
        className="pointer-events-none absolute"
        style={{ left: MARGIN.left, top: MARGIN.top, width: innerW, height: innerH }}
      />
      <svg width={width} height={height} className="absolute inset-0" role="img"
        aria-label="Timeline of every pattern released by 18 rule-selected knitting designers, 2005 to 2026, one row per designer sorted by entrance date, one dot per pattern sized by how many users favorited it.">
        <g transform={`translate(${MARGIN.left},${MARGIN.top})`}>
          {DESIGNERS.map((d, i) => (
            <g key={d.name}>
              {i % 2 === 1 && (
                <rect x={0} y={i * ROW_H} width={innerW} height={ROW_H}
                  fill={theme.role.muted} opacity={0.06} />
              )}
              <text x={-10} y={rowY(i) + 4} textAnchor="end" fontSize={11}
                fill="var(--foreground)">
                {d.name}
                <tspan fill={theme.role.muted} fontSize={9}>
                  {"  " + d.badges}
                </tspan>
              </text>
            </g>
          ))}

          {MILESTONES.map(([year, label]) => (
            <g key={year}>
              <line x1={xScale(year)} x2={xScale(year)} y1={0} y2={innerH}
                stroke={theme.role.muted} strokeDasharray="5 4"
                strokeWidth={1} opacity={0.6} />
              {/* vertical label in the reserved top band — clear of the
                  dot field entirely, rotated to survive the 2016-2020
                  marker cluster */}
              <text fontSize={10} fill={theme.role.muted}
                transform={`rotate(-90 ${xScale(year)} -8)`}
                x={xScale(year) + 4} y={-8} textAnchor="start">
                {label}
              </text>
            </g>
          ))}

          {tooltipData && (
            <circle cx={tooltipData.x} cy={tooltipData.y}
              r={tooltipData.r + 2} fill="none"
              stroke="var(--foreground)" strokeWidth={1.25} />
          )}

          <AxisBottom
            top={innerH}
            scale={xScale}
            tickValues={[2006, 2010, 2014, 2018, 2022, 2026]}
            tickFormat={(v) => String(v)}
            stroke={theme.role.muted}
            tickStroke={theme.role.muted}
            tickLabelProps={{ fill: theme.role.muted, fontSize: 11, textAnchor: "middle" }}
          />

          <rect width={innerW} height={innerH} fill="transparent"
            onPointerMove={onMove} onPointerLeave={hideTooltip} />
        </g>
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
          <div className="font-semibold">{tooltipData.pattern || "(untitled)"}</div>
          <div>
            {tooltipData.designer} · {tooltipData.month}
          </div>
          <div style={{ color: theme.role.muted }}>
            favorited by {tooltipData.favorites.toLocaleString()} users
          </div>
        </TooltipWithBounds>
      )}
    </div>
  );
}

export default function CadenceTimeline() {
  return (
    <figure id="cadence-chart" className="w-full">
      <figcaption className="mb-3">
        <h2 className="text-lg font-semibold">What success took, by era of entry</h2>
        <p className="text-sm" style={{ color: "var(--muted)" }}>
          Every pattern released by the rule-selected cast — one dot per pattern,
          sized by favorites, rows sorted by entrance. Badges: C cohort champion ·
          F 20k+ designer fans · K KnitStars faculty · E 3+ prestige-venue
          patterns.
        </p>
      </figcaption>
      <ParentSize>{({ width }) => <Chart width={width} />}</ParentSize>
      <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
        Source: Ravelry pattern registry, full catalogs of 18 designers selected
        by mechanical rule (2+ badges); pattern favorite counts as of August 2026.
      </p>
    </figure>
  );
}
