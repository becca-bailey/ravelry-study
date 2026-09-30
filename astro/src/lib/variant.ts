"use client";

import { useEffect, useState } from "react";

/* Chart presentation variant, read from the URL (?variant=article).

   "site" is the full research view: badges, every milestone, method notes.
   "article" is the stripped-down version for the essay/interview
   screenshots — only what the surrounding prose needs. SSR renders "site";
   the flag is picked up after hydration, before the screenshot script
   captures (it waits for network idle + a settle delay). */

export type Variant = "site" | "article";

export function useVariant(): Variant {
  const [variant, setVariant] = useState<Variant>("site");
  useEffect(() => {
    const v = new URLSearchParams(window.location.search).get("variant");
    if (v === "article") setVariant("article");
  }, []);
  return variant;
}
