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

/* The stacked view: colour means era. Each named band (a brand
   with >= NAMED_MIN panel projects) takes a step of a one-hue ramp keyed to
   the year it peaked, earliest with the most ink, so the old guard thinning
   under a pale crowd of newcomers is the picture, not an inference. The
   long tail sits on the baseline in two grey tiers (100 to 500 projects,
   and under 100) so its growth reads against a flat edge. Shares are the
   panel index normalised to each year's sum over all brands. Hover a band
   for its numbers and the year's five biggest; click, or search, to see one
   brand alone. */

interface Band { id: number; name: string; total: number; v: number[]; peakYear: number; era: number }

const META = brandData.meta;
const YEARS: number[] = META.years_list;
const LAST = YEARS.length - 1;
const NAMED_MIN = 500;
const TAIL_SMALL = -2;
const TAIL_MID = -1;
const ERAS = [2011, 2014, 2017, 2020, 2023]; // cohort upper bounds; the sixth is open
const ERA_TOKENS = [1, 2, 3, 4, 5, 6].map((i) => `--era-${i}`);

const sum = (a: number[], b: number[]) => a.map((x, i) => x + b[i]);
const zeros = () => YEARS.map(() => 0);

const named = brandData.companies.filter((c) => c.total >= NAMED_MIN);
const mid = brandData.companies.filter((c) => c.total < NAMED_MIN);
const RAW = [
  { id: TAIL_SMALL, name: `${brandData.other.companies.toLocaleString("en-US")} brands under 100 projects`,
    total: brandData.other.n.reduce((a, b) => a + b, 0), v: brandData.other.index },
  { id: TAIL_MID, name: `${mid.length} brands with 100 to ${NAMED_MIN} projects`,
    total: mid.reduce((a, c) => a + c.total, 0), v: mid.reduce((acc, c) => sum(acc, c.index), zeros()) },
  ...named.map((c) => ({ id: c.id, name: c.name, total: c.total, v: c.index })),
];
const YEAR_TOTAL = YEARS.map((_, i) => RAW.reduce((a, b) => a + b.v[i], 0));
const eraOf = (y: number) => ERAS.findIndex((b) => y <= b) === -1 ? ERAS.length : ERAS.findIndex((b) => y <= b);
/* normalised, tails first, then named by peak year (ties: bigger first) */
const BANDS: Band[] = RAW.map((b) => {
  const v = b.v.map((x, i) => x / YEAR_TOTAL[i]);
  const peakYear = YEARS[v.indexOf(Math.max(...v))];
  return { ...b, v, peakYear, era: eraOf(peakYear) };
}).sort((a, b) => (a.id < 0 || b.id < 0) ? a.id - b.id : a.peakYear - b.peakYear || b.total - a.total);
const Y0: number[][] = [];
{
  const acc = zeros();
  for (const b of BANDS) { Y0.push([...acc]); b.v.forEach((x, i) => { acc[i] += x; }); }
}
const BY_ID = new Map(BANDS.map((b, i) => [b.id, i]));
/* every exported brand is searchable, even those drawn inside the mid tier */
const SEARCHABLE = brandData.companies.map((c) => ({ id: c.id, name: c.name, total: c.total, index: c.index }));
const VARIETY = brandData.variety;

const MARGIN = { top: 16, right: 24, bottom: 40, left: 44 };
const CHART_H = 460;
const MIN_LABEL_PX = 15;

const pct = (v: number, d = 1) => `${(100 * v).toFixed(d)}%`;
const fmt = (n: number) => n.toLocaleString("en-US");
const eraLabel = (e: number) => e === 0 ? `to ${ERAS[0]}` : e === ERAS.length ? `${ERAS[ERAS.length - 1] + 1} on` : `${ERAS[e - 1] + 1} to ${ERAS[e]}`;

interface Scales { x: (y: number) => number; y: (v: number) => number }

/* The band paths never depend on hover, so they are memoised and the hover
   highlight is a class toggled on the DOM (see .brand-eras in globals.css). */
const Bands = memo(function Bands({ scales, fills, interactive }: { scales: Scales; fills: string[]; interactive: boolean }) {
  return (
    <>
      {BANDS.map((b, i) => (
        <Area<number> key={b.id} data={YEARS.map((_, yi) => yi)} curve={curveMonotoneX}
          x={(yi) => scales.x(YEARS[yi])} y0={(yi) => scales.y(Y0[i][yi])} y1={(yi) => scales.y(Y0[i][yi] + b.v[yi])}
          className="band" data-band={i}
          style={{ fill: fills[i], cursor: interactive ? "pointer" : undefined }}
          stroke="var(--background)" strokeWidth={0.4} />
      ))}
    </>
  );
});

interface Solo { name: string; v: number[]; total: number; peakYear: number }

interface ChartProps { width: number; solo: Solo | null; onPick: (id: number | null) => void; article: boolean }

function Chart({ width, solo, onPick, article }: ChartProps) {
  const theme = useThemeColors();
  const { showTooltip, hideTooltip, tooltipData, tooltipLeft, tooltipTop } =
    useTooltip<{ band: number | null; yi: number }>();
  const svgRef = useRef<SVGSVGElement>(null);
  const hovered = useRef<SVGPathElement | null>(null);
  const innerW = width - MARGIN.left - MARGIN.right;
  const innerH = CHART_H - MARGIN.top - MARGIN.bottom;

  const xScale = useMemo(() => scaleLinear({ domain: [YEARS[0], YEARS[LAST]], range: [0, innerW] }), [innerW]);
  const yMax = useMemo(() => {
    if (!solo) return 1;
    const m = Math.max(...solo.v);
    const step = m > 0.05 ? 0.02 : m > 0.01 ? 0.005 : 0.001;
    return Math.ceil(m / step) * step;
  }, [solo]);
  const yScale = useMemo(() => scaleLinear({ domain: [0, yMax], range: [innerH, 0] }), [innerH, yMax]);
  const scales = useMemo<Scales>(() => ({ x: (y) => xScale(y), y: (v) => yScale(v) }), [xScale, yScale]);
  const fills = useMemo(() => BANDS.map((b) =>
    b.id === TAIL_SMALL ? theme.resolve("--era-tail-small")
      : b.id === TAIL_MID ? theme.resolve("--era-tail-mid")
      : theme.resolve(ERA_TOKENS[b.era])), [theme]);

  const yiMemo = tooltipData?.yi ?? LAST;
  const topAtYear = useMemo(() => [...SEARCHABLE].sort((a, b) => b.index[yiMemo] - a.index[yiMemo]).slice(0, 5), [yiMemo]);

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
    const yi = yearAt(p.x);
    if (solo) { showTooltip({ tooltipData: { band: null, yi }, tooltipLeft: p.x, tooltipTop: p.y }); return; }
    const t = e.target as Element;
    const el = t.classList?.contains("band") ? (t as SVGPathElement) : null;
    setHover(el);
    if (el) showTooltip({ tooltipData: { band: Number(el.dataset.band), yi }, tooltipLeft: p.x, tooltipTop: p.y });
    else hideTooltip();
  };
  const onLeave = () => { setHover(null); hideTooltip(); };
  const onClick = (e: React.MouseEvent<SVGSVGElement>) => {
    if (article) return;
    if (solo) { onPick(null); return; }
    const t = e.target as Element;
    if (t.classList?.contains("band")) onPick(BANDS[Number((t as SVGPathElement).dataset.band)].id);
  };

  /* labels for named bands thick enough at their widest point */
  type Label = { i: number; x: number; y: number; w: number; size: number; name: string; px: number };
  const labels: Label[] = [];
  if (!solo) {
    const cands = BANDS.flatMap((b, i) => {
      let best = 0, bestPx = 0;
      b.v.forEach((x, yi) => { const px = x * innerH; if (px > bestPx) { bestPx = px; best = yi; } });
      if (bestPx < MIN_LABEL_PX) return [];
      const size = Math.min(15, 9 + bestPx / 8);
      const w = b.name.length * size * 0.58;
      const x = Math.min(innerW - w / 2, Math.max(w / 2, xScale(YEARS[best])));
      return [{ i, x, y: yScale(Y0[i][best] + b.v[best] / 2), w, size, name: b.name, px: bestPx }];
    }).sort((a, b) => b.px - a.px);
    for (const c of cands) {
      const clash = labels.some((l) => Math.abs(l.x - c.x) < (l.w + c.w) / 2 + 6 && Math.abs(l.y - c.y) < (l.size + c.size) / 2 + 2);
      if (!clash) labels.push(c);
    }
  }

  const yi = tooltipData?.yi ?? LAST;
  const tipBand = tooltipData && tooltipData.band !== null ? BANDS[tooltipData.band] : null;
  const aria = solo ? `Share of brand uses for ${solo.name}, ${YEARS[0]} to ${YEARS[LAST]}.`
    : `Every yarn brand's share of brand uses on the panel, stacked, ${YEARS[0]} to ${YEARS[LAST]}: the long tail of small brands on the baseline, then named brands by the year they peaked, coloured by era.`;

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
                style={{ fill: theme.shade(theme.chart[0], 0.45, "white") }} stroke={theme.chart[0]} strokeWidth={1.5} />
              <text x={innerW / 2} y={innerH * 0.42} textAnchor="middle" fontSize={Math.min(40, innerW / 12)}
                fontWeight={600} fill="var(--foreground)" style={{ paintOrder: "stroke", stroke: "var(--background)", strokeWidth: 6, strokeLinejoin: "round" }}>
                {solo.name}
              </text>
            </>
          ) : (
            <>
              <Bands scales={scales} fills={fills} interactive={!article} />
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
            border: "1px solid var(--muted)", borderRadius: 6, padding: "8px 10px", fontSize: 12, lineHeight: 1.5, minWidth: 220 }}>
          <div className="font-semibold">{solo ? solo.name : tipBand!.name}</div>
          <div className="tabular-nums">{YEARS[yi]}: {pct(solo ? solo.v[yi] : tipBand!.v[yi])} of brand uses</div>
          {!solo && tipBand!.id >= 0 && <div style={{ color: grey }}>peaked {tipBand!.peakYear} · {fmt(tipBand!.total)} panel projects</div>}
          <div className="mt-1.5 border-t pt-1.5" style={{ borderColor: "color-mix(in srgb, var(--muted) 30%, transparent)", color: grey }}>
            biggest in {YEARS[yi]}
            {topAtYear.map((c) => (
              <div key={c.id} className="flex justify-between gap-4 tabular-nums" style={{ color: "var(--foreground)" }}>
                <span>{c.name}</span><span>{pct(c.index[yi] / YEAR_TOTAL[yi])}</span>
              </div>
            ))}
          </div>
          {!solo && <div className="mt-1" style={{ color: grey }}>click to see on its own</div>}
        </TooltipWithBounds>
      )}
    </div>
  );
}

function Search({ focus, setFocus }: { focus: number | null; setFocus: (id: number | null) => void }) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [cursor, setCursor] = useState(0);
  const wrap = useRef<HTMLDivElement>(null);
  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q === "" ? [] : SEARCHABLE.filter((b) => b.name.toLowerCase().includes(q)).slice(0, 8);
  }, [query]);

  useEffect(() => {
    const close = (e: PointerEvent) => {
      if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, []);

  const pick = (id: number) => { setFocus(id); setQuery(""); setOpen(false); setCursor(0); };
  const onKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setCursor((c) => Math.min(c + 1, matches.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setCursor((c) => Math.max(c - 1, 0)); }
    else if (e.key === "Enter") { e.preventDefault(); if (matches[cursor]) pick(matches[cursor].id); }
    else if (e.key === "Escape") { setOpen(false); setFocus(null); }
  };
  const border = { borderColor: "color-mix(in srgb, var(--muted) 40%, transparent)" };
  const pill = "rounded-full border px-2.5 py-0.5";

  return (
    <div ref={wrap} className="mb-3 flex flex-wrap items-center gap-2 text-sm">
      <div className="relative" style={{ width: 260 }}>
        <input type="text" value={query} placeholder="find a brand…" aria-label="Find a brand in the era view"
          onChange={(e) => { setQuery(e.target.value); setOpen(true); setCursor(0); }}
          onFocus={() => setOpen(true)} onKeyDown={onKey}
          className="w-full rounded-md border bg-transparent px-2.5 py-1 outline-none focus:border-[var(--origin)]"
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
      {focus !== null && (
        <>
          <button type="button" onClick={() => setFocus(null)} className={pill} style={{ ...border, color: "var(--muted)" }}>
            ← all brands
          </button>
          <button type="button" className={pill} style={{ ...border, color: "var(--origin)" }}
            onClick={() => window.dispatchEvent(new CustomEvent("yarn-brands:add", { detail: { id: focus } }))}>
            ↑ compare in the line chart
          </button>
        </>
      )}
    </div>
  );
}

function Tile({ label, a, b, unit = "" }: { label: string; a: number | null; b: number | null; unit?: string }) {
  return (
    <div className="rounded-md border px-3 py-2" style={{ borderColor: "color-mix(in srgb, var(--muted) 30%, transparent)" }}>
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
  const [focus, setFocus] = useState<number | null>(null);
  const solo = useMemo<Solo | null>(() => {
    if (focus === null) return null;
    const idx = BY_ID.get(focus);
    if (idx !== undefined) { const b = BANDS[idx]; return { name: b.name, v: b.v, total: b.total, peakYear: b.peakYear }; }
    const c = SEARCHABLE.find((s) => s.id === focus);
    if (!c) return null;
    const v = c.index.map((x, i) => x / YEAR_TOTAL[i]);
    return { name: c.name, v, total: c.total, peakYear: YEARS[v.indexOf(Math.max(...v))] };
  }, [focus]);
  const v0 = VARIETY[0], v1 = VARIETY[VARIETY.length - 1];
  const peakEff = VARIETY.reduce((a, b) => ((b.eff_brands ?? 0) > (a.eff_brands ?? 0) ? b : a));
  const theme = useThemeColors();

  return (
    <figure id="yarn-brand-eras" className="w-full">
      <figcaption className="mb-3">
        <h2 className="text-lg font-semibold">Every brand at once</h2>
        <p className="text-sm" style={{ color: "var(--muted)" }}>
          Brands with at least {NAMED_MIN} panel projects, stacked by share of brand uses in
          the order they peaked and coloured by when: the earlier the peak, the deeper the
          purple. The long tail sits on the baseline in grey.
          {!article && " Hover a band, click to see one brand on its own, or search."}
        </p>
      </figcaption>
      {!article && <Search focus={focus} setFocus={setFocus} />}
      <ParentSize>{({ width }) => <Chart width={width} solo={solo} onPick={setFocus} article={article} />}</ParentSize>

      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs" style={{ color: "var(--muted)" }}>
        <span>peaked</span>
        {ERA_TOKENS.map((t, e) => (
          <span key={t} className="inline-flex items-center gap-1.5">
            <i className="inline-block h-2.5 w-3.5 rounded-sm" style={{ background: `var(${t})` }} />{eraLabel(e)}
          </span>
        ))}
        <span className="inline-flex items-center gap-1.5">
          <i className="inline-block h-2.5 w-3.5 rounded-sm" style={{ background: "var(--era-tail-mid)" }} />100 to {NAMED_MIN} projects
        </span>
        <span className="inline-flex items-center gap-1.5">
          <i className="inline-block h-2.5 w-3.5 rounded-sm" style={{ background: "var(--era-tail-small)" }} />under 100
        </span>
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
              <th className="py-1 text-right font-medium">tail under 100</th>
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
                <td className="py-1 text-right">{pct(BANDS[0].v[i], 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>}

      {!article && (
        <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
          Each band is a brand's panel index divided by the year's sum over every brand, so
          the stack fills 100% of brand uses; a project that linked two brands counts once for
          each, and these shares are not comparable with the lines above. Bands are drawn
          for the {named.length} brands with at least {NAMED_MIN} panel projects; the {mid.length} with
          100 to {NAMED_MIN} and the {fmt(brandData.other.companies)} under 100 are the two grey
          tiers, and any of the named or mid-tier brands can be searched. "Effective number of
          brands" is the inverse Simpson index on a fixed draw of {fmt(META.rarefy)} linked projects
          a year, so growth in the panel itself does not inflate it; it peaked at {peakEff.eff_brands} in {peakEff.year}.
        </p>
      )}
    </figure>
  );
}
