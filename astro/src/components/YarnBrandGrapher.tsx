"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AxisBottom, AxisLeft } from "@visx/axis";
import { curveMonotoneX } from "@visx/curve";
import { localPoint } from "@visx/event";
import { GridRows } from "@visx/grid";
import { Group } from "@visx/group";
import { ParentSize } from "@visx/responsive";
import { scaleLinear } from "@visx/scale";
import { LinePath } from "@visx/shape";
import { TooltipWithBounds, useTooltip } from "@visx/tooltip";
import { useThemeColors } from "@/lib/themeColors";
import { useVariant } from "@/lib/variant";
import brandData from "@/data/yarn_brands.json";

/* Yarn-brand share over time, baby-name-grapher style: pick up to six
   brands and see each one's panel index by year. The index is the share of
   projects that used the brand, measured within each of 25 long-lived
   patterns by project start year and averaged across patterns with equal
   weight, so a pattern's own rise and fall does not move the line. Only
   projects whose yarn is linked to Ravelry's yarn database are in the
   denominator. */

interface Point { year: number; index: number; pooled: number; n: number }
export interface Company { id: number; name: string; total: number; series: Point[] }
interface Coverage { year: number; projects: number; with_packs: number; with_brand: number; n_patterns: number }

const META = brandData.meta;
const YEARS: number[] = META.years_list;
/* the JSON stores each company's series as parallel arrays over META.years_list */
export const COMPANIES: Company[] = brandData.companies.map((c) => ({
  id: c.id, name: c.name, total: c.total,
  series: YEARS.map((year, i) => ({ year, index: c.index[i], pooled: c.pooled[i], n: c.n[i] })),
}));
const COVERAGE: Coverage[] = brandData.coverage as Coverage[];
const BY_ID = new Map(COMPANIES.map((c) => [c.id, c]));

const MAX_SELECTED = 6;
const idsOf = (names: string[]) => names
  .map((n) => COMPANIES.find((c) => c.name === n)?.id)
  .filter((id): id is number => id !== undefined);

/* Casts for the three stories in the write-up. The default is one brand of
   each trajectory type: the brand in question, a slow riser, a slowly
   eroding workhorse, a hand-dyer with a long arc, and a fashion that
   crashed. "sale" is Knit Picks against the control basket of mass brands
   from the notes; "dyers" the hand-dyed cycles; "risers" the brands still
   climbing after a decade and more. */
export const PRESETS: { key: string; label: string; names: string[] }[] = [
  { key: "default", label: "one of each", names: ["Knit Picks", "Malabrigo Yarn", "Cascade Yarns", "madelinetosh", "Noro"] },
  { key: "sale", label: "Knit Picks and its peers", names: ["Knit Picks", "Cascade Yarns", "Garnstudio", "Berroco", "Lion Brand", "Patons North America"] },
  { key: "dyers", label: "hand-dyed cycles", names: ["Noro", "Rohrspatz & Wollmeise", "Lorna's Laces", "madelinetosh", "Hedgehog Fibres"] },
  { key: "risers", label: "still rising", names: ["Malabrigo Yarn", "Garnstudio", "Schoppel-Wolle", "Lang Yarns", "West Yorkshire Spinners"] },
];
const DEFAULT_IDS = idsOf(PRESETS[0].names);

/* Six categorical line colours, one per picker slot (see --brand-line-* in
   globals.css). A brand keeps its slot, and so its colour, until removed. */
const SLOT_TOKENS = [1, 2, 3, 4, 5, 6].map((i) => `--brand-line-${i}`);

const MARGIN = { top: 24, right: 156, bottom: 40, left: 44 };
const CHART_H = 400;
const LABEL_H = 14;

const pct = (v: number, d = 1) => `${(100 * v).toFixed(d)}%`;
const fmt = (n: number) => n.toLocaleString("en-US");

/** Keep a list of ids in slots: removals free a slot, additions take the first free one. */
function assignSlots(prev: (number | null)[], ids: number[]): (number | null)[] {
  const slots = prev.map((id) => (id !== null && ids.includes(id) ? id : null));
  for (const id of ids) {
    if (slots.includes(id)) continue;
    const free = slots.indexOf(null);
    if (free >= 0) slots[free] = id;
  }
  return slots;
}

/** Push overlapping end labels apart so none sit closer than LABEL_H. */
function spreadLabels(items: { id: number; y: number }[], maxY: number) {
  const sorted = [...items].sort((a, b) => a.y - b.y);
  for (let i = 1; i < sorted.length; i++) {
    if (sorted[i].y - sorted[i - 1].y < LABEL_H) sorted[i].y = sorted[i - 1].y + LABEL_H;
  }
  // if the last one overflowed the bottom, shift the chain back up
  const overflow = sorted.length ? sorted[sorted.length - 1].y - maxY : 0;
  if (overflow > 0) {
    for (let i = sorted.length - 1; i >= 0; i--) {
      sorted[i].y -= overflow;
      if (i > 0 && sorted[i].y - sorted[i - 1].y >= LABEL_H) break;
    }
  }
  return new Map(sorted.map((s) => [s.id, s.y]));
}

interface ChartProps { width: number; slots: (number | null)[]; article: boolean }

function Chart({ width, slots, article }: ChartProps) {
  const theme = useThemeColors();
  const { showTooltip, hideTooltip, tooltipData, tooltipLeft, tooltipTop } =
    useTooltip<number>();
  const innerW = width - MARGIN.left - MARGIN.right;
  const innerH = CHART_H - MARGIN.top - MARGIN.bottom;

  const lines = useMemo(
    () => slots.flatMap((id, i) => (id === null ? [] : [{ company: BY_ID.get(id)!, slot: i }])),
    [slots],
  );
  const yMax = useMemo(() => {
    const m = Math.max(0.01, ...lines.flatMap((l) => l.company.series.map((p) => p.index)));
    const step = m > 0.05 ? 0.02 : 0.01;
    return Math.ceil(m / step) * step;
  }, [lines]);

  const xScale = useMemo(
    () => scaleLinear({ domain: [YEARS[0], YEARS[YEARS.length - 1]], range: [0, innerW] }),
    [innerW],
  );
  const yScale = useMemo(() => scaleLinear({ domain: [0, yMax], range: [innerH, 0] }), [innerH, yMax]);

  if (width < 10) return null;
  const colour = (slot: number) => theme.resolve(SLOT_TOKENS[slot]);
  const last = YEARS[YEARS.length - 1];
  const labelY = spreadLabels(
    lines.map((l) => ({ id: l.company.id, y: yScale(l.company.series[l.company.series.length - 1].index) })),
    innerH,
  );
  const acquiredX = xScale(META.acquired);

  const onMove = (e: React.PointerEvent<SVGRectElement>) => {
    const p = localPoint(e);
    if (!p) return;
    const year = Math.round(xScale.invert(p.x - MARGIN.left));
    const y = Math.min(last, Math.max(YEARS[0], year));
    showTooltip({ tooltipData: y, tooltipLeft: MARGIN.left + xScale(y), tooltipTop: p.y });
  };

  const hoverRows = tooltipData === undefined ? [] : lines
    .map((l) => ({ ...l, point: l.company.series.find((p) => p.year === tooltipData)! }))
    .sort((a, b) => b.point.index - a.point.index);

  const names = lines.map((l) => l.company.name).join(", ");

  return (
    <div className="relative">
      <svg width={width} height={CHART_H} role="img"
        aria-label={`Panel share of ${names || "no brands"} by project start year, ${YEARS[0]} to ${last}.`}>
        <Group left={MARGIN.left} top={MARGIN.top}>
          <GridRows scale={yScale} width={innerW} stroke={theme.role.muted} strokeOpacity={0.18} />

          {/* acquisition marker */}
          <line x1={acquiredX} x2={acquiredX} y1={0} y2={innerH}
            stroke={theme.role.muted} strokeDasharray="4 4" strokeWidth={1} />
          <text x={acquiredX + 5} y={10} fontSize={11} fill={theme.role.muted}>
            Knit Picks sold
          </text>

          {lines.map((l) => {
            const c = colour(l.slot);
            return (
              <Group key={l.company.id}>
                <LinePath<Point> data={l.company.series} curve={curveMonotoneX}
                  x={(p) => xScale(p.year)} y={(p) => yScale(p.index)}
                  stroke={c} strokeWidth={2.25}
                  strokeLinejoin="round" strokeLinecap="round" />
                <text x={innerW + 8} y={(labelY.get(l.company.id) ?? 0) + 4}
                  fontSize={11.5} fontWeight={600} fill={c}>
                  {l.company.name}
                </text>
              </Group>
            );
          })}

          {/* crosshair */}
          {tooltipData !== undefined && (
            <Group>
              <line x1={xScale(tooltipData)} x2={xScale(tooltipData)} y1={0} y2={innerH}
                stroke={theme.role.muted} strokeOpacity={0.6} />
              {hoverRows.map((r) => (
                <circle key={r.company.id} cx={xScale(tooltipData)} cy={yScale(r.point.index)} r={4}
                  fill={colour(r.slot)} stroke="var(--background)" strokeWidth={1.5} />
              ))}
            </Group>
          )}

          <AxisLeft scale={yScale} numTicks={5}
            tickFormat={(v) => pct(Number(v), 0)}
            stroke={theme.role.muted} tickStroke={theme.role.muted}
            tickLabelProps={{ fill: theme.role.muted, fontSize: 11, textAnchor: "end", dx: -4 }} />
          <AxisBottom top={innerH} scale={xScale}
            tickValues={YEARS.filter((y) => y % (innerW < 420 ? 4 : 2) === 0)}
            tickFormat={(v) => String(v)}
            stroke={theme.role.muted} tickStroke={theme.role.muted}
            tickLabelProps={{ fill: theme.role.muted, fontSize: 11, textAnchor: "middle" }} />

          {!article && (
            <rect x={0} y={0} width={innerW} height={innerH} fill="transparent"
              onPointerMove={onMove} onPointerLeave={hideTooltip} />
          )}
        </Group>
      </svg>

      {tooltipData !== undefined && hoverRows.length > 0 && (
        <TooltipWithBounds left={tooltipLeft} top={tooltipTop} className="pointer-events-none"
          style={{ position: "absolute", background: "var(--background)", color: "var(--foreground)",
            border: "1px solid var(--muted)", borderRadius: 6, padding: "8px 10px", fontSize: 12, lineHeight: 1.5 }}>
          <div className="font-semibold">{tooltipData}</div>
          {hoverRows.map((r) => (
            <div key={r.company.id} className="flex items-baseline gap-3 tabular-nums">
              <span className="inline-flex items-center gap-1.5">
                <i className="inline-block h-2 w-2 rounded-full" style={{ background: colour(r.slot) }} />
                {r.company.name}
              </span>
              <span className="ml-auto">{pct(r.point.index)}</span>
            </div>
          ))}
        </TooltipWithBounds>
      )}
    </div>
  );
}

interface PickerProps { slots: (number | null)[]; onChange: (ids: number[]) => void }

function Picker({ slots, onChange }: PickerProps) {
  const theme = useThemeColors();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [cursor, setCursor] = useState(0);
  const wrap = useRef<HTMLDivElement>(null);
  const selected = slots.filter((id): id is number => id !== null);
  const full = selected.length >= MAX_SELECTED;

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    return COMPANIES
      .filter((c) => !selected.includes(c.id) && (q === "" || c.name.toLowerCase().includes(q)))
      .slice(0, 8);
  }, [query, selected]);

  useEffect(() => {
    const close = (e: PointerEvent) => {
      if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, []);

  const add = (id: number) => {
    if (full) return;
    onChange([...selected, id]);
    setQuery("");
    setCursor(0);
  };
  const remove = (id: number) => { onChange(selected.filter((s) => s !== id)); setOpen(false); };

  const onKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setCursor((c) => Math.min(c + 1, matches.length - 1)); setOpen(true); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setCursor((c) => Math.max(c - 1, 0)); }
    else if (e.key === "Enter") { e.preventDefault(); if (matches[cursor]) add(matches[cursor].id); }
    else if (e.key === "Escape") setOpen(false);
    else if (e.key === "Backspace" && query === "" && selected.length) remove(selected[selected.length - 1]);
  };

  const chipStyle = { borderColor: "color-mix(in srgb, var(--muted) 40%, transparent)" };

  return (
    <div ref={wrap} className="mb-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        {slots.map((id, i) => id === null ? null : (
          <span key={id} className="inline-flex items-center gap-1.5 rounded-full border py-0.5 pl-2 pr-1" style={chipStyle}>
            <i className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: `var(${SLOT_TOKENS[i]})` }} />
            {BY_ID.get(id)!.name}
            <button type="button" onClick={() => remove(id)} aria-label={`Remove ${BY_ID.get(id)!.name}`}
              className="ml-0.5 rounded-full px-1 leading-none hover:bg-[color-mix(in_srgb,var(--muted)_25%,transparent)]"
              style={{ color: "var(--muted)" }}>×</button>
          </span>
        ))}
        <div className="relative flex-1" style={{ minWidth: 180 }}>
          <input type="text" value={query} placeholder={full ? `up to ${MAX_SELECTED} brands` : "add a brand…"}
            disabled={full} aria-label="Search brands"
            onChange={(e) => { setQuery(e.target.value); setOpen(true); setCursor(0); }}
            onFocus={() => setOpen(true)} onKeyDown={onKey}
            className="w-full rounded-md border bg-transparent px-2.5 py-1 outline-none focus:border-[var(--origin)] disabled:opacity-60"
            style={chipStyle} />
          {open && !full && matches.length > 0 && (
            <ul role="listbox" className="absolute left-0 z-10 mt-1 w-full overflow-hidden rounded-md border shadow-sm"
              style={{ background: "var(--background)", borderColor: "color-mix(in srgb, var(--muted) 40%, transparent)", maxWidth: 320 }}>
              {matches.map((c, i) => (
                <li key={c.id} role="option" aria-selected={i === cursor}
                  onPointerDown={(e) => { e.preventDefault(); add(c.id); }}
                  onPointerEnter={() => setCursor(i)}
                  className="flex cursor-pointer items-baseline justify-between px-2.5 py-1"
                  style={{ background: i === cursor ? "color-mix(in srgb, var(--muted) 18%, transparent)" : undefined }}>
                  <span>{c.name}</span>
                  <span className="text-xs tabular-nums" style={{ color: "var(--muted)" }}>{fmt(c.total)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

export default function YarnBrandGrapher() {
  const article = useVariant() === "article";
  const [slots, setSlots] = useState<(number | null)[]>(() =>
    assignSlots(Array(MAX_SELECTED).fill(null), DEFAULT_IDS));
  /* ?preset=sale|dyers|risers loads a story's cast (used by the screenshot
     script for the article variant) */
  useEffect(() => {
    const key = new URLSearchParams(window.location.search).get("preset");
    const preset = PRESETS.find((p) => p.key === key);
    if (preset) setSlots(assignSlots(Array(MAX_SELECTED).fill(null), idsOf(preset.names)));
  }, []);
  /* the stacked view below can push a brand into the picker (a window event,
     since the two charts are separate Astro islands); a full picker drops
     its last-added brand to make room */
  useEffect(() => {
    const onAdd = (e: Event) => {
      const id = (e as CustomEvent<{ id: number }>).detail?.id;
      if (id === undefined || !BY_ID.has(id)) return;
      setSlots((prev) => {
        const ids = prev.filter((s): s is number => s !== null);
        if (ids.includes(id)) return prev;
        const next = ids.length >= MAX_SELECTED ? [...ids.slice(0, -1), id] : [...ids, id];
        return assignSlots(prev, next);
      });
      document.getElementById("yarn-brand-grapher")?.scrollIntoView({ behavior: "smooth", block: "start" });
    };
    window.addEventListener("yarn-brands:add", onAdd);
    return () => window.removeEventListener("yarn-brands:add", onAdd);
  }, []);
  const lines = slots.flatMap((id, i) => (id === null ? [] : [{ company: BY_ID.get(id)!, slot: i }]));
  const first = COVERAGE[0];
  const latest = COVERAGE[COVERAGE.length - 1];

  return (
    <figure id="yarn-brand-grapher" className="w-full">
      <figcaption className="mb-3">
        <h2 className="text-lg font-semibold">Which yarn brands knitters chose</h2>
        <p className="text-sm" style={{ color: "var(--muted)" }}>
          Share of projects on 25 long-lived patterns that used each brand, by
          the year the project was started, {YEARS[0]} to {YEARS[YEARS.length - 1]}.
          {!article && " Pick up to six brands; hover for the numbers."}
        </p>
      </figcaption>
      {!article && <Picker slots={slots} onChange={(ids) => setSlots((prev) => assignSlots(prev, ids))} />}
      {!article && (
        <div className="mb-3 flex flex-wrap items-center gap-2 text-xs" style={{ color: "var(--muted)" }}>
          <span>stories:</span>
          {PRESETS.map((p) => (
            <button key={p.key} type="button"
              onClick={() => setSlots(assignSlots(Array(MAX_SELECTED).fill(null), idsOf(p.names)))}
              className="rounded-full border px-2.5 py-0.5 hover:border-[var(--origin)]"
              style={{ borderColor: "color-mix(in srgb, var(--muted) 40%, transparent)", color: "var(--foreground)" }}>
              {p.label}
            </button>
          ))}
        </div>
      )}
      <ParentSize>{({ width }) => <Chart width={width} slots={slots} article={article} />}</ParentSize>

      {!article && lines.length > 0 && <details className="mt-3 text-xs">
        <summary className="cursor-pointer" style={{ color: "var(--muted)" }}>Table view</summary>
        <div className="overflow-x-auto">
          <table className="mt-2 w-full tabular-nums" style={{ borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ color: "var(--muted)" }}>
                <th className="py-1 text-left font-medium">year</th>
                {lines.map((l) => <th key={l.company.id} className="py-1 text-right font-medium">{l.company.name}</th>)}
                <th className="py-1 text-right font-medium">patterns</th>
              </tr>
            </thead>
            <tbody>
              {YEARS.map((y, yi) => (
                <tr key={y} style={{ borderTop: "1px solid color-mix(in srgb, var(--muted) 30%, transparent)" }}>
                  <td className="py-1">{y}</td>
                  {lines.map((l) => <td key={l.company.id} className="py-1 text-right">{pct(l.company.series[yi].index)}</td>)}
                  <td className="py-1 text-right" style={{ color: "var(--muted)" }}>{COVERAGE[yi].n_patterns}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>}

      {!article && (
        <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
          Source: {fmt(META.projects)} Ravelry projects on {META.patterns} patterns and the
          {" "}{fmt(META.packs)} yarns they link, {META.generated}. Each line is the share
          of a pattern's projects that used the brand, averaged with equal weight across
          the patterns with at least {META.min_denom} yarn-linked projects that year
          ({first.n_patterns} patterns in {first.year}, {latest.n_patterns} in {latest.year}),
          so one popular pattern cannot carry a line. Only projects whose yarn is linked
          to Ravelry's yarn database count: {pct(first.with_brand, 0)} of {first.year} projects,
          {" "}{pct(latest.with_brand, 0)} of {latest.year}.
          The dashed line marks February {META.acquired}, when Knit Picks' parent company
          was sold to a private-equity buyer.
        </p>
      )}
    </figure>
  );
}
