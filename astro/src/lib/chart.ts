/* Shared sizing rules for the charts.

   A chart is "narrow" below NARROW px of container width: a phone held
   upright, or a half-width column. Narrow charts give the plot the width
   they would otherwise spend on a right-hand label column (end labels
   move into a legend under the plot), shorten long annotations, and thin
   the year ticks so the labels do not run into each other. */

export const NARROW = 520;
export const isNarrow = (width: number) => width < NARROW;

/** Year ticks for a linear time axis: every 2, 4, 6 or 8 years, the first
    step that leaves at least minPx between tick labels. */
export function yearTicks(years: number[], innerW: number, minPx = 44): number[] {
  const span = years[years.length - 1] - years[0];
  const perYear = innerW / Math.max(1, span);
  const step = [2, 4, 6, 8].find((s) => s * perYear >= minPx) ?? 8;
  return years.filter((y) => y % step === 0);
}
