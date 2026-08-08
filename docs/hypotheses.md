# Working Hypotheses (2026-08-07)

Becca's refined hypotheses, recorded before seeing pilot data, with
operationalizations. These extend the research plan's core cohort question
into distributional territory: the claim is about the *shape* of success
within cohorts, not only its average level.

## The enhanced three-cohort hypothesis (final form, 2026-08-07)

Three cohorts, defined by entry infrastructure:

1. **Traditional print media** (employment, magazines, yarn companies)
2. **Early blogging** (owned platforms, RSS, early Ravelry)
3. **Instagram era** (algorithmic feeds)

The claims, in becca's words: in the print cohort, designers could make a
living but were less likely to reach cult celebrity status within the
community. By the Instagram era, the landscape became dominated by a few
celebrities who are disproportionately successful. At each stage it was
harder to break through, but the ones that did became more successful.

Formally: across cohorts the **floor falls and the ceiling rises**. The
distribution of designer success shifts from a middle-class-occupation
shape (compressed, livable middle, low ceiling) toward winner-take-all
(thin middle, extreme tail). Two monotone predictions per transition:

- P(reaching a modest audience threshold | genuine attempt) **decreases**
- E(success | top decile of cohort) **increases**

**Persistence as the viability proxy (added after discussion).** With no
income data, continued activity stands in for economic viability: people
who had to take day jobs to make a living are less likely to still be
publishing. Operationalization:

- *Fixed-tenure survival:* share of each cohort still publishing N years
  after their first pattern (N = 5, 8, 12). Comparing cohorts at the SAME
  career age neutralizes the "recent cohorts haven't had time to quit"
  asymmetry; print, blog, and early-Instagram cohorts all have 8+ years
  of observable history.
- *Survival curves:* Kaplan-Meier time-to-exit per cohort, exit defined
  as no new pattern for 3+ years, with right-censoring at collection
  date. Cohort-specific hazards are the formal version of the floor
  claim.
- Both need only `first_pattern_published` / `last_pattern_published`
  plus per-pattern dates — already in the collection plan.

Caveats to name: (1) exit ≠ failure — retirement (the print cohort is
older), and success-pivots away from pattern publishing (Flood into
manufacturing, Herzog stepping back post-CustomFit) both read as exit;
where possible flag known pivots via the anchor list. (2) Persistence ≠
income in the Instagram era — publishing alongside a day job is cheap, so
late-cohort persistence can overstate viability; the proxy is
conservative in the direction that works against the hypothesis, which
strengthens any decline that still shows. (3) Left-truncation: print
designers who exited before Ravelry existed never appear at all, so the
observed print cohort is success-biased — their survival rates are upper
bounds. (4) Validate the proxy in interviews: ask directly whether and
when other income was necessary.

**The flicker refinement (2026-08-08, full dataset).** The era
transitions have structure the original hypothesis missed:

- *Interregnum, 2013–15:* the class of 2015 is a measured trough
  (median 82 vs ~154 for 2013–14 classes). Mechanism: RSS discovery was
  dead but Instagram was still chronological/follower-bound — a gap
  between discovery regimes with both windows shut.
- *The algorithm's generous opening, 2016–17:* the class of 2016 is the
  strongest entering class in the dataset (median 208; deep upper
  ranks — PetiteKnit, eri shimizu, Chantal Miyagishima, multiple 5k+
  designers; NOT a one-outlier artifact — median without PetiteKnit is
  194). New feed surfaces subsidize discovery while bootstrapping
  engagement. Every algorithm-era anchor entered 2014–16.
- *Enclosure, 2018–:* classes of 2017+ decline steadily as reach
  throttling arrived.

Refined era sequence: window (blogs) → interregnum (2013–15) → brief
second window (early algorithm, 2016–17) → enclosure. The window
didn't just close; it flickered, and the flicker minted the era's
superstars. Corollary: generous phases shorten across successive
platforms (blogs ~a decade, algorithmic IG ~2 years, TikTok arguably
none). Caveats: single-year bootstrap CIs overlap — the dip/bump is
the leading interpretation, not yet a certified finding; must survive
age-adjustment and craft splits in Phase 3.

**What the Ravelry data can and can't say.** The celebrity-concentration
claims are directly testable (Gini, median-vs-p95, quantile regression —
see H2/H3 below, now read as cross-cohort comparisons). The "could make a
living" claim for the print cohort is NOT in Ravelry data — their income
was employment and commissions, invisible to fan counts. That claim rests
on the qualitative layer and secondary sources (trade press, interviews
with Gaughan/Weisenberger-generation designers). Relatedly, fan counts
mean different things per cohort: for print designers Ravelry audience
was never the currency; for Instagram designers it undercounts (audience
lives off-platform). State both in the limitations, and lean on
within-cohort *shape* comparisons, which are robust to level differences
in what fans measure.

## H1 — Older creators have steadier engagement

Early-cohort designers accumulated audience under low-friction discovery
and hold it durably; their engagement is consistent rather than spiky.

**Tests:**
- *Pattern-level spread:* per designer, the coefficient of variation of
  favorites across their patterns. H1 predicts lower within-designer
  variance for early cohorts — engagement arrives from a standing audience
  rather than from individual patterns going viral.
- *Panel trajectories (if archived designer pages carry fan counts):* fan
  count deltas across Wayback captures. H1 predicts early-cohort designers
  show smooth, roughly linear accumulation; late-cohort successes show
  step functions around breakout moments.
- *Longevity proxy:* gap between first and last publication dates, and
  favorites on recent patterns relative to peak patterns.

## H2 — Late-cohort winners exist but are fewer and disproportionately successful

The market has newer dominant designers (Andrea Mowry, PetiteKnit, the
Ranunculus designer), characterized by unusual skill, especially at social
media. Success in late cohorts is concentrated in a thinner tail.

**Tests:**
- *Within-cohort concentration:* Gini coefficient (or top-decile share) of
  fan counts by cohort. H2 predicts concentration rises for later cohorts.
- *Median vs. tail divergence:* p50 and p95 fan counts per cohort. H2
  predicts the median falls across cohorts while the p95 falls less, holds,
  or rises — the middle compresses, the top persists.
- *Social-media covariate:* has-Instagram (and later, Instagram follower
  counts) interacted with cohort. H2 predicts the Instagram coefficient
  grows across cohorts: cross-platform skill matters more as internal
  discovery weakens.
- *Case anchors:* pull the named designers' full records as known reference
  points (all are post-2015 breakouts). Their profiles should look like
  outliers relative to their cohort's distribution, and their qualitative
  stories (interview layer) should show the social-media mechanism the
  quantitative data can't measure directly.

## H3 — The closing window raises the entry bar and the payoff

As discovery friction rises, the skill threshold for building any audience
increases, but those who clear it capture more than early-era equivalents
did — fewer winners, bigger wins.

**Tests:**
- *Conditional returns:* among top-decile designers within each cohort,
  fans per pattern published. H3 predicts this conditional payoff is flat
  or increasing across cohorts even as the unconditional median falls.
- *Entry survival:* share of each cohort's designers clearing modest
  audience thresholds (100, 1,000 fans). H3 predicts monotonic decline.
- *Quantile regression* of fans on cohort + output controls: H3 predicts
  strongly negative cohort coefficients at low/middle quantiles,
  attenuated or reversed at the top quantiles.

## Named case anchors (added 2026-08-07, from becca's influencer research)

Machine-readable list in `data/anchors.yaml`. Ravelry records for the
designer anchors get pulled alongside the pilot for distributional
placement (each should sit far outside their cohort's typical range).

**Early cohort (blog/RSS-era, ~2000–2010).** Jared Flood (Brooklyn Tweed,
blog 2005), Ysolda Teague (Knitty break, business 2008), Kate Davies,
Stephanie Pearl-McPhee (Yarn Harlot, essayist not designer), Kay Gardiner &
Ann Shayne (Mason-Dixon → Modern Daily Knitting), Clara Parkes (Knitter's
Review, 2000), Amy Singer (Knitty, 2002), Jess & Casey Forbes (Ravelry
itself, 2007). Shared shape becca's source identifies: publish free for
years → readership → book → a business that isn't content (manufacturing,
retail, software, supply chain) — and they own their platforms (mailing
lists, sites, shops), which is why they survived the collapse of blog
traffic. This sharpens H1's mechanism: early-cohort steadiness may be
*owned-channel distribution*, not just accumulated audience.

**Late cohort (algorithm-era, 2015+).** PetiteKnit (Mette Wendelboe
Okkels, ~2M Instagram, patterns since 2016; anchor of the Danish wave —
Anne Ventzel, Lærke Bagger, Fiber Tales, Spektakelstrik, Aegyoknit),
Andrea Mowry (Find Your Fade), Stephen West (Westknits — note: Knitty-era
entry, algorithm-era scale; a bridge case), Caitlin Hunter (Boyland
Knitworks, Tegna), Joji Locatelli, Isabell Kraemer. Model: the person and
aesthetic are the product; patterns are the monetization.

**Institutional cohort (pre-internet entry, ~pre-2005).** Added
2026-08-07: designers who entered through traditional publishing and
industry employment — a job at a yarn company, magazine commissions,
fashion manufacturing. Julie Weisenberger (knitwear company in the 1980s,
sold to Bendel and Nordstrom, yarn-company design through the 1990s) and
Norah Gaughan (yarn-company staff design, Berroco design director) are the
type cases; Kim Hargreaves (Rowan) likely fits too. Their entry
infrastructure was employment, not audience — which makes knitting a
microcosm of the whole series: the same community contains an
institutional-employment window (parallel to manufacturing), an
owned-platform window (parallel to blogging/journalism), and an
algorithmic window (parallel to the present), in sequence.

Predictions for this cohort: Ravelry fan counts modest relative to
offline stature (audience was never their currency); back-catalogs
entered Ravelry as bulk imports with publication dates predating the
platform; revenue routes through publishers/companies rather than
direct pattern sales.

*Operationalization — this cohort is detectable in the data already
collected:* (1) first published pattern predates Ravelry (pre-2007
`published` dates — the pilot's "imported back-catalog" designers like
Elsebeth Lavold, first=1998, and Vivian Høxbro, first=2004, are this
cohort, not noise to exclude); (2) `pattern_sources` composition — the
API exposes each pattern's source type (book, magazine, self-published
download), so share-of-patterns-in-print vs. self-published quantifies
how institutional a designer's route was, for every designer in the
sample.

**Third model, cohort-orthogonal (system-builders).** Amy Herzog (Fit to
Flatter tutorials → books → CustomFit software) and Julie Weisenberger
(Cocoknits Method + physical tools). Credibility from solving a technical
problem, not from being watchable. Useful as contrast cases: if H2/H3 are
about social-media skill as the late-era entry ticket, the system-builder
route is an alternative door — does it still open post-2016?

**Gatekeepers / prestige currency (context, not data rows).** Laine
magazine, Long Thread Media, Shetland Wool Week patronage, Vogue Knitting
Live, Edinburgh Yarn Festival, Rhinebeck, Woollinn. Becca's source notes
the highest-reach (PetiteKnit) and highest-prestige (Shetland patron)
circles barely overlap — two different games. Worth one line in the essay;
also a warning that "audience size" is only one currency of success.

**Measurement notes.** Parkes, Singer, Pearl-McPhee, Gardiner/Shayne, and
the Forbeses have no meaningful Ravelry designer records — they are
interview/context anchors, not data rows. West and Teague have both
Knitty-era entry and current scale, making them the best longitudinal
Wayback case studies. PetiteKnit is the sharpest test of the
Ravelry-undercount limitation: her fan count vs. ~2M Instagram followers
quantifies how much audience the internal measure misses.

## H4 — Polish (added 2026-08-07, later-phase)

Becca's hypothesis: blog-era creators could be less polished and use a
different (more personal) voice than Instagram-era creators, whose
presentation is professionalized. The rising skill floor (H3) should be
visible in the *artifacts themselves*, not just the outcomes.

**Data:** pattern `notes` (designer's own description/marketing copy) is
in every pattern-detail response — already accumulating in the raw cache.
Also usable: photo counts, size-range width, offered languages,
"tech edited by" / "test knit" credits, external links in notes.

**Methods (direct reuse of the Language of Work pipeline):**
1. *Semantic axes:* curate pole-sentence axes — personal/diaristic voice
   ("I made this for my sister's wedding") ↔ product copy ("Written in 9
   sizes, charted and written instructions, tech edited"). Embed notes,
   project, score by cohort. The lowork axis machinery (embedding cache,
   build/score/validate, circularity check) ports directly.
2. *Surface features (cheap, interpretable):* notes length, structured
   sections, size count, language count, professional credits, emoji,
   first-person density. Professionalization index by cohort.
3. *LLM polish rubric* with hand-label agreement protocol (lowork M-gate
   style) as validation of the axis scores.
4. *(Stretch)* photo polish via vision-model classification of
   first_photo URLs (model shots / styled flat-lays vs. snapshots).

**The critical confound — text is live, not historical.** Pattern notes
are editable; a 2009 pattern's notes may have been rewritten in 2022
(`updated_at` tells us). Mitigations: (a) restrict era comparisons to
patterns where updated_at ≈ created_at; (b) use Wayback captures of
designer/pattern pages for era-authentic text — the same archived pages
already identified for the H1 panel; (c) treat live-text results as
"current voice of designers by cohort" (interesting in itself — did
blog-era designers professionalize their old copy?) rather than
"voice of each era."

Sequencing: Phase 3.5/4 — needs no new collection decisions now beyond
making sure Phase 2's pattern-detail fetches persist `notes` (they do:
the raw cache keeps full responses).

## H5 — Labor cadence case studies (added 2026-08-07, later-phase)

Becca's question: how often did era-defining figures have to publish?
E.g. Stephanie Pearl-McPhee's blog-era essay cadence vs. Andrea Mowry's
daily Instagram presence. Not a scale analysis — 5–10 case figures.

**Feasibility (probed 2026-08-07):**
- *Blogs:* live monthly archives are parseable — yarnharlot.ca/2007/03/
  returns ~10 posts for that month. Cadence countable per month across
  the whole blog era from the sites themselves (Yarn Harlot, Mason-Dixon,
  Brooklyn Tweed blog), with Wayback backfill where sites died.
- *Instagram:* profile pages can't be crawled historically, but Wayback
  captures preserve the meta description — followers AND total post
  count at each capture date. First-differences give posts/year and
  follower growth. Coverage is thin for mid-size accounts (Mowry: 3
  captures — 2014, 2020, 2022 — plus today's live count of 3,445 posts)
  and likely denser for PetiteKnit-scale accounts. Coarse but honest:
  interval-average cadence + growth curve per anchor.

**The claim this tests:** the labor contract changed across windows —
not just how much you publish but what kind of work it is. A blog-era
unit was a 1,000+ word essay every few days to an audience you owned; an
algorithm-era unit is a styled photo/reel daily to a feed that decays in
48 hours. Cadence numbers plus content-type description make the
"treadmill speed" claim concrete in the essays.

**Caveats:** IG post counts exclude stories and deleted posts, so
algorithm-era labor is *undercounted* (conservative direction). Blog-era
invisible labor (comment moderation, newsletters) likewise. Cadence ≠
hours; the interviews should ask directly about weekly content hours
then vs. now — this is a strong interview question for every cohort.

## H6 — Artifact durability (added 2026-08-07)

Becca's hypothesis, extending H5: the bar gets higher AND the product
gets less durable. A 2005 blog sock pattern still draws daily use;
algorithm-era hits spike when everyone makes them, then decline steeply.
Classic patterns are annuities; trend patterns are wages.

**Measurement — verified feasible (2026-08-07):**
`/projects/search.json?query=<pattern name>` works with the read-only key
and returns project records with `started`/`completed`/`created_at` dates
and `pattern_id` (for validating hits; the `pattern-id` param itself is
ignored — quirk noted, proper param name may exist in the login-walled
docs). Musselburgh: 50,708 projects retrievable. A random sample of
~500–1,000 projects per pattern gives the usage-date histogram.

**Metrics per pattern:**
- *Front-loading index:* share of lifetime projects started within 12
  months of publication. Prediction: rises sharply for algorithm-era
  patterns.
- *Usage half-life:* months until half of observed projects occurred.
- *Age-N vitality:* projects/month at age 3+ relative to peak year.
  "Still alive at 5" as a binary is essay-friendly.

**Sample design:** the head-to-head is anchor mega-hits (Find Your Fade
2017, Musselburgh 2020, Sophie Scarf 2021) vs. long-lived classics
(Hitchhiker 2011, Clapotis 2004, Baby Surprise Jacket) plus a random
slice of ordinary patterns per cohort from the pilot designers.

**Confounds to normalize:** (1) platform activity varies by year — a
pattern's project counts must be normalized by total Ravelry projects
started that year (estimable by sampling projects search unfiltered);
(2) early years under-recorded (Ravelry small before ~2009) — affects
pre-2009 patterns' early curves; (3) seasonality (year-granularity
smooths it); (4) survivorship — we only see patterns that still exist.

**Why it matters for the argument:** H5 × H6 is the labor-and-reward
story in one frame. Blog era: slower cadence, durable artifacts —
effort compounds. Algorithm era: daily cadence, decaying artifacts —
effort must be re-performed. Same hours, different asset classes. If the
data shows rising front-loading across pattern cohorts, "the product is
less durable" stops being a vibe and becomes a curve.

## H7 — The crochet lag (added 2026-08-07)

Becca's hypothesis: the crochet window opened later and stayed open
longer, because crochet's popularity surge is recent (short-video era,
pandemic beginners) while its historical canon is thin.

**Mechanism:** windows are open where new demand meets a small
back-catalog. Crochet had (a) a thinner canon — lower cold-start wall,
fewer immortal classics crowding the popularity lists; (b) a recent
demand surge (TikTok-native craft, pandemic cohort of new crocheters
needing patterns); (c) historically lower status in the community —
fewer entrenched incumbents. Same theory, different clock.

**Why it matters:** this is a within-dataset replication test. If the
window framework is real, crochet should show the SAME cohort shapes as
knitting, shifted later by ~5–8 years: a still-livable middle in recent
crochet cohorts where knitting's has hollowed, higher fans-per-pattern
for late crochet entrants, and (eventually) the same closing.
Difference-in-differences across sub-crafts, all inside one platform's
data — stronger evidence than any single-craft trend.

**Test:** run every cohort analysis (median fans, middle-band share,
Gini, fans-per-pattern) split by craft. We already collect
n_knitting/n_crochet per designer and craft per pattern. Pilot hints
support it: crochet share of output rises monotonically across cohorts
(30% → 56% → 63%), and several of the pilot's rare late-cohort
breakouts are crochet designers.

**Supporting anecdote (becca's lived experiment):** a self-supporting
crochet designer described test-knitting as her entry point years ago;
becca followed the same path and found it now oversubscribed with
unlikely payoff — cohort-correct advice received one cohort too late.

## Cautions

- **Survivorship cuts both ways.** Early-cohort failures may have left the
  platform entirely (making early cohorts look uniformly steady), while
  late-cohort failures are still visible. Any concentration comparison
  needs this named, and the ≥5-patterns floor partially mitigates it.
- **Fan counts are Ravelry-internal.** PetiteKnit-scale designers may hold
  most of their audience on Instagram; the Instagram-handle extension is
  what keeps H2 honest.
- **"Skill" is not directly measurable.** The quantitative side can only
  show the distributional signature (fewer, bigger winners); the interview
  and case-study layer carries the mechanism claim. Ratings
  (`rating_average`) and photo presence are weak proxies at best.
- Recorded before seeing pilot results, so the data can still say no.
