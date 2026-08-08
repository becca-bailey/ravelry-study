# Champion codebook — manual coding of cohort winners

One row per designer in `data/champion-codes.csv` (create as you go;
columns below). Code what's observable today; note "gone" when a
property is unfindable — absence is data. Add a `notes` column for
anything that doesn't fit; the odd detail is often the essay detail.

| column | values | tests |
|---|---|---|
| designer | name as in dataset | join key |
| cohort_year | from dataset | |
| long_form | yes / some / no | H4 voice |
| photo_quality | pro / good-amateur / snapshot | H4 polish |
| cadence_gut | daily / weekly / monthly / dormant | H5 (automated pass later) |
| home_base | own-site / substack / ig-only / ravelry-only / dead | ownership |
| newsletter | yes / no | owned channel |
| archives_intact | yes / partial / gone / redirects-to-ig | durability |
| face_visible | face-forward / occasional / hands-only | person-as-product |
| models | self / pro-models / flat-lay / customers | polish + person |
| origin_story | job / hobby / parental-leave / unstated | leisure gate |
| claimed_start_year | year | cross-check cohort |
| sells_beyond_patterns | yarn / kits / books / classes / retreats / membership / none | monetization era |
| sponsorships_visible | yes / no | algorithm-era economy |
| multi_language | yes / no | professionalization |
| tech_edit_credits | yes / no | certification |
| test_knit_calls | yes / no | unpaid economy |
| community_run | ravelry-group / kal-mkal / discord / fb / none | community infra |
| institutional_ties | magazines / yarn-co collabs / books / knitstars / festivals / none | prestige currency |
| trend_behavior | wave-rider / lane-setter / classic-catalog | canon vs feed |
| ig_followers | number if visible | undercount ratio |
| notes | free text | everything else |
