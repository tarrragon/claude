# External Shock Analysis and Structural vs One-Time Decomposition

> **Role**: Operational reference for the `business-analysis` skill. Consult when a company's margin or earnings change sharply, or when an industry faces cost/demand disruption.

## Shock Type Classification

Classify the shock before deciding whether the affected company needs short-term coping or long-term transformation.

| Type | Examples | Transmission Speed | Duration | Reversibility Test |
| --- | --- | --- | --- | --- |
| Supply-side | War disrupting commodity exports (Ukraine grain, Middle East oil), disease outbreak (ASF reducing pig supply), natural disaster (earthquake damaging fab) | Fast (weeks) | Depends on whether the source is removable | Check if alternative supply sources exist and how fast they activate |
| Demand-side | Pandemic lockdown (restaurant demand collapse), financial crisis (consumer spending contraction) | Fast to medium | Typically 1-3 years | Ask whether demand is deferred (will return) or destroyed (permanently gone) |
| Structural shift | Energy transition (fossil to renewable), AI displacement (knowledge work), regulation change (emission standards) | Slow (years) | Permanent | No reversibility — the question is adaptation speed |

**Mixed-type identification**: A single event can trigger multiple types simultaneously. Feed cost spikes from the Ukraine war were a supply-side shock (reversible — grain prices eventually stabilized), but they accelerated a structural shift (irreversible — processing capacity built during the crisis stays). Classify each consequence independently.

## Structural vs One-Time Decomposition

When a company's margin jumps or drops significantly, decompose the sources into three categories before drawing any conclusion.

### Three Source Categories

| Category | Identification Condition | Persistence | Financial Statement Signal |
| --- | --- | --- | --- |
| Structural improvement | Assets or capabilities already deployed: new processing lines, vertically integrated infrastructure, new high-value channels | Persists — the underlying asset remains | CapEx in prior periods → revenue contribution in current period; product mix shift in revenue breakdown |
| External windfall | Market conditions outside the company's control: commodity price swings, supply shortages boosting prices, favorable exchange rates | Reverses when conditions change | Margin improvement without corresponding CapEx or operational change; coincides with known external events |
| One-time financial items | Non-recurring actions: asset disposal gains, accounting policy changes, restructuring charges | Does not repeat | Disclosed in footnotes; often appears in non-operating income/expense |

### Decomposition Procedure

1. List every margin change driver identified in earnings calls, analyst reports, or management commentary.
2. Tag each driver as structural / external / one-time using the identification conditions above.
3. Estimate each driver's contribution in percentage points of margin change.
4. Sum structural drivers only → this is the sustainable margin level.
5. Calculate normalized EPS = reported EPS minus estimated per-share impact of external and one-time items.

### Normalized EPS as a Moving Range

Normalized EPS is not a fixed number — it shifts as external conditions evolve. Treat it as a range, not a point estimate. When a second external shock arrives before the first one's effects fully unwind, the range itself needs updating.

Tracking indicators for each category:
- Structural: processing revenue as % of total (should hold or increase quarter over quarter)
- External: commodity price index, exchange rate, supply/demand balance indicators
- One-time: check whether the same type of gain/loss appears in consecutive periods (if so, reclassify)

## Shock-Period Financial Statement Reading

During a shock, all companies in the affected industry show deteriorating financials. Distinguish companies that are investing through the shock from those being crushed by it.

| Signal | Transforming (Positive) | Being Crushed (Negative) |
| --- | --- | --- |
| Capital expenditure | Counter-cyclical increase (investing in new capacity, channels) | Sharp reduction or freeze |
| New products | Launching higher-margin product lines | Product line unchanged or shrinking |
| Cost structure | Processing/branded revenue share increasing | Still heavily dependent on commodity business |
| Operating cash flow | Positive (core business still generates cash) | Negative (operations themselves burn cash) |
| Debt type | Long-term investment borrowing increasing | Short-term revolving credit increasing |

A company showing 3+ positive signals during a shock is likely emerging stronger. A company showing 3+ negative signals faces existential risk.

## Post-Shock Competitive Landscape

After a major cost shock passes, three structural changes typically emerge:

1. **Concentration increases**: High-cost or undercapitalized competitors exit. Survivors gain market share passively. Track: number of active competitors, top-3 market share trend.

2. **Value chain reorganization**: Survivors accelerate vertical integration — locking in upstream raw materials or downstream distribution during the shock. Track: self-supply ratios, new channel revenue contribution.

3. **Entry barriers rise**: Post-shock industry requires higher capital intensity (processing equipment, channel investment). New entrants face higher startup costs than pre-shock. Track: average CapEx/revenue ratio for the industry.

## Escape Path Tracking

Three paths that commodity businesses use to escape margin squeeze:

| Path | Logic | Tracking Indicators | Failure Scenario |
| --- | --- | --- | --- |
| Upstream integration | Control raw material costs, reduce supply volatility | Self-supply ratio trend, procurement cost as % of revenue | Over-investment in upstream capacity that becomes stranded when commodity prices normalize |
| Downstream integration | Control end pricing, capture processing premium | Branded/processed revenue share, gross margin trend | Channel investment that fails to attract customers (empty stores, low utilization) |
| Scale-driven cost reduction | Spread fixed costs over higher volume | Revenue growth with stable or improving margin | Revenue grows but margin stays flat or declines (scale without efficiency) |

## Prediction-Validation Cycle

Apply the framework in period N, record specific predictions, check against actuals in period N+1, and adjust.

**Procedure:**
1. At analysis time: state which margin components are structural vs one-time, and estimate normalized EPS.
2. At next reporting period: compare actual EPS and margin to predictions.
3. If prediction was directionally correct: the framework is working; refine estimates.
4. If prediction missed: identify whether a new external variable appeared (add to shock tracking) or the structural assessment was wrong (adjust classification criteria).

This cycle transforms the analysis from retrospective commentary into a testable, improvable judgment system.
