"use client";

import { memo, useEffect, useMemo, useRef, useState } from "react";
import { AxisBottom, AxisLeft } from "@visx/axis";
import { curveMonotoneX } from "@visx/curve";
import { localPoint } from "@visx/event";
import { Group } from "@visx/group";
import { ParentSize } from "@visx/responsive";
import { scaleLinear } from "@visx/scale";
import { Area } from "@visx/shape";
import { TooltipWithBounds, useTooltip } from "@visx/tooltip";
import { useThemeColors } from "@/lib/themeColors";
import { useVariant } from "@/lib/variant";
import brandData from "@/data/yarn_brands.json";

/* The stacked view: colour means era. Each named band (a brand with >=
   NAMED_MIN panel projects) takes a step of a one-hue ramp keyed to the
   year it peaked, earliest with the most ink, so the old guard thinning
   under a pale crowd of newcomers is the picture, not an inference. The
   long tail sits on the baseline in two grey tiers (100 to 500 projects,
   and 20 to 100); brands under 20 projects, mostly individual crafters,
   are left out of the stack and its denominator. Shares are the panel
   index normalised to each year's sum over the brands shown.

   Click the 100-500 tier and it fans out: a full-height stack of just
   the brands inside it, each coloured by era, with the same hover and
   click. Click a brand, or search, to see it on its own. */

interface Company { id: number; name: string; total: number; index: number[] }
interface Tier { lo: number; hi: number; label: string; ids: number[]; fan: boolean }
interface Band { id: number; name: string; total: number; v: number[]; peakYear: number; era: number; tier?: Tier }

const META = brandData.meta;
const YEARS: number[] = META.years_list;
const LAST = YEARS.length - 1;
const NAMED_MIN = 500;
const ERAS = [2011, 2014, 2017, 2020, 2023]; // cohort upper bounds; the sixth is open
const ERA_TOKENS = [1, 2, 3, 4, 5, 6].map((i) => `--ramp-${i}`);
const TIER_TOKENS = ["--ramp-tail-2", "--ramp-tail-1"]; /* 100-500, 20-100 */

const COMPANIES: Company[] = brandData.companies as Company[];
const BY_COMPANY = new Map(COMPANIES.map((c) => [c.id, c]));
/* only the 100-500 tier fans out; the 20-100 one holds over a thousand
   brands, too many paths to draw */
const TIERS: Tier[] = [
  { lo: 100, hi: NAMED_MIN, label: `brands with 100 to ${NAMED_MIN} projects`, ids: [], fan: true },
  { lo: META.min_lite, hi: 100, label: `brands with ${META.min_lite} to 100 projects`, ids: [], fan: false },
];
for (const c of COMPANIES) for (const t of TIERS) if (c.total >= t.lo && c.total < t.hi) t.ids.push(c.id);

const zeros = () => YEARS.map(() => 0);
const sumOf = (ids: number[]) => ids.reduce((acc, id) => { BY_COMPANY.get(id)!.index.forEach((x, i) => { acc[i] += x; }); return acc; }, zeros());
/* denominator: every brand with >= min_lite projects */
const YEAR_TOTAL = sumOf(COMPANIES.map((c) => c.id));
const eraOf = (y: number) => { const i = ERAS.findIndex((b) => y <= b); return i === -1 ? ERAS.length : i; };
const peakOf = (v: number[]) => YEARS[v.indexOf(Math.max(...v))];

/** stack a set of bands: tiers first (in the order given), then named by peak year */
function stack(bands: Band[]): { bands: Band[]; y0: number[][] } {
  const sorted = [...bands].sort((a, b) =>
    (a.tier || b.tier) ? Number(Boolean(b.tier)) - Number(Boolean(a.tier)) : a.peakYear - b.peakYear || b.total - a.total);
  const y0: number[][] = [];
  const acc = zeros();
  for (const b of sorted) { y0.push([...acc]); b.v.forEach((x, i) => { acc[i] += x; }); }
  return { bands: sorted, y0 };
}

/* the full view: named brands plus the two tiers (smallest on the baseline), as shares of all brands shown */
const FULL = stack([
  ...[...TIERS].reverse().map((t): Band => {
    const i = TIERS.indexOf(t);
    const v = sumOf(t.ids).map((x, yi) => x / YEAR_TOTAL[yi]);
    return { id: -(i + 1), name: `${t.ids.length.toLocaleString("en-US")} ${t.label}`,
      total: t.ids.reduce((a, id) => a + BY_COMPANY.get(id)!.total, 0), v, peakYear: peakOf(v), era: 0, tier: t };
  }),
  ...COMPANIES.filter((c) => c.total >= NAMED_MIN).map((c): Band => {
    const v = c.index.map((x, i) => x / YEAR_TOTAL[i]);
    const peakYear = peakOf(v);
    return { id: c.id, name: c.name, total: c.total, v, peakYear, era: eraOf(peakYear) };
  }),
]);

/* a tier fanned out: its brands as shares of the tier that year */
function fanOut(t: Tier): { bands: Band[]; y0: number[][] } {
  const total = sumOf(t.ids);
  return stack(t.ids.map((id): Band => {
    const c = BY_COMPANY.get(id)!;
    const v = c.index.map((x, i) => (total[i] > 0 ? x / total[i] : 0));
    const peakYear = peakOf(v);
    return { id, name: c.name, total: c.total, v, peakYear, era: eraOf(peakYear) };
  }));
}

const VARIETY = brandData.variety;
const MARGIN = { top: 16, right: 24, bottom: 40, left: 44 };
const CHART_H = 460;
const MIN_LABEL_PX = 15;

const pct = (v: number, d = 1) => `${(100 * v).toFixed(d)}%`;
const fmt = (n: number) => n.toLocaleString("en-US");

interface Scales { x: (y: number) => number; y: (v: number) => number }

/* The band paths never depend on hover, so they are memoised and the hover
   highlight is a class toggled on the DOM (see .brand-eras in globals.css). */
const Bands = memo(function Bands({ bands, y0, scales, fills, interactive }: { bands: Band[]; y0: number[][]; scales: Scales; fills: string[]; interactive: boolean }) {
  return (
    <>
      {bands.map((b, i) => (
        <Area<number> key={b.id} data={YEARS.map((_, yi) => yi)} curve={curveMonotoneX}
          x={(yi) => scales.x(YEARS[yi])} y0={(yi) => scales.y(y0[i][yi])} y1={(yi) => scales.y(y0[i][yi] + b.v[yi])}
          className="band" data-band={i} fill={fills[i]}
          style={{ cursor: interactive ? "pointer" : undefined }}
          stroke="var(--background)" strokeWidth={0.4} />
      ))}
    </>
  );
});

type View = { kind: "full" } | { kind: "tier"; tier: Tier } | { kind: "solo"; id: number };

interface ChartProps { width: number; view: View; setView: (v: View) => void; article: boolean }

function Chart({ width, view, setView, article }: ChartProps) {
  const theme = useThemeColors();
  const { showTooltip, hideTooltip, tooltipData, tooltipLeft, tooltipTop } =
    useTooltip<{ band: number | null; yi: number }>();
  const svgRef = useRef<SVGSVGElement>(null);
  const hovered = useRef<SVGPathElement | null>(null);
  const innerW = width - MARGIN.left - MARGIN.right;
  const innerH = CHART_H - MARGIN.top - MARGIN.bottom;

  const stacked = useMemo(() => (view.kind === "tier" ? fanOut(view.tier) : FULL), [view]);
  const { bands, y0 } = stacked;
  const solo = useMemo(() => {
    if (view.kind !== "solo") return null;
    const c = BY_COMPANY.get(view.id);
    if (!c) return null;
    const v = c.index.map((x, i) => x / YEAR_TOTAL[i]);
    return { name: c.name, v, total: c.total, peakYear: peakOf(v) };
  }, [view]);

  const xScale = useMemo(() => scaleLinear({ domain: [YEARS[0], YEARS[LAST]], range: [0, Math.max(1, innerW)] }), [innerW]);
  const yMax = useMemo(() => {
    if (!solo) return 1;
    const m = Math.max(...solo.v);
    const step = m > 0.05 ? 0.02 : m > 0.01 ? 0.005 : 0.001;
    return Math.ceil(m / step) * step;
  }, [solo]);
  const yScale = useMemo(() => scaleLinear({ domain: [0, yMax], range: [innerH, 0] }), [innerH, yMax]);
  const scales = useMemo<Scales>(() => ({ x: (y) => xScale(y), y: (v) => yScale(v) }), [xScale, yScale]);
  const fills = useMemo(() => bands.map((b) =>
    (b.tier ? theme.resolve(TIER_TOKENS[TIERS.indexOf(b.tier)]) : theme.resolve(ERA_TOKENS[b.era]))), [bands, theme]);
  const yi = tooltipData?.yi ?? LAST;
  /* the five biggest brands at the hovered year, within the current view */
  const inTier = view.kind === "tier" ? view.tier : null;
  const topAtYear = useMemo(() => {
    const pool = inTier ? inTier.ids : COMPANIES.map((c) => c.id);
    return pool.map((id) => BY_COMPANY.get(id)!).sort((a, b) => b.index[yi] - a.index[yi]).slice(0, 5);
  }, [yi, inTier]);

  if (width < 10) return null;
  const grey = theme.role.muted;

  const yearAt = (px: number) => Math.min(LAST, Math.max(0, Math.round(xScale.invert(px - MARGIN.left)) - YEARS[0]));
  const setHover = (el: SVGPathElement | null) => {
    if (hovered.current === el) return;
    hovered.current?.classList.remove("is-hover");
    hovered.current = el;
    el?.classList.add("is-hover");
    if (el) svgRef.current?.setAttribute("data-hover", ""); else svgRef.current?.removeAttribute("data-hover");
  };
  const onMove = (e: React.PointerEvent<SVGSVGElement>) => {
    if (article) return;
    const p = localPoint(e);
    if (!p) return;
    const year = yearAt(p.x);
    if (solo) { showTooltip({ tooltipData: { band: null, yi: year }, tooltipLeft: p.x, tooltipTop: p.y }); return; }
    const t = e.target as Element;
    const el = t.classList?.contains("band") ? (t as SVGPathElement) : null;
    setHover(el);
    if (el) showTooltip({ tooltipData: { band: Number(el.dataset.band), yi: year }, tooltipLeft: p.x, tooltipTop: p.y });
    else hideTooltip();
  };
  const onLeave = () => { setHover(null); hideTooltip(); };
  const onClick = (e: React.MouseEvent<SVGSVGElement>) => {
    if (article) return;
    if (solo) { setView({ kind: "full" }); return; }
    const t = e.target as Element;
    if (!t.classList?.contains("band")) return;
    const b = bands[Number((t as SVGPathElement).dataset.band)];
    if (b.tier && !b.tier.fan) return;
    setHover(null); hideTooltip();
    setView(b.tier ? { kind: "tier", tier: b.tier } : { kind: "solo", id: b.id });
  };

  /* labels for bands thick enough at their widest point, thickest first,
     kept inside the plot and dropped when they would overlap one placed */
  type Label = { i: number; x: number; y: number; w: number; size: number; name: string; px: number };
  const labels: Label[] = [];
  if (!solo) {
    const cands = bands.flatMap((b, i) => {
      let best = 0, bestPx = 0;
      b.v.forEach((x, k) => { const px = x * innerH; if (px > bestPx) { bestPx = px; best = k; } });
      if (bestPx < MIN_LABEL_PX) return [];
      const size = Math.min(15, 9 + bestPx / 8);
      const w = b.name.length * size * 0.58;
      const x = Math.min(innerW - w / 2, Math.max(w / 2, xScale(YEARS[best])));
      return [{ i, x, y: yScale(y0[i][best] + b.v[best] / 2), w, size, name: b.name, px: bestPx }];
    }).sort((a, b) => b.px - a.px);
    for (const c of cands) {
      const clash = labels.some((l) => Math.abs(l.x - c.x) < (l.w + c.w) / 2 + 6 && Math.abs(l.y - c.y) < (l.size + c.size) / 2 + 2);
      if (!clash) labels.push(c);
    }
  }

  const tipBand = tooltipData && tooltipData.band !== null ? bands[tooltipData.band] : null;
  /* inside a fanned-out tier, the "biggest" shares are of the tier, like the band values */
  const denom = inTier ? sumOf(inTier.ids)[yi] : YEAR_TOTAL[yi];
  const tierActive = (t: Tier, year: number) => t.ids.filter((id) => BY_COMPANY.get(id)!.index[year] > 0).length;
  const tierTop = (t: Tier, year: number) =>
    t.ids.map((id) => BY_COMPANY.get(id)!).sort((a, b) => b.index[year] - a.index[year]).slice(0, 5);
  const aria = solo ? `Share of brand uses for ${solo.name}, ${YEARS[0]} to ${YEARS[LAST]}.`
    : inTier ? `The ${fmt(inTier.ids.length)} ${inTier.label}, stacked as shares of that tier, ${YEARS[0]} to ${YEARS[LAST]}, coloured by the year each peaked.`
    : `Every yarn brand's share of brand uses on the panel, stacked, ${YEARS[0]} to ${YEARS[LAST]}: the long tail on the baseline in two tiers, then named brands by the year they peaked, coloured by era.`;

  return (
    <div className="relative">
      <svg ref={svgRef} width={width} height={CHART_H} role="img" aria-label={aria} className="brand-eras"
        onPointerMove={onMove} onPointerLeave={onLeave} onClick={onClick}
        style={{ cursor: !article && solo ? "zoom-out" : undefined }}>
        <Group left={MARGIN.left} top={MARGIN.top}>
          {solo ? (
            <>
              <Area<number> data={YEARS.map((_, i) => i)} curve={curveMonotoneX}
                x={(i) => xScale(YEARS[i])} y0={innerH} y1={(i) => yScale(solo.v[i])}
                style={{ fill: theme.shade(theme.resolve("--primary"), 0.45, "white") }} stroke={theme.resolve("--primary")} strokeWidth={1.5} />
              <text x={innerW / 2} y={innerH * 0.42} textAnchor="middle" fontSize={Math.min(40, innerW / 12)}
                fontWeight={600} fill="var(--foreground)" style={{ paintOrder: "stroke", stroke: "var(--background)", strokeWidth: 6, strokeLinejoin: "round" }}>
                {solo.name}
              </text>
            </>
          ) : (
            <>
              <Bands bands={bands} y0={y0} scales={scales} fills={fills} interactive={!article} />
              {labels.map((l) => (
                <text key={l.i} x={l.x} y={l.y + l.size / 3} textAnchor="middle" fontSize={l.size} fontWeight={600}
                  fill="var(--foreground)"
                  style={{ pointerEvents: "none", paintOrder: "stroke", stroke: "var(--background)", strokeWidth: 3, strokeLinejoin: "round", strokeOpacity: 0.7 }}>
                  {l.name}
                </text>
              ))}
            </>
          )}
          <AxisLeft scale={yScale} numTicks={5} tickFormat={(v) => pct(Number(v), yMax <= 0.05 ? 1 : 0)}
            stroke={grey} tickStroke={grey} tickLabelProps={{ fill: grey, fontSize: 11, textAnchor: "end", dx: -4 }} />
          <AxisBottom top={innerH} scale={xScale}
            tickValues={YEARS.filter((y) => y % (innerW < 420 ? 4 : 2) === 0)}
            tickFormat={(v) => String(v)} stroke={grey} tickStroke={grey}
            tickLabelProps={{ fill: grey, fontSize: 11, textAnchor: "middle" }} />
        </Group>
      </svg>

      {tooltipData && (solo || tipBand) && (
        <TooltipWithBounds left={tooltipLeft} top={tooltipTop} className="pointer-events-none"
          style={{ position: "absolute", background: "var(--background)", color: "var(--foreground)",
            border: "1px solid var(--muted)", borderRadius: 6, padding: "8px 10px", fontSize: 12, lineHeight: 1.5, maxWidth: 300 }}>
          <div className="font-semibold">{solo ? solo.name : tipBand!.name}</div>
          <div className="tabular-nums">
            {YEARS[yi]}: {pct(solo ? solo.v[yi] : tipBand!.v[yi])} of {inTier && !solo ? "the tier" : "brand uses"}
          </div>
          {!solo && tipBand!.tier && (
            <div style={{ color: grey }}>{fmt(tierActive(tipBand!.tier, yi))} of them used in {YEARS[yi]}{tipBand!.tier.fan ? " · click to fan out" : ""}</div>
          )}
          {!solo && !tipBand!.tier && (
            <div style={{ color: grey }}>peaked {tipBand!.peakYear} · {fmt(tipBand!.total)} panel projects · click to see on its own</div>
          )}
          <div className="mt-1.5 border-t pt-1.5" style={{ borderColor: "color-mix(in srgb, var(--muted) 30%, transparent)", color: grey }}>
            biggest in {YEARS[yi]}{!solo && tipBand!.tier ? " in the tier" : inTier ? " in the tier" : ""}
            {(!solo && tipBand!.tier ? tierTop(tipBand!.tier, yi) : topAtYear).map((c) => (
              <div key={c.id} className="flex justify-between gap-4 tabular-nums" style={{ color: "var(--foreground)" }}>
                <span>{c.name}</span><span>{pct(c.index[yi] / (!solo && tipBand!.tier ? YEAR_TOTAL[yi] : denom))}</span>
              </div>
            ))}
          </div>
        </TooltipWithBounds>
      )}
    </div>
  );
}

function Search({ view, setView }: { view: View; setView: (v: View) => void }) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [cursor, setCursor] = useState(0);
  const wrap = useRef<HTMLDivElement>(null);
  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q === "" ? [] : COMPANIES.filter((b) => b.name.toLowerCase().includes(q)).slice(0, 8);
  }, [query]);

  useEffect(() => {
    const close = (e: PointerEvent) => {
      if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, []);

  const pick = (id: number) => { setView({ kind: "solo", id }); setQuery(""); setOpen(false); setCursor(0); };
  const onKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setCursor((c) => Math.min(c + 1, matches.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setCursor((c) => Math.max(c - 1, 0)); }
    else if (e.key === "Enter") { e.preventDefault(); if (matches[cursor]) pick(matches[cursor].id); }
    else if (e.key === "Escape") { setOpen(false); setView({ kind: "full" }); }
  };
  const border = { borderColor: "color-mix(in srgb, var(--muted) 40%, transparent)" };
  const pill = "rounded-full border px-2.5 py-0.5";

  return (
    <div ref={wrap} className="mb-3 flex flex-wrap items-center gap-2 text-sm">
      <div className="relative" style={{ width: 260 }}>
        <input type="text" value={query} placeholder="find a brand…" aria-label="Find a brand in the era view"
          onChange={(e) => { setQuery(e.target.value); setOpen(true); setCursor(0); }}
          onFocus={() => setOpen(true)} onKeyDown={onKey}
          className="w-full rounded-md border bg-transparent px-2.5 py-1 outline-none focus:border-[var(--primary)]"
          style={border} />
        {open && matches.length > 0 && (
          <ul role="listbox" className="absolute left-0 z-10 mt-1 w-full overflow-hidden rounded-md border shadow-sm"
            style={{ background: "var(--background)", ...border }}>
            {matches.map((b, i) => (
              <li key={b.id} role="option" aria-selected={i === cursor}
                onPointerDown={(e) => { e.preventDefault(); pick(b.id); }}
                onPointerEnter={() => setCursor(i)}
                className="flex cursor-pointer items-baseline justify-between px-2.5 py-1"
                style={{ background: i === cursor ? "color-mix(in srgb, var(--muted) 18%, transparent)" : undefined }}>
                <span>{b.name}</span>
                <span className="text-xs tabular-nums" style={{ color: "var(--muted)" }}>{fmt(b.total)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
      {view.kind !== "full" && (
        <button type="button" onClick={() => setView({ kind: "full" })} className={pill} style={{ ...border, color: "var(--muted)" }}>
          ← all brands
        </button>
      )}
      {view.kind === "tier" && (
        <span className="text-xs" style={{ color: "var(--muted)" }}>
          the {fmt(view.tier.ids.length)} {view.tier.label}, as shares of that tier
        </span>
      )}
    </div>
  );
}

function Tile({ label, a, b, unit = "" }: { label: string; a: number | null; b: number | null; unit?: string }) {
  return (
    <div className="rounded-md border px-3 py-2" style={{ borderColor: "color-mix(in srgb, var(--muted) 30%, transparent)", background: "var(--surface-tile)" }}>
      <div className="text-xs" style={{ color: "var(--muted)" }}>{label}</div>
      <div className="mt-0.5 flex items-baseline gap-2">
        <span className="text-xl font-semibold">{a === null ? "–" : fmt(a)}{unit}</span>
        <span className="text-sm" style={{ color: "var(--muted)" }}>→</span>
        <span className="text-xl font-semibold">{b === null ? "–" : fmt(b)}{unit}</span>
      </div>
    </div>
  );
}

export default function YarnBrandEras() {
  const article = useVariant() === "article";
  const [view, setView] = useState<View>({ kind: "full" });
  const v0 = VARIETY[0], v1 = VARIETY[VARIETY.length - 1];
  const peakEff = VARIETY.reduce((a, b) => ((b.eff_brands ?? 0) > (a.eff_brands ?? 0) ? b : a));
  const named = COMPANIES.filter((c) => c.total >= NAMED_MIN).length;

  return (
    <figure id="yarn-brand-eras" className={article ? "w-full" : "w-full rounded-lg p-4"}
      style={article ? undefined : { background: "var(--surface-figure)" }}>
      <figcaption className="mb-3">
        <h2 className="text-lg font-semibold">Every brand at once</h2>
        <p className="text-sm" style={{ color: "var(--muted)" }}>
          Brands with at least {NAMED_MIN} panel projects, stacked by share of brand uses in
          the order they peaked and coloured by when: the earlier the peak, the deeper the
          colour. The long tail sits on the baseline in two grey tiers.
          {!article && " Hover a band; click the 100-to-500 tier to fan it out brand by brand, click a brand to see it on its own, or search."}
        </p>
      </figcaption>
      {!article && <Search view={view} setView={setView} />}
      <ParentSize>{({ width }) => <Chart width={width} view={view} setView={setView} article={article} />}</ParentSize>

      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs" style={{ color: "var(--muted)" }}>
        <span className="inline-flex items-center gap-1.5">
          peaked earlier
          <i className="inline-block h-2.5 w-16 rounded-sm"
            style={{ background: `linear-gradient(to right, ${ERA_TOKENS.map((t) => `var(${t})`).join(", ")})` }} />
          later
        </span>
        {TIERS.map((t, i) => (
          <span key={t.lo} className="inline-flex items-center gap-1.5">
            <i className="inline-block h-2.5 w-3.5 rounded-sm" style={{ background: `var(${TIER_TOKENS[i]})` }} />{t.lo} to {t.hi} projects
          </span>
        ))}
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <Tile label={`effective number of brands, ${v0.year} → ${v1.year}`} a={v0.eff_brands} b={v1.eff_brands} />
        <Tile label={`brands covering half of all uses, ${v0.year} → ${v1.year}`} a={v0.half_cover} b={v1.half_cover} />
        <Tile label={`share of the ten biggest, ${v0.year} → ${v1.year}`} a={Math.round(100 * v0.top10_share)} b={Math.round(100 * v1.top10_share)} unit="%" />
      </div>

      {!article && <details className="mt-3 text-xs">
        <summary className="cursor-pointer" style={{ color: "var(--muted)" }}>Table view (variety by year)</summary>
        <table className="mt-2 w-full tabular-nums" style={{ borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ color: "var(--muted)" }}>
              <th className="py-1 text-left font-medium">year</th>
              <th className="py-1 text-right font-medium">brands used</th>
              <th className="py-1 text-right font-medium">effective brands</th>
              <th className="py-1 text-right font-medium">covering half</th>
              <th className="py-1 text-right font-medium">top ten share</th>
              {TIERS.map((t) => <th key={t.lo} className="py-1 text-right font-medium">{t.lo} to {t.hi}</th>)}
            </tr>
          </thead>
          <tbody>
            {VARIETY.map((r, i) => (
              <tr key={r.year} style={{ borderTop: "1px solid color-mix(in srgb, var(--muted) 30%, transparent)" }}>
                <td className="py-1">{r.year}</td>
                <td className="py-1 text-right">{fmt(r.brands)}</td>
                <td className="py-1 text-right">{r.eff_brands ?? "–"}</td>
                <td className="py-1 text-right">{r.half_cover}</td>
                <td className="py-1 text-right">{pct(r.top10_share, 0)}</td>
                {TIERS.map((t) => <td key={t.lo} className="py-1 text-right">{pct(FULL.bands.find((b) => b.tier === t)!.v[i], 0)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </details>}

      {!article && (
        <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
          Each band is a brand's panel index divided by the year's sum over every brand shown,
          so the stack fills 100% of brand uses; a project that linked two brands counts once
          for each, and these shares are not comparable with the lines above. Bands are drawn
          for the {named} brands with at least {NAMED_MIN} panel projects; the {fmt(TIERS[0].ids.length)} with
          100 to {NAMED_MIN} and the {fmt(TIERS[1].ids.length)} with {META.min_lite} to 100 are the two grey
          tiers; the first fans out on a click, the second is too many bands to draw and is
          described on hover instead. The {fmt(brandData.other.companies)} brands
          with fewer than {META.min_lite} panel projects, most of them individual crafters, are left
          out of the stack and its denominator. "Effective number of brands" is the inverse
          Simpson index on a fixed draw of {fmt(META.rarefy)} linked projects a year, so growth
          in the panel itself does not inflate it; it peaked at {peakEff.eff_brands} in {peakEff.year}.
        </p>
      )}
    </figure>
  );
}
