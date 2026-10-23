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
export interface OwnerEvent { id: number; name: string; date: string; t: number; buyer: string; buyer_type: "pe" | "pe_backed" | "private"; kind: "sold" | "backed"; note: string; source: string; confirmed: boolean; first_pe: boolean }
/* ownership changes with dated press coverage; unconfirmed ones stay in
   the data but off the chart. The chart marks one event per brand: its
   first sale to a private-equity firm or to a company one owned. */
export const EVENTS: OwnerEvent[] = (brandData.events as OwnerEvent[]).filter((e) => e.confirmed);
const PE_EVENT = new Map<number, OwnerEvent>(EVENTS.filter((e) => e.first_pe && e.t >= YEARS[0]).map((e) => [e.id, e]));
const BUYER_TYPE = { pe: "private-equity firm", pe_backed: "private-equity-owned company", private: "private owner" };
const BY_ID = new Map(COMPANIES.map((c) => [c.id, c]));

const MAX_SELECTED = 6;
const idsOf = (names: string[]) => names
  .map((n) => COMPANIES.find((c) => c.name === n)?.id)
  .filter((id): id is number => id !== undefined);

/* Casts for the stories in the write-up; the first is the default. "sale"
   is Knit Picks against the control basket of mass brands from the notes;
   "dyers" the hand-dyed cycles; "risers" the brands still climbing after a
   decade and more. */
/* A preset may give brands a role instead of a slot colour: the brand the
   story is about takes --series-focus and its peers --series-context, so the
   question is visible before the labels are read. */
export const PRESETS: { key: string; label: string; names: string[]; roles?: Record<string, string>; sales?: boolean }[] = [
  /* the six biggest panel brands sold to private equity; the only story
     that draws the sale markers */
  { key: "sold", label: "sold to private equity", names: ["Knit Picks", "madelinetosh", "Berroco", "Regia", "Rowan", "Red Heart"], sales: true },
  /* the control basket from the notes, with Plymouth in place of Berroco,
     which has shared Knit Picks's owner since 2021 */
  { key: "sale", label: "Knit Picks and its peers", names: ["Knit Picks", "Cascade Yarns", "Garnstudio", "Plymouth Yarn", "Lion Brand", "Patons North America"],
    roles: { "Knit Picks": "--series-focus", "Cascade Yarns": "--series-context", "Garnstudio": "--series-context", "Plymouth Yarn": "--series-context", "Lion Brand": "--series-context", "Patons North America": "--series-context" } },
  { key: "dyers", label: "hand-dyed cycles", names: ["Noro", "Rohrspatz & Wollmeise", "Lorna's Laces", "madelinetosh", "Hedgehog Fibres", "Spincycle Yarns"] },
  /* peaks in 2024 or 2025 and up on 2016 and 2019; Berroco has grown since its sale */
  { key: "risers", label: "still rising", names: ["Malabrigo Yarn", "Garnstudio", "Berroco", "Lang Yarns", "West Yorkshire Spinners", "Hobbii"] },
  /* the Danish brands arriving with the Scandinavian designs, with Norway's
     Sandnes for comparison; Garnstudio is left out because it has been
     large since 2008 and would flatten the rest */
  { key: "nordic", label: "the Danish wave", names: ["Hobbii", "Knitting for Olive", "Filcolana", "Holst Garn", "Isager Yarn", "Sandnes Garn"] },
  /* the class of 2008: peaking as the panel starts, under half of that by 2016 */
  { key: "socks", label: "the class of 2008", names: ["Noro", "Debbie Bliss", "Blue Moon Fiber Arts", "Lorna's Laces", "Rohrspatz & Wollmeise", "Koigu"] },
  /* the next big brand? the brands that first reached a tenth of a percent
     after 2015 and have grown fastest since 2022; Hobbii leads, and took
     growth-equity money from Verdane in 2022 */
  { key: "next", label: "the next big brand?", names: ["Hobbii", "Juniper Moon Farm", "Purl Soho", "Farmer's Daughter Fibers", "Cardiff Cashmere", "Laines du Nord"] },
  /* the craft-store shelf: Red Heart and Bernat giving way to the stores' own labels */
  { key: "bigbox", label: "the craft-store shelf", names: ["Lion Brand", "Patons North America", "Red Heart", "Caron", "Loops & Threads", "Yarn Bee"] },
];
const DEFAULT_IDS = idsOf(PRESETS[0].names);

/* Six categorical line colours, one per picker slot (see --series-* in
   globals.css). A brand keeps its slot, and so its colour, until removed. */
const SLOT_TOKENS = [1, 2, 3, 4, 5, 6].map((i) => `--series-${i}`);

type Roles = Map<number, string>;
const rolesOf = (p: { names: string[]; roles?: Record<string, string> }): Roles =>
  new Map(Object.entries(p.roles ?? {}).flatMap(([n, t]) => { const id = idsOf([n])[0]; return id === undefined ? [] : [[id, t]]; }));

const MARGIN = { top: 20, right: 184, bottom: 40, left: 44 };

/** a brand's index at a fractional year, linear between the two surrounding years */
function indexAt(c: Company, t: number): number {
  const i = Math.max(0, Math.min(c.series.length - 2, Math.floor(t) - YEARS[0]));
  const f = Math.max(0, Math.min(1, t - YEARS[i]));
  return c.series[i].index + (c.series[i + 1].index - c.series[i].index) * f;
}
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

interface ChartProps { width: number; slots: (number | null)[]; roles: Roles; sales: boolean; article: boolean }

function Chart({ width, slots, roles, sales, article }: ChartProps) {
  const theme = useThemeColors();
  const { showTooltip, hideTooltip, tooltipData, tooltipLeft, tooltipTop } =
    useTooltip<number>();
  const innerW = width - MARGIN.left - MARGIN.right;

  const lines = useMemo(
    () => slots.flatMap((id, i) => (id === null ? [] : [{ company: BY_ID.get(id)!, slot: i }])),
    [slots],
  );
  const xScale = useMemo(
    () => scaleLinear({ domain: [YEARS[0], YEARS[YEARS.length - 1]], range: [0, Math.max(1, innerW)] }),
    [innerW],
  );

  /* one marker per selected brand, at its first private-equity sale, on
     the brand's own line and tagged with its name and the year */
  type Marker = { e: OwnerEvent; line: typeof lines[number]; x: number };
  const markers: Marker[] = !sales ? [] : lines
    .flatMap((l) => { const e = PE_EVENT.get(l.company.id); return e ? [{ e, line: l, x: xScale(e.t) }] : []; })
    .sort((a, b) => a.e.t - b.e.t);
  const top = MARGIN.top;
  const innerH = CHART_H - top - MARGIN.bottom;
  const yMax = useMemo(() => {
    const m = Math.max(0.01, ...lines.flatMap((l) => l.company.series.map((p) => p.index)));
    const step = m > 0.05 ? 0.02 : 0.01;
    return Math.ceil(m / step) * step;
  }, [lines]);

  const yScale = useMemo(() => scaleLinear({ domain: [0, yMax], range: [innerH, 0] }), [innerH, yMax]);

  if (width < 10) return null;
  const colour = (slot: number, id?: number) => theme.resolve((id !== undefined && roles.get(id)) || SLOT_TOKENS[slot]);
  const isContext = (id: number) => roles.get(id) === "--series-context";
  const shownEventsAt = (year: number) =>
    !sales ? [] : EVENTS.filter((e) => Math.floor(e.t) === year && lines.some((l) => l.company.id === e.id));
  const last = YEARS[YEARS.length - 1];

  const labelY = spreadLabels(
    lines.map((l) => ({ id: l.company.id, y: yScale(l.company.series[l.company.series.length - 1].index) })),
    innerH,
  );

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
        <Group left={MARGIN.left} top={top}>
          <GridRows scale={yScale} width={innerW} stroke={theme.role.muted} strokeOpacity={0.18} />

          {lines.map((l) => {
            const c = colour(l.slot, l.company.id);
            const quiet = isContext(l.company.id);
            const ly = labelY.get(l.company.id) ?? 0;
            return (
              <Group key={l.company.id}>
                <LinePath<Point> data={l.company.series} curve={curveMonotoneX}
                  x={(p) => xScale(p.year)} y={(p) => yScale(p.index)}
                  stroke={c} strokeWidth={quiet ? 1.5 : 2.25}
                  strokeLinejoin="round" strokeLinecap="round" />
                {/* end label in ink; the dot carries identity */}
                <circle cx={innerW + 10} cy={ly} r={3.5} fill={c} />
                <text x={innerW + 18} y={ly + 4} fontSize={11.5} fontWeight={quiet ? 500 : 600}
                  fill={quiet ? theme.role.muted : "var(--foreground)"}>
                  {l.company.name}
                </text>
              </Group>
            );
          })}

          {/* ownership changes: a ringed dot on the line at the sale month with a
              dotted drop line to the axis, tagged with brand and year; each tag
              takes the first of above / below / further out that does not
              overlap a tag already placed */}
          {(() => {
            const placed: { x: number; y: number; w: number }[] = [];
            const TAG_H = 11;
            return markers.map((m) => {
              const c = colour(m.line.slot, m.line.company.id);
              const cy = yScale(indexAt(m.line.company, m.e.t));
              const tag = `${m.e.name} ${m.e.kind === "backed" ? "backed" : "sold"} ${Math.floor(m.e.t)}`;
              const w = tag.length * 5.6;
              const options = [cy - 10, cy + 17, cy - 22, cy + 29, cy - 34];
              const ty = options.find((y) => !placed.some((p) => Math.abs(p.x - m.x) < (p.w + w) / 2 && Math.abs(p.y - y) < TAG_H)) ?? options[0];
              placed.push({ x: m.x, y: ty, w });
              /* keep the tag inside the plot */
              const tx = Math.min(innerW - w / 2, Math.max(w / 2, m.x));
              return (
              <Group key={`${m.e.id}-${m.e.date}`}>
                {/* drop line: divides this brand's time into before and after, and stops at its line */}
                <line x1={m.x} x2={m.x} y1={cy + 6.5} y2={innerH} stroke={c} strokeWidth={1.25} strokeDasharray="2 3" strokeOpacity={0.8} />
                <circle cx={m.x} cy={cy} r={6.5} fill="var(--background)" stroke={c} strokeWidth={1.5} />
                <circle cx={m.x} cy={cy} r={3} fill={c} />
                <text x={tx} y={ty} fontSize={10} fontWeight={600} textAnchor="middle" fill="var(--foreground)"
                  style={{ paintOrder: "stroke", stroke: "var(--background)", strokeWidth: 3, strokeLinejoin: "round" }}>
                  {tag}
                </text>
              </Group>
              );
            });
          })()}

          {/* crosshair */}
          {tooltipData !== undefined && (
            <Group>
              <line x1={xScale(tooltipData)} x2={xScale(tooltipData)} y1={0} y2={innerH}
                stroke={theme.role.muted} strokeOpacity={0.6} />
              {hoverRows.map((r) => (
                <circle key={r.company.id} cx={xScale(tooltipData)} cy={yScale(r.point.index)} r={4}
                  fill={colour(r.slot, r.company.id)} stroke="var(--background)" strokeWidth={1.5} />
              ))}
            </Group>
          )}

          <AxisLeft scale={yScale} numTicks={5}
            tickFormat={(v) => pct(Number(v), yMax <= 0.05 ? 1 : 0)}
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
                <i className="inline-block h-2 w-2 rounded-full" style={{ background: colour(r.slot, r.company.id) }} />
                {r.company.name}
              </span>
              <span className="ml-auto">{pct(r.point.index)}</span>
            </div>
          ))}
          {shownEventsAt(tooltipData).map((e) => (
            <div key={`${e.id}-${e.date}`} className="mt-1" style={{ color: theme.role.muted }}>
              {e.name} {e.kind === "backed" ? "backed by" : "sold to"} {e.buyer}
            </div>
          ))}
        </TooltipWithBounds>
      )}
    </div>
  );
}

interface PickerProps { slots: (number | null)[]; roles: Roles; onChange: (ids: number[]) => void }

function Picker({ slots, roles, onChange }: PickerProps) {
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

  const chipStyle = { borderColor: "color-mix(in srgb, var(--muted) 40%, transparent)", background: "var(--surface-chip)" };

  return (
    <div ref={wrap} className="mb-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        {slots.map((id, i) => id === null ? null : (
          <span key={id} className="inline-flex items-center gap-1.5 rounded-full border py-0.5 pl-2 pr-1" style={chipStyle}>
            <i className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: `var(${roles.get(id) ?? SLOT_TOKENS[i]})` }} />
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
            className="w-full rounded-md border bg-transparent px-2.5 py-1 outline-none focus:border-[var(--primary)] disabled:opacity-60"
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
  const [roles, setRoles] = useState<Roles>(() => new Map());
  /* sale markers belong to the private-equity story; picker edits keep
     whatever the last story set */
  const [sales, setSales] = useState<boolean>(() => Boolean(PRESETS[0].sales));
  const loadPreset = (p: typeof PRESETS[number]) => {
    setSlots(assignSlots(Array(MAX_SELECTED).fill(null), idsOf(p.names)));
    setRoles(rolesOf(p));
    setSales(Boolean(p.sales));
  };
  /* picker edits keep a role only for brands still selected */
  const changeSelection = (ids: number[]) => {
    setSlots((prev) => assignSlots(prev, ids));
    setRoles((prev) => new Map([...prev].filter(([id]) => ids.includes(id))));
  };
  /* ?preset=sale|dyers|risers loads a story's cast (used by the screenshot
     script for the article variant) */
  useEffect(() => {
    const key = new URLSearchParams(window.location.search).get("preset");
    const preset = PRESETS.find((p) => p.key === key);
    if (preset) loadPreset(preset);
  }, []);
  const lines = slots.flatMap((id, i) => (id === null ? [] : [{ company: BY_ID.get(id)!, slot: i }]));
  const shownIds = new Set(lines.map((l) => l.company.id));
  const shownEvents = sales ? EVENTS.filter((e) => shownIds.has(e.id)) : [];
  const first = COVERAGE[0];
  const latest = COVERAGE[COVERAGE.length - 1];

  return (
    <figure id="yarn-brand-grapher" className={article ? "w-full" : "w-full rounded-lg p-4"}
      style={article ? undefined : { background: "var(--surface-figure)" }}>
      <figcaption className="mb-3">
        <h2 className="text-lg font-semibold">Which yarn brands knitters chose</h2>
        <p className="text-sm" style={{ color: "var(--muted)" }}>
          Share of projects on 25 long-lived patterns that used each brand, by
          the year the project was started, {YEARS[0]} to {YEARS[YEARS.length - 1]}.
          {sales && "A ringed dot marks the month a brand was first sold to a private-equity owner. "}
          {!article && " Pick up to six brands; hover for the numbers."}
        </p>
      </figcaption>
      {!article && <Picker slots={slots} roles={roles} onChange={changeSelection} />}
      {!article && (
        <div className="mb-3 flex flex-wrap items-center gap-2 text-xs" style={{ color: "var(--muted)" }}>
          <span>stories:</span>
          {PRESETS.map((p) => (
            <button key={p.key} type="button"
              onClick={() => loadPreset(p)}
              className="rounded-full border px-2.5 py-0.5 hover:border-[var(--primary)]"
              style={{ borderColor: "color-mix(in srgb, var(--muted) 40%, transparent)", color: "var(--foreground)" }}>
              {p.label}
            </button>
          ))}
        </div>
      )}
      <ParentSize>{({ width }) => <Chart width={width} slots={slots} roles={roles} sales={sales} article={article} />}</ParentSize>
      {shownEvents.length > 0 && (
        <div className="mt-1 flex items-center gap-1.5 text-xs" style={{ color: "var(--muted)" }}>
          <svg width={14} height={20} aria-hidden="true">
            <line x1={7} x2={7} y1={12} y2={20} stroke="currentColor" strokeWidth={1.25} strokeDasharray="2 3" />
            <circle cx={7} cy={7} r={5.5} fill="var(--background)" stroke="currentColor" strokeWidth={1.5} />
            <circle cx={7} cy={7} r={2.5} fill="currentColor" />
          </svg>
          the month of the brand's first sale to a private-equity owner
        </div>
      )}

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

      {!article && shownEvents.length > 0 && <details className="mt-2 text-xs">
        <summary className="cursor-pointer" style={{ color: "var(--muted)" }}>Ownership changes for the brands shown</summary>
        <table className="mt-2 w-full" style={{ borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ color: "var(--muted)" }}>
              <th className="py-1 text-left font-medium">brand</th>
              <th className="py-1 text-left font-medium">when</th>
              <th className="py-1 text-left font-medium">to</th>
              <th className="py-1 text-left font-medium">buyer</th>
              <th className="py-1 text-left font-medium">what happened</th>
            </tr>
          </thead>
          <tbody>
            {shownEvents.map((e) => (
              <tr key={`${e.id}-${e.date}`} style={{ borderTop: "1px solid color-mix(in srgb, var(--muted) 30%, transparent)" }}>
                <td className="py-1 pr-3">{e.name}</td>
                <td className="py-1 pr-3 whitespace-nowrap">{e.date}</td>
                <td className="py-1 pr-3">{e.buyer}</td>
                <td className="py-1 pr-3 whitespace-nowrap">{BUYER_TYPE[e.buyer_type]}{e.first_pe ? " ●" : ""}</td>
                <td className="py-1">{e.note}{e.source && <> <a href={e.source} style={{ color: "var(--muted)" }}>source</a></>}</td>
              </tr>
            ))}
          </tbody>
        </table>
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
          {" "}{pct(latest.with_brand, 0)} of {latest.year}.{" "}
          {sales && <>On the private-equity story, each marker sits at the announced month of
          the brand's first sale to a private-equity firm, or to a company one owned; later
          sales and sales to private owners are in the table above (● marks the one
          drawn). Patons North America, Bernat and Caron have no marker because their
          parent, Spinrite, was already private-equity-owned before {YEARS[0]}.</>} Sales resting on a single secondary report are
          left off the chart.
        </p>
      )}
    </figure>
  );
}
