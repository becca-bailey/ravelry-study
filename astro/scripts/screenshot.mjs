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
const TARGETS = [
  { path: "/", selector: "#window-chart", out: "window_explorer.png" },
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
  const page = await browser.newPage({
    viewport: { width: 1200, height: 800 },
    deviceScaleFactor: 2,
    colorScheme: "light",
  });
  for (const t of TARGETS) {
    await page.goto(`http://localhost:${PORT}${t.path}`, { waitUntil: "networkidle" });
    const el = page.locator(t.selector);
    await el.waitFor();
    await page.waitForTimeout(400); // let fonts + hydration settle
    await el.screenshot({ path: `${OUT_DIR}${t.out}` });
    console.log(`wrote reports/${t.out}`);
  }
  await browser.close();
} finally {
  preview.kill();
}
