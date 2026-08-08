# The Closing Window: Research Plan

*A study of cohort effects, platform infrastructure, and cumulative advantage in creative labor markets*

---

## The Core Argument

The hypothesis is this: access to an audience in creative fields has never been purely a function of talent or effort. It has always depended on structural conditions — specific platforms, infrastructure, and institutional forms that create low-friction discovery during a particular window of time. People who establish themselves during that window accumulate durable advantages that compound over time. People who arrive after the window closes face a fundamentally different cost structure, and no amount of individual effort can fully substitute for what the infrastructure used to provide for free.

The crafting community is the primary case study because it is narrow, has unusually rich longitudinal public data, and contains a natural experiment: Ravelry was founded in 2007 and has been continuous ever since, meaning it spans the pre- and post-Google Reader era, the rise and algorithmic shift of Instagram, and the professionalization of crafting content — all within a single measurable community.

---

## Research Questions

**Primary empirical question:** Is there a measurable cohort effect in the Ravelry designer community, where earlier-joining designers have systematically larger audiences than later-joining designers with equivalent output volume?

**Secondary questions:**

1. Has the relationship between output (patterns published, downloads) and audience size (fans) changed over time? That is, does a pattern published in 2010 generate more long-term following than an equivalent pattern published in 2020?

2. Are there identifiable inflection points in the data — around July 2013 (Google Reader shutdown) and June 2016 (Instagram's switch to algorithmic feed) — where the rate of fan accumulation per unit of output changes?

3. Does the gap between early-cohort and late-cohort designers widen, narrow, or hold steady over time? (Widening would suggest compounding; holding steady would suggest a floor effect.)

---

## Primary Data Source: Ravelry

### Why Ravelry

Ravelry has been running since 2007, which means it contains designers who built audiences during every relevant era: the RSS/blogging window, the early Instagram window, and the current post-algorithmic era. Every designer profile is public and includes join date, fan count, and pattern history. This is unusually clean longitudinal data for a creative community — most platforms don't expose join dates or long historical records.

### What to Collect

Per designer:
- Join date (month and year)
- Current fan count (Ravelry calls these "fans" on designer pages)
- Total patterns published
- Total pattern downloads/saves (Ravelry shows download counts per pattern)
- Pattern categories (knitting vs. crochet, garments vs. accessories, etc.)
- Whether patterns are free or paid
- Linked external platforms (Instagram handle, website URL)

Per pattern (optional enrichment):
- Publication date
- Download/save count at time of collection
- Price point

### Sampling Strategy

A stratified random sample by join year is the cleanest approach. Sample approximately 50–75 designers per join-year cohort from 2007 through 2023, applying a floor of at least 5 patterns published (to exclude hobbyists who posted once and disappeared). This gives you roughly 800–1,200 designers and lets you compare cohorts fairly without biasing toward the most successful designers.

The floor matters: "designers with at least 5 patterns" is a proxy for "people who made a genuine attempt to build a presence," which is the population you actually want to study. Adjusting the floor is a sensitivity check worth running.

### Data Access

Ravelry has a public API at `api.ravelry.com` — investigate current access and authentication requirements. Key endpoints to explore: designer profiles, pattern search (filterable by designer), and pattern details. If the API is restricted or rate-limited heavily, the fallback is scraping designer profile pages with Python/BeautifulSoup, which is the same approach used in the DHH corpus work. Ravelry's HTML structure is fairly stable.

The Instagram extension: many Ravelry designer profiles link an Instagram handle. Collecting those handles lets you pull current Instagram follower counts as a cross-platform audience measure, which would strengthen the argument by showing the pattern isn't just an artifact of Ravelry's internal discovery mechanics. This is optional for the core analysis but worth building in from the start if the data is accessible.

---

## Methods

The toolkit here maps directly onto the Language of Work methodology.

**Data collection:** Python, requests/BeautifulSoup or Ravelry API calls, Pandas for cleaning and structuring.

**Cohort analysis (descriptive):** Group designers by join year. For each cohort, calculate median and mean fan counts, controlling for patterns published. Visualize fan distributions by cohort — a box plot or violin plot showing the full distribution per year will make the compression effect visible if it exists. The visual alone may be the most communicable finding.

**Regression (inferential):** A basic OLS specification:

```
fans ~ join_year + n_patterns + n_downloads + pct_paid + category_dummies
```

If `join_year` has a significant negative coefficient after controlling for output volume, that's the core finding. A more flexible specification replaces `join_year` with cohort fixed effects to let each year's effect be estimated independently rather than assuming a linear trend.

**Inflection point analysis:** Run the regression separately on pre-2013, 2013–2016, and post-2016 cohorts, and compare the coefficient on `n_patterns` across periods. If more patterns yield less audience in later periods, that's evidence of a structural shift rather than just cohort composition effects.

**Rate of accumulation (longitudinal proxy):** Since you're collecting data at one point in time, you can construct `fans_per_year_since_joining` as an approximation of accumulation rate. This controls for the fact that early joiners have simply had more time. If this rate is declining for more recent cohorts, the window is closing in the clearest possible sense.

**Named limitations to state explicitly (in the Language of Work style):**
- Ravelry fans measure engagement within the Ravelry ecosystem, not total audience; designers with large Instagram followings but few Ravelry fans would be undercounted
- Survivorship bias: inactive designers from early cohorts may have left the platform, making early cohorts look more uniformly successful than they were
- Cannot separate "joined Ravelry early and compounded from there" from "was already established elsewhere (blog, magazine) and joined Ravelry with a pre-built reputation" — the cohort variable captures timing, not the mechanism
- One cross-sectional snapshot; fan counts reflect accumulated history, not current trajectory

---

## Qualitative Layer: Interviews

The quantitative finding tells you *whether* the pattern exists. The interviews tell you *what it felt like from inside it* — what discovery looked like in 2009 vs. 2019, what changed and when, what effort looks like now versus then. This is where the piece gets human.

**Who to find:** Aim for 5–8 designers spanning the full period, roughly:
- 2 who built their following between 2007 and 2012 (the Google Reader / early Ravelry era)
- 2 who built primarily on Instagram between 2012 and 2016 (before the algorithm change)
- 2–3 who have been building since 2018 or later

Ravelry's designer directory is searchable; you can identify candidates by join date and then reach out. Knitting podcast communities, Ravelry forums, and Instagram are also good sourcing grounds.

**What to ask:**
- How did you find your first readers/followers? What did that process look like?
- Did you feel the discovery environment change at any point? When, and how?
- What does building an audience require now that it didn't before?
- What would you tell someone starting today that you didn't have to think about when you started?

The goal is not to confirm the hypothesis but to get the texture right — including cases that complicate or contradict the pattern. If a designer who joined in 2020 has built a substantial audience, you want to know how, and whether the mechanism supports or undermines the structural argument.

---

## Broader Theoretical Frame

The crafting community is the case study. The argument is larger.

The same pattern appears across fields at different scales:
- **Journalism / independent writing:** The digital journalism hiring window (roughly 2010–2018) gave a specific cohort of writers institutional platforms, clip files, and agent attention. The writers now thriving independently on Substack — Petersen, Lenz, Sole-Smith — largely converted institutional credibility built during that window into portable audience. The window closed as BuzzFeed, Vice, The Awl, and Jezebel collapsed.
- **Tech labor:** Post-recession, pre-COVID (roughly 2012–2019), companies hired aggressively enough that non-traditional candidates — boot camp graduates, career changers — could get in. That window has largely closed.
- **Manufacturing:** The postwar golden age through the late 1970s allowed working-class entry without credentials. The people who built stable careers during that window retired with pensions; the people who arrived after the offshoring years found a different economy.

The academic framework connecting these cases already exists: Merton's Matthew Effect (cumulative advantage), Barabási's preferential attachment (rich-get-richer in networks), and platform lifecycle research documenting how early-stage platforms are more egalitarian than mature ones. You don't need to prove this framework from scratch — you need to demonstrate that it describes something specific and human in the crafting data, and then show it's not just a crafting story.

The place you put yourself inside the finding: you caught the tech window in 2015, deliberately and with clear eyes about what it was. You are now attempting to catch a different window in a field where the window has structurally narrowed. The research is not abstract.

### The AI Window: A Comparison Case

The AI boom is a useful endpoint for the series because it tests whether the window framework is purely descriptive — "this is how things have worked" — or whether something qualitatively new is happening. The AI window has several properties that distinguish it from every previous window and make it worth treating as a separate case rather than just the latest instance of the pattern.

**It closes other windows simultaneously.** Previous technology waves opened new lanes without sealing the ones they replaced. The internet didn't eliminate manufacturing jobs; it added a category. The AI window is actively automating the entry-level coding work that was the accessible on-ramp of the 2012–2019 tech window. Stanford's Digital Economy Lab found a 16% relative employment decline for workers aged 22–25 in AI-exposed software engineering roles. The American Prospect captured the irony directly: AI is eliminating the jobs that "learn to code" pointed people toward. A window that closes other windows while opening itself is a structurally different kind of event.

**The demographic access is narrower than the previous tech window, not wider.** The 2012–2019 tech window had an explicit democratization narrative — boot camps, career changers, no CS degree required. The AI window routes primarily through recent graduates whose university curricula were rebuilt around AI tools, through ML research pipelines that run through elite institutions, and through the specific cohort that had both the access and the leisure to experiment with these tools as they emerged. Forty-five percent of employers are now seeking "AI native" talent specifically — a phrase that means young enough to have grown up with these tools, which is age preference without naming age. The AI talent pipeline has been male-dominated for its entire history; "AI native" as a hiring category reproduces that pipeline rather than disrupting it.

**The wealth creation is going to capital, not workers.** Every previous window created some form of middle-class participation within the field — not equal to founders or investors, but real. The AI boom's wealth is concentrating almost entirely in equity holders of about five companies. GovAI's research is explicit: as AI matures, income shifts from labor to capital owners. The people completing AI certifications and listing "prompt engineering" on their résumés are adapting to survive, not participating in the wealth event.

**The urgency is partly manufactured by interested parties.** The "get on the AI bus before it leaves" pressure is being driven primarily by the companies that profit from wide AI adoption — the labs, the productivity software vendors, the training platforms. This isn't a conspiracy; it's just that the entity telling you there's a bus and you'd better hurry has a financial stake in that message. The emotional register is fear, not opportunity, and that's a meaningful departure from previous windows.

**The skills may not produce stable careers.** Previous windows — blogging, tech hiring, manufacturing — created careers that remained viable for a decade or more. "Prompt engineering" had roughly an 18-month window before it became a punchline. The specific technical skills that are valuable in AI now are being abstracted away by the tools themselves on a months-long timeline. Whether catching this bus leads anywhere stable is genuinely unclear in a way that previous windows were not.

The AI case is the one where you can note, without sensationalism, that the bus metaphor may no longer hold. Previous windows failed some people by closing. This one is doing something different: it's driving through the crowd on its way out of the station.

---

## Output: A Substack Essay Series

The primary output is a series of Substack essays. This is worth stating plainly rather than treating as a fallback, because the dynamics described in this research are exactly the dynamics determining how it gets distributed. Pitching to Wired or The Atlantic is possible and worth attempting at some point, but the probability is lower precisely because of what this project is about: access to those platforms depends on credentials and existing audience that the project itself is documenting the difficulty of acquiring. Writing the series on Substack is not the consolation prize — it's the honest response to the structural conditions, and it mirrors the position of every creator this research is about.

There is also a practical argument for Substack first: a completed, data-backed essay series is a better pitch vehicle than a cold idea. "I've written a five-part investigation into platform economics and creative labor, with original Ravelry data, that has found X" is a different pitch than "I have an idea." The series builds the asset the pitch needs. That's its own ironic echo of the dynamics being described — you need the thing to get the thing — but it's at least a path.

### Rough Series Arc

The order can flex, but one logical sequence:

**Essay 1: The Bus** — Establish the framework through the crafting community. The Ravelry data is the backbone. Open on the Guatemala bus story or equivalent scene; build to the data; close on the question the series will answer. This is the empirical anchor that makes everything else more than cultural commentary.

**Essay 2: The Building With the Door In It** — The journalism golden age, 2010–2018. Lindy West and The Stranger. Anne Helen Petersen at BuzzFeed. The specific infrastructure — alt-weeklies, digital publications with institutional prestige, agent attention flowing through known outlets — that no longer functions in the same way. This essay is more qualitative, built on cases and interviews rather than data.

**Essay 3: Learn to Code** — The tech window, roughly 2012–2019. Draw on the 2017 essay you wrote, which already makes this argument with unusual clarity. The "learn to code" discourse as a political deflection. The window closing. The position this leaves you in now. You are deepest inside the finding in this essay.

**Essay 4: The Bus Is Driving Through the Crowd** — The AI window as a different kind of event. The window-that-closes-other-windows structure. The demographic narrowing. The wealth going to capital. The fear-based urgency. How this case tests whether the framework is descriptive or whether something new is happening.

**Essay 5: The Ambition Penalty** — The synthesis. What these patterns mean for how we understand ambition, individual effort, and structural opportunity. The book passage you photographed belongs here. This is the essay that asks the "so what" back to the reader rather than delivering a tidy answer.

The series doesn't need to publish in this order. Essay 3 or Essay 5 might make the stronger opener depending on what you want the entry point to be.

### A Note on the Irony

The series is being written on a platform where discovery is structurally difficult for new writers — which means the work that describes the problem is subject to the problem. Name this somewhere, probably in Essay 5 or in a brief author's note. It's not a failure of strategy. It's accurate.

---

## Sequencing

**Phase 1 — Data access (1 week):** Investigate Ravelry API access. Build a prototype scrape of 20–30 designer profiles across different join years. Confirm which variables are actually accessible and clean. Adjust the data plan based on what you find.

**Phase 2 — Sample design and collection (2 weeks):** Define the full sampling strategy, run the collection, clean the data. This is where Pandas earns its keep. Flag data quality issues as you go — they become named limitations in the piece.

**Phase 3 — Analysis (1–2 weeks):** Cohort visualization, regression, inflection point tests. Let the findings drive the framing rather than forcing the data to confirm a predetermined conclusion. If the pattern is weaker than expected, that's also interesting.

**Phase 4 — Interviews (parallel with phases 2–3):** Start identifying and reaching out to subjects early, because scheduling takes time. Aim to have interviews done before you start drafting so the voices can shape the structure.

**Phase 5 — Writing:** The essay opens on a scene, not a thesis. The data lands near the middle. You place yourself inside the finding before the end. The close doesn't manufacture resolution.

---

## One Thing to Settle First

Before starting data collection, decide on Essay 1's scope: is the Ravelry data enough on its own to carry a standalone piece, or does Essay 1 also need the interview layer to be publishable? The data analysis alone could be the backbone of a shorter, sharper essay; adding interviews makes it richer but takes longer. 

Starting with the data is the lower-risk path: it moves, you learn what the numbers actually show, and you can add the qualitative layer in revision. The worst outcome is that you build the whole interview apparatus around a finding the data doesn't actually support. Let the Ravelry scrape run first.
