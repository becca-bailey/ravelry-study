"use client";

import { useEffect, useMemo, useRef, useState } from "react";
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

/* Every brand at once, stacked: the baby-name-grapher view. Each band is a
   brand's share of brand uses on the panel (its panel index divided by the
   year's sum over all brands, so the stack always fills 100%: a project
   that linked two brands counts once for each). Brands with fewer than
   meta.min_total panel projects are summed into one grey "everything
   else" band. Bands are stacked in order of their peak year, oldest at the
   bottom, so the eras read upward. Hover a band for its numbers; click, or
   search, to see one brand on its own. */

interface Band { id: number; name: string; total: number; v: number[]; peakYear: number }

const META = brandData.meta;
const YEARS: number[] = META.years_list;
const OTHER_ID = -1;

const RAW: Band[] = [
  ...brandData.companies.map((c) => ({ id: c.id, name: c.name, total: c.total, v: c.index, peakYear: 0 })),
  { id: OTHER_ID, name: `${brandData.other.companies.toLocaleString("en-US")} smaller brands`,
    total: brandData.other.n.reduce((a, b) => a + b, 0), v: brandData.other.index, peakYear: 0 },
];
const YEAR_TOTAL = YEARS.map((_, i) => RAW.reduce((a, b) => a + b.v[i], 0));
/* normalised to share of brand uses, ordered by peak year (ties: bigger first), other on top */
const BANDS: Band[] = RAW.map((b) => {
  const v = b.v.map((x, i) => x / YEAR_TOTAL[i]);
  const peak = v.indexOf(Math.max(...v));
  return { ...b, v, peakYear: YEARS[peak] };
}).sort((a, b) => a.id === OTHER_ID ? 1 : b.id === OTHER_ID ? -1
  : a.peakYear - b.peakYear || b.total - a.total);
/* cumulative lower edge per band and year */
const Y0: number[][] = [];
{
  const acc = YEARS.map(() => 0);
  for (const b of BANDS) { Y0.push([...acc]); b.v.forEach((x, i) => { acc[i] += x; }); }
}
const BY_ID = new Map(BANDS.map((b, i) => [b.id, i]));

const MARGIN = { top: 16, right: 24, bottom: 40, left: 44 };
const CHART_H = 460;
/* tints of the series hue, mixed toward white so they lift on both themes */
const TINTS = [1, 0.78, 0.58, 0.4];
const MIN_LABEL_PX = 15;

const pct = (v: number, d = 1) => `${(100 * v).toFixed(d)}%`;
const fmt = (n: number) => n.toLocaleString("en-US");

interface ChartProps { width: number; focus: number | null; setFocus: (id: number | null) => void; article: boolean }

function Chart({ width, focus, setFocus, article }: ChartProps) {
  const theme = useThemeColors();
  const { showTooltip, hideTooltip, tooltipData, tooltipLeft, tooltipTop } =
    useTooltip<{ band: number; yi: number }>();
  const [hover, setHover] = useState<number | null>(null);
  const innerW = width - MARGIN.left - MARGIN.right;
  const innerH = CHART_H - MARGIN.top - MARGIN.bottom;
  const focusIdx = focus === null ? null : BY_ID.get(focus) ?? null;
  const solo = focusIdx === null ? null : BANDS[focusIdx];

  const xScale = useMemo(
    () => scaleLinear({ domain: [YEARS[0], YEARS[YEARS.length - 1]], range: [0, innerW] }),
    [innerW],
  );
  const yMax = useMemo(() => {
    if (!solo) return 1;
    const m = Math.max(...solo.v);
    const step = m > 0.05 ? 0.02 : m > 0.01 ? 0.005 : 0.001;
    return Math.ceil(m / step) * step;
  }, [solo]);
  const yScale = useMemo(() => scaleLinear({ domain: [0, yMax], range: [innerH, 0] }), [innerH, yMax]);

  if (width < 10) return null;
  const base = theme.chart[0];
  const grey = theme.role.muted;
  const hot = theme.chartContrast[0];
  const fillOf = (i: number) =>
    BANDS[i].id === OTHER_ID ? theme.shade(grey, 0.5, "transparent")
      : theme.shade(base, TINTS[i % TINTS.length], "white");

  const yearAt = (px: number) => {
    const y = Math.round(xScale.invert(px - MARGIN.left));
    return Math.min(YEARS.length - 1, Math.max(0, y - YEARS[0]));
  };
  const onMove = (i: number) => (e: React.PointerEvent<SVGPathElement>) => {
    const p = localPoint(e);
    if (!p) return;
    setHover(i);
    showTooltip({ tooltipData: { band: i, yi: yearAt(p.x) }, tooltipLeft: p.x, tooltipTop: p.y });
  };
  const leave = () => { setHover(null); hideTooltip(); };

  /* labels for bands thick enough at their widest point, thickest first,
     kept inside the plot and dropped when they would overlap one placed */
  type Label = { i: number; x: number; y: number; w: number; size: number; name: string };
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

  const tip = tooltipData ? BANDS[tooltipData.band] : null;
  const label = solo ? `Share of brand uses for ${solo.name}, ${YEARS[0]} to ${YEARS[YEARS.length - 1]}.`
    : `Every yarn brand's share of brand uses on the panel, stacked, ${YEARS[0]} to ${YEARS[YEARS.length - 1]}, oldest-peaking brands at the bottom.`;

  return (
    <div className="relative">
      <svg width={width} height={CHART_H} role="img" aria-label={label}
        onClick={() => { if (!article && solo) setFocus(null); }}
        style={{ cursor: !article && solo ? "zoom-out" : undefined }}>
        <Group left={MARGIN.left} top={MARGIN.top}>
          {solo ? (
            <>
              <Area<number> data={YEARS.map((_, i) => i)} curve={curveMonotoneX}
                x={(i) => xScale(YEARS[i])} y0={innerH} y1={(i) => yScale(solo.v[i])}
                style={{ fill: fillOf(focusIdx!) }} stroke={base} strokeWidth={1.5} />
              <text x={innerW / 2} y={innerH * 0.42} textAnchor="middle" fontSize={Math.min(40, innerW / 12)}
                fontWeight={600} fill="var(--foreground)" style={{ paintOrder: "stroke", stroke: "var(--background)", strokeWidth: 6, strokeLinejoin: "round" }}>
                {solo.name}
              </text>
              {!article && (
                <rect x={0} y={0} width={innerW} height={innerH} fill="transparent"
                  onPointerMove={(e) => { const p = localPoint(e); if (p) showTooltip({ tooltipData: { band: focusIdx!, yi: yearAt(p.x) }, tooltipLeft: p.x, tooltipTop: p.y }); }}
                  onPointerLeave={hideTooltip} />
              )}
            </>
          ) : (
            <>
              {BANDS.map((b, i) => (
                <Area<number> key={b.id} data={YEARS.map((_, yi) => yi)} curve={curveMonotoneX}
                  x={(yi) => xScale(YEARS[yi])}
                  y0={(yi) => yScale(Y0[i][yi])} y1={(yi) => yScale(Y0[i][yi] + b.v[yi])}
                  style={{ fill: hover === i ? hot : fillOf(i), cursor: article ? undefined : "pointer" }}
                  stroke="var(--background)" strokeWidth={0.4}
                  onPointerMove={article ? undefined : onMove(i)}
                  onPointerLeave={article ? undefined : leave}
                  onClick={article ? undefined : (e) => { e.stopPropagation(); setFocus(b.id); }} />
              ))}
              {labels.map((l) => (
                <text key={l.i} x={l.x} y={l.y + l.size / 3} textAnchor="middle" fontSize={l.size} fontWeight={600}
                  fill="var(--foreground)"
                  style={{ pointerEvents: "none", paintOrder: "stroke", stroke: "var(--background)", strokeWidth: 3, strokeLinejoin: "round", strokeOpacity: 0.7 }}>
                  {l.name}
                </text>
              ))}
            </>
          )}

          <AxisLeft scale={yScale} numTicks={5} tickFormat={(v) => pct(Number(v), yMax < 0.02 ? 1 : 0)}
            stroke={grey} tickStroke={grey}
            tickLabelProps={{ fill: grey, fontSize: 11, textAnchor: "end", dx: -4 }} />
          <AxisBottom top={innerH} scale={xScale}
            tickValues={YEARS.filter((y) => y % (innerW < 420 ? 4 : 2) === 0)}
            tickFormat={(v) => String(v)} stroke={grey} tickStroke={grey}
            tickLabelProps={{ fill: grey, fontSize: 11, textAnchor: "middle" }} />
        </Group>
      </svg>

      {tip && tooltipData && (
        <TooltipWithBounds left={tooltipLeft} top={tooltipTop} className="pointer-events-none"
          style={{ position: "absolute", background: "var(--background)", color: "var(--foreground)",
            border: "1px solid var(--muted)", borderRadius: 6, padding: "8px 10px", fontSize: 12, lineHeight: 1.5 }}>
          <div className="font-semibold">{tip.name}</div>
          <div className="tabular-nums">{YEARS[tooltipData.yi]}: {pct(tip.v[tooltipData.yi])} of brand uses</div>
          {tip.id !== OTHER_ID && <div style={{ color: grey }}>peak {tip.peakYear} · {fmt(tip.total)} panel projects</div>}
          {!solo && <div style={{ color: grey }}>click to see on its own</div>}
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
  const named = useMemo(() => BANDS.filter((b) => b.id !== OTHER_ID).sort((a, b) => b.total - a.total), []);
  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q === "" ? [] : named.filter((b) => b.name.toLowerCase().includes(q)).slice(0, 8);
  }, [query, named]);

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
  const current = focus === null ? null : BANDS[BY_ID.get(focus)!];

  return (
    <div ref={wrap} className="mb-3 flex flex-wrap items-center gap-2 text-sm">
      <div className="relative" style={{ width: 260 }}>
        <input type="text" value={query} placeholder="find a brand…" aria-label="Find a brand"
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
      {current && (
        <button type="button" onClick={() => setFocus(null)}
          className="rounded-full border px-2.5 py-0.5" style={{ ...border, color: "var(--muted)" }}>
          ← all brands
        </button>
      )}
    </div>
  );
}

export default function YarnBrandStream() {
  const article = useVariant() === "article";
  const [focus, setFocus] = useState<number | null>(null);
  const tableRows = useMemo(() => {
    const top = BANDS.filter((b) => b.id !== OTHER_ID).sort((a, b) => b.total - a.total).slice(0, 10);
    return [...top, BANDS[BANDS.length - 1]];
  }, []);
  const latest = brandData.coverage[brandData.coverage.length - 1];

  return (
    <figure id="yarn-brand-stream" className="w-full">
      <figcaption className="mb-3">
        <h2 className="text-lg font-semibold">Every brand at once</h2>
        <p className="text-sm" style={{ color: "var(--muted)" }}>
          The same panel with all {fmt(brandData.companies.length)} named brands stacked
          by their share of brand uses, oldest-peaking at the bottom. Smaller brands are
          one band.{!article && " Hover a band, click to see one brand on its own, or search."}
        </p>
      </figcaption>
      {!article && <Search focus={focus} setFocus={setFocus} />}
      <ParentSize>{({ width }) => <Chart width={width} focus={focus} setFocus={setFocus} article={article} />}</ParentSize>

      {!article && <details className="mt-3 text-xs">
        <summary className="cursor-pointer" style={{ color: "var(--muted)" }}>Table view (ten largest brands and the rest)</summary>
        <div className="overflow-x-auto">
          <table className="mt-2 w-full tabular-nums" style={{ borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ color: "var(--muted)" }}>
                <th className="py-1 text-left font-medium">brand</th>
                <th className="py-1 text-left font-medium">peak</th>
                {YEARS.filter((y) => y % 3 === 1).map((y) => <th key={y} className="py-1 text-right font-medium">{y}</th>)}
              </tr>
            </thead>
            <tbody>
              {tableRows.map((b) => (
                <tr key={b.id} style={{ borderTop: "1px solid color-mix(in srgb, var(--muted) 30%, transparent)" }}>
                  <td className="py-1">{b.name}</td>
                  <td className="py-1">{b.id === OTHER_ID ? "" : b.peakYear}</td>
                  {YEARS.map((y, i) => y % 3 === 1 ? <td key={y} className="py-1 text-right">{pct(b.v[i])}</td> : null)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>}

      {!article && (
        <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
          Each band is a brand's panel index divided by that year's sum over every brand,
          so the stack always fills 100% of brand uses; a project that linked two brands
          counts once for each, and the shares are not comparable with the lines above,
          which are shares of projects. Brands with fewer than {META.min_total} panel
          projects since {YEARS[0]} are summed into the grey band, {fmt(brandData.other.companies)} of
          them, {pct(BANDS[BANDS.length - 1].v[YEARS.length - 1], 0)} of brand uses in {latest.year}.
          Band order is by the year each brand peaked.
        </p>
      )}
    </figure>
  );
}
