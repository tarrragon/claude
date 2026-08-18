# Value Investing Assessment

> **Role**: Operational reference for the `business-analysis` skill — extends Step 4 (valuation) from "is this business viable" to "is this stock mispriced relative to intrinsic value" (Buffett-style value investing).
>
> **When to read**: When the analysis goal is an investment decision on a listed company — identifying whether current price underestimates durable earning power, or whether apparent cheapness is a trap.

## Boundary: Business Analysis vs Investment Analysis

Business analysis answers "is this a good company" (margins, positioning, strategy). Investment analysis answers "is this a good price for this company" — a comparison that requires data business analysis alone never collects: historical valuation bands, market cap series, capital efficiency ratios. A complete company analysis with no price data cannot support a buy/avoid judgment. State this limitation explicitly rather than letting a business-quality conclusion masquerade as an investment recommendation.

## Three-Gate Screen

All three gates must pass. A failure at any gate vetoes the investment regardless of the other two — where "the investment" means the compounder thesis specifically: a gate failure vetoes compounder classification, not investability under every discipline (see School Routing below for names that fail here but qualify under a different ruler).

### Gate 1: Moat Durability

The moat test is pricing power through downturns — not margin level in good years.

| Check | Method | Pass signal |
| --- | --- | --- |
| Margin stability across cycles | Pull 10-year gross margin series; find the worst 2 years | Margin floor stays above peer median even in bad years |
| Pricing power direction | Did prices rise with (or faster than) input costs during inflation? | Cost pass-through within 2-3 quarters |
| Customer switching cost | What must a customer change to switch supplier? | Concrete switching activities (production line recalibration, recertification), not just habit |
| Moat type identification | Scale / network / switching cost / brand / regulatory license / formula-patent | At least one structural moat, named specifically |

Single-year high margin is a cycle observation, not a moat observation. A company earning 21% gross margin at the top of a livestock price cycle may have a structural floor of 16% — the moat is the floor, not the peak.

### Gate 2: Management Quality (Capital Allocation)

Judge management by what they do with retained earnings, not by narrative.

| Check | Method | Red flag |
| --- | --- | --- |
| Retained earnings test | Over 10 years: for each $1 retained (not paid out), did market value grow more than $1? | Retained capital compounding below index returns |
| Dividend consistency | 10-year dividend record | Cuts without corresponding earnings collapse; erratic policy |
| M&A track record | Did past acquisitions reach their stated targets? | Serial acquisitions with no follow-up disclosure of returns |
| Capex return trail | Prior expansion projects: did they generate the projected revenue/margins? | Capex direction announced but returns never reported |
| Insider alignment | Director/major shareholder ownership trend | Insiders reducing while promoting growth narrative |

### Gate 3: Price Below Intrinsic Value

| Check | Method | Note |
| --- | --- | --- |
| Normalized earnings basis | Strip one-time items (cycle windfalls, disposal gains) before applying any multiple | Valuing peak-cycle EPS at average multiples double-counts the good year |
| Historical valuation band | Current P/E and P/B vs the company's own 10-year percentile | "13x" is meaningless without knowing whether the stock's band is 8-15x or 12-25x |
| Owner earnings | Net income + D&A - maintenance capex (exclude growth capex) | Requires splitting maintenance vs growth capex — ask what spending merely keeps current revenue |
| Margin of safety | Buy only when price is materially below conservative intrinsic estimate | The discount absorbs estimation error; without it, precision of the estimate becomes the bet |

## Capital Efficiency Screen

Margins measure product economics; ROE measures owner economics. A 13% gross margin business with high asset turnover can be a better owner outcome than a 30% margin business that consumes capital.

- **10-year ROE series**: consistent ROE above ~15% without rising leverage is the primary quantitative filter.
- **Holding-company numerator discipline**: for a parent that consolidates partially-owned subsidiaries, ROE must use parent-attributable profit over parent-attributable equity. Using total consolidated profit (which includes noncontrolling interests) against parent equity overstates ROE — field case: a holding company's ROE band inflated from ~14-19% to ~22-28% by this mismatch, flipping its quality-gate verdict. Sanity check: numerator ÷ share count must reproduce reported EPS.
- **Holding-layer dilution**: a holding layer's ROE is structurally diluted relative to its best operating subsidiaries — judge capital-allocation culture at the operating-entity level, and note that buying the holding layer buys the whole portfolio, not the crown jewel.
- **DuPont decomposition**: ROE = net margin × asset turnover × leverage. Identify which lever drives ROE — turnover-driven and margin-driven ROE are durable; leverage-driven ROE is fragile.
- **ROIC vs WACC**: value is created only when return on invested capital exceeds cost of capital. High-capex transformations must eventually show ROIC above hurdle, or the growth destroys value.

## Taiwan-Specific Governance Signals

| Signal | Where to find | Interpretation |
| --- | --- | --- |
| 董監質押比率 (director share pledges) | Public company filings (MOPS) | High or rising pledge ratios precede governance crises; pledged shares create forced-selling and control-defense incentives misaligned with minority shareholders |
| Related-party transaction magnitude | Annual report footnotes | Rising intercompany volume shifts profit between entities; margin of any single entity becomes unreliable |
| Ownership dispute activity | News + shareholding changes | Active control contests divert management attention and can trigger defensive asset sales at bad prices |
| Cross-shareholding / JV opacity | Group structure mapping | Unlisted JVs carrying critical operations (production, procurement) escape disclosure — risk hides where reporting doesn't reach |

## Value Window Identification

The recurring pattern for entry timing: reported earnings compressed by a one-time or cyclical shock while structural signals remain positive.

| Signal set | Reading |
| --- | --- |
| Earnings down + capex up + operating cash flow positive + new products launching | Transforming under pressure — market prices the compressed earnings, structure is improving unpriced |
| Earnings down + capex frozen + short-term debt rising | Being crushed — cheapness is justified |
| Earnings up sharply + windfall component identified | Cycle peak — normalize before valuing; often the worst entry despite best headlines |
| Complex holding structure obscuring operating earnings | Potential mispricing from opacity — but only actionable after YOU decompose the one-timers; unresolved opacity is your blind spot too |

## Value Trap Taxonomy

Cheap is a starting condition, not a conclusion. Three trap types that pass a naive price screen:

1. **Damaged-moat trap**: price collapsed because the moat (brand trust, license, technology relevance) was structurally impaired. Test: does the moat have a credible recovery path with a timeline, or does recovery depend on customers forgetting? Consumer trust damage routinely persists 5-10 years.
2. **Governance trap**: assets and earnings intact but controlled by parties whose interests oppose minority shareholders. No price is low enough when the person allocating your capital is working against you.
3. **Structural-decline trap**: low multiple on earnings that are themselves in secular decline (technology substitution, demand migration). The E in P/E keeps falling to meet the P.

## Valuation Band Reading: Derating vs Cheapness

A price at the bottom of the historical band is only a margin of safety if the band itself is stable. When the band's ceiling compresses for consecutive years (e.g. 25-34x → 20-27x over three years), the market is structurally re-rating the sector's growth, and "below the old band" is the new normal, not a discount. Distinguish the two before concluding cheapness:

| Observation | Reading | Action implication |
| --- | --- | --- |
| Price at band bottom, band stable 5+ years | Sentiment or one-time discount | Candidate margin of safety |
| Price mid-band of a band that keeps compressing | Structural derating in progress | Buying is a bet the derating has ended — demand extra compensation (dividend yield floor, normalized-earnings discount) |
| Price below even the compressed band | Market pricing in further deterioration | Check the trap taxonomy before touching |

## School Routing: Compounder vs Special Situation

A name that fails the three gates is not automatically uninvestable — it may belong to a different discipline. Route explicitly:

- **Compounder (Buffett)**: passes all three gates; the return engine is retained-earnings compounding; holding period is indefinite; the key risk is moat erosion.
- **Asset discount / special situation (Graham)**: fails the quality gate but trades below a conservatively-computed asset value (e.g. a listed stake alone ≈ the company's own market cap, with operating businesses priced near zero). The return engine is discount convergence; the key risks are that the discount is permanent (family-holdco discounts often are) and that no catalyst exists. A special-situation thesis without a named catalyst is a hope, not a thesis.

Names that fit neither ruler get an explicit residual label instead of a silent "neither": **turnaround speculation** (return engine is expectation revision — a self-consistent strategy, but not value investing under either school) or **governance-trap exclusion** (no price qualifies while capital allocation is controlled against minority holders — see Value Trap Taxonomy). An undefined residual bucket hides the difference between watch-list, speculation, and permanent exclusion.

State which ruler you are using. Mixing them — e.g. justifying a failed quality gate with an asset-discount argument while expecting compounder-style holding comfort — produces positions nobody knows how to manage.

## Point-in-Time Verdict: Flip Conditions Are Output

An assessment dated to a specific price is stale the day the price moves. Make every verdict replayable by attaching, per name, the concrete conditions under which the verdict flips — price triggers (multiple on normalized earnings, yield floor) and structural triggers (governance ruling, capital-return policy announcement, ROE crossing a threshold with evidence). The flip-condition list is a mandatory output section, not commentary — the reader's action is to set alerts on it, not to memorize the verdicts.

For names with a pending binary event (lawsuit ruling, regulatory decision), write **both scripts in advance**: the same event can flip the name in opposite directions (a ruling that triggers a forced-selling window creates entry; a ruling that ignites a control contest converts the name into a governance trap). Deciding the reading after the event invites narrative-fitting.

## Output Addition

When this reference is used, extend the standard output with:

1. **Three-gate scorecard** (moat / management / price — pass, fail, or insufficient data per gate)
2. **Data sufficiency statement** — which of the required series (10-year ROE, valuation band, pledge ratio, owner earnings) were actually obtained; a gate assessed without its data is marked "insufficient data", never silently passed
3. **Value window classification** (transforming-under-pressure / crushed / cycle-peak / opacity) with the specific signals observed
4. **Trap check** — explicitly test all three trap types before concluding a low price is an opportunity
5. **Flip-condition list** — per name, the price and structural triggers that would change the verdict (see Point-in-Time Verdict section); for pending binary events, both scripts written in advance
6. **School label** — compounder or special situation, stated explicitly (see School Routing section)
