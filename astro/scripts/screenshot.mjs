/* Deterministic chart screenshots for the writeup.

   Serves the built site (astro preview), renders each target element at a
   fixed viewport and 2x scale, and writes PNGs to ../reports/. Run:

     npm run screenshot

   Add entries to TARGETS as more charts land. */

import { spawn } from "node:child_process";
import { mkdirSync } from "node:fs";
import { chromium } from "playwright";

const PORT = 4322; // off the dev-server port so the two never collide
const OUT_DIR = new URL("../../reports/", import.meta.url).pathname;
const PAD = 24; // whitespace around each captured element, in CSS px
const TARGETS = [
  { path: "/closing-window/", selector: "#window-chart", out: "window_explorer.png" },
  { path: "/closing-window/", selector: "#evergreen-chart", out: "evergreen_curves_web.png" },
  { path: "/closing-window/", selector: "#conversion-chart", out: "conversion_web.png" },
  { path: "/closing-window/", selector: "#cadence-chart", out: "cadence_timeline_web.png" },
  { path: "/mkal/", selector: "#mkal-participation", out: "mkal_participation_web.png" },
  { path: "/mkal/", selector: "#mkal-outcomes", out: "mkal_outcomes_web.png" },
  { path: "/yarn-brands/", selector: "#yarn-brand-grapher", out: "yarn_brand_grapher_web.png" },
  { path: "/yarn-brands/", selector: "#yarn-brand-eras", out: "yarn_brand_eras_web.png" },
  { path: "/yarn-brands/", selector: "#yarn-brand-loyalty", out: "yarn_brand_loyalty_web.png" },
  // stripped-down versions for the essay/interview (see src/lib/variant.ts)
  { path: "/closing-window/?variant=article", selector: "#window-chart", out: "window_explorer_article.png" },
  { path: "/closing-window/?variant=article", selector: "#evergreen-chart", out: "evergreen_curves_article.png" },
  { path: "/closing-window/?variant=article", selector: "#cadence-chart", out: "cadence_timeline_article.png" },
  { path: "/mkal/?variant=article", selector: "#mkal-participation", out: "mkal_participation_article.png" },
  { path: "/mkal/?variant=article", selector: "#mkal-outcomes-bars", out: "mkal_outcomes_article.png" },
  { path: "/mkal/?variant=article&year=2014", selector: "#mkal-finish-curve", out: "mkal_finish_curve_2014_article.png" },
  { path: "/mkal/?variant=article&year=2021", selector: "#mkal-finish-curve", out: "mkal_finish_curve_2021_article.png" },
  { path: "/mkal/?variant=article&year=2025", selector: "#mkal-finish-curve", out: "mkal_finish_curve_2025_article.png" },
  { path: "/yarn-brands/?variant=article", selector: "#yarn-brand-grapher", out: "yarn_brand_grapher_article.png" },
  { path: "/yarn-brands/?variant=article&preset=sold", selector: "#yarn-brand-grapher", out: "yarn_brand_grapher_sold_article.png" },
  { path: "/yarn-brands/?variant=article&preset=sale", selector: "#yarn-brand-grapher", out: "yarn_brand_grapher_sale_article.png" },
  { path: "/yarn-brands/?variant=article&preset=dyers", selector: "#yarn-brand-grapher", out: "yarn_brand_grapher_dyers_article.png" },
  { path: "/yarn-brands/?variant=article&preset=risers", selector: "#yarn-brand-grapher", out: "yarn_brand_grapher_risers_article.png" },
  { path: "/yarn-brands/?variant=article&preset=nordic", selector: "#yarn-brand-grapher", out: "yarn_brand_grapher_nordic_article.png" },
  { path: "/yarn-brands/?variant=article&preset=socks", selector: "#yarn-brand-grapher", out: "yarn_brand_grapher_socks_article.png" },
  { path: "/yarn-brands/?variant=article&preset=bigbox", selector: "#yarn-brand-grapher", out: "yarn_brand_grapher_bigbox_article.png" },
  { path: "/yarn-brands/?variant=article&preset=next", selector: "#yarn-brand-grapher", out: "yarn_brand_grapher_next_article.png" },
  { path: "/yarn-brands/?variant=article", selector: "#yarn-brand-eras", out: "yarn_brand_eras_article.png" },
  { path: "/yarn-brands/?variant=article", selector: "#yarn-brand-loyalty", out: "yarn_brand_loyalty_article.png" },
];

const preview = spawn("npx", ["astro", "preview", "--port", String(PORT)], {
  cwd: new URL("..", import.meta.url).pathname,
  stdio: ["ignore", "inherit", "inherit"],
});

async function waitForServer(url, tries = 40) {
  for (let i = 0; i < tries; i++) {
    try {
      const res = await fetch(url);
      if (res.ok) return;
    } catch {}
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error(`preview server never came up at ${url}`);
}

try {
  await waitForServer(`http://localhost:${PORT}/`);
  mkdirSync(OUT_DIR, { recursive: true });
  const browser = await chromium.launch();
  // Tall viewport so every chart sits fully in view: clip coordinates stay
  // viewport-relative and no mid-capture resize retriggers ParentSize.
  const page = await browser.newPage({
    viewport: { width: 1200, height: 4000 },
    deviceScaleFactor: 2,
    colorScheme: "light",
  });
  for (const t of TARGETS) {
    await page.goto(`http://localhost:${PORT}${t.path}`, { waitUntil: "networkidle" });
    const el = page.locator(t.selector);
    await el.waitFor();
    await page.waitForTimeout(400); // let fonts + hydration settle
    // clip = element box expanded by PAD so the page background frames it
    const box = await el.boundingBox();
    if (!box) throw new Error(`no bounding box for ${t.selector}`);
    await page.screenshot({
      path: `${OUT_DIR}${t.out}`,
      clip: {
        x: Math.max(0, box.x - PAD),
        y: Math.max(0, box.y - PAD),
        width: box.width + PAD * 2,
        height: box.height + PAD * 2,
      },
    });
    console.log(`wrote reports/${t.out}`);
  }
  await browser.close();
} finally {
  preview.kill();
}
