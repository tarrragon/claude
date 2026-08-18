# Company Positioning and Industry Benchmarking

> **Role**: Operational reference for the `business-analysis` skill's Steps 2-3 (Position the Company, Build Industry Benchmarks).
>
> **When to read**: When determining what type of company is being analyzed and what "normal" looks like for its industry.

## Two-Axis Positioning

### Lifecycle Stage Determination

| Stage | Revenue growth rate | Profitability | Primary evaluation focus |
| --- | --- | --- | --- |
| Seed | No revenue or minimal | Negative (expected) | Burn rate, runway, milestone progress |
| Growth | > 50% YoY | Often negative | Unit economics, LTV/CAC, retention |
| Transition zone | 15-50% YoY | Variable | Both growth and mature metrics — use unit economics stability as tiebreaker |
| Mature | 5-15% YoY, stable profit | Positive | FCF, dividend sustainability, moat durability |
| Transformation/Decline | Flat or declining | Compressing | Net asset value, restructuring capability, cash runway |

Growth rate thresholds are cross-industry rough references. Adjust by industry norms.

### Business Model Determination

| Model | Revenue source | Key differentiating metric |
| --- | --- | --- |
| Product company | Own brand/IP sales | Gross margin (reflects pricing power) |
| Distributor/Agent | Reselling others' products | Inventory turnover x margin = annualized return |
| Service provider | People x utilization x rate | Utilization rate (billable hours / total hours) |
| Platform | GMV x Take Rate | GMV growth + Take Rate trend |
| Manufacturer | Physical product manufacturing | Capacity utilization + yield rate |
| Vertically integrated | Spans multiple value chain stages | Evaluate each stage separately; watch for related party transfer pricing |
| Franchise (franchisor) | Ingredient supply + royalties + franchise fees | Store count growth + per-store revenue contribution |

### Cross-Reference Matrix (Priority Metrics)

| Stage \ Model | Product | Distributor | Service | Platform | Manufacturer |
| --- | --- | --- | --- | --- | --- |
| Seed | Prototype + runway | N/A | First clients + runway | Cold-start + runway | Production line + runway |
| Growth | Margin trend + LTV/CAC | Turnover + contract expansion | Utilization + per-capita revenue | GMV growth + Take Rate | Capacity utilization + yield |
| Mature | FCF + moat | Contract renewal + inventory efficiency | Retention + pipeline | Network effects + concentration | Depreciation cycle + input sensitivity |
| Transformation | New product line + cash reserves | New agency rights + transition cost | New service line + workforce adjustment | New market / new matching | Equipment renewal + capacity adjustment |

## Industry Benchmark Construction

### Data Sources (Taiwan)

| Source | Coverage | Precision | Access |
| --- | --- | --- | --- |
| MOPS | Listed/OTC companies | High | Free, web query |
| Financial analysis tools (e.g. Goodinfo) | Listed/OTC | High | Free or low monthly fee |
| SME White Paper | SME statistics | Medium | Free, annual |
| Industry association reports | Specific industries | Medium-High | Member access or public |
| Franchise HQ disclosure | Specific franchise systems | Low-Medium | Information sessions (marketing bias) |

### Peer Group Construction

Filter by four dimensions, minimum 5-8 companies:

1. **Sub-industry**: Same product/service type (e.g., IC design vs packaging within "semiconductors").
2. **Scale**: Similar revenue range (e.g., 1-5 billion vs 50-100 billion).
3. **Lifecycle**: Similar growth rate range.
4. **Geography**: Similar primary market.

If fewer than 5 companies remain, relax one dimension (typically scale).

Use **median** (not average) — average gets skewed by outliers. Pull **8-12 quarters** of trend data, not just the latest snapshot.

**Survivorship bias**: Public data only includes surviving companies. Social media benchmarks from franchise owners only include those still operating. Note this bias when interpreting "industry average."

## Deviation Analysis

### Four Deviation Directions

| Direction | Positive explanation | Negative explanation | How to distinguish |
| --- | --- | --- | --- |
| Margin above peers | Product differentiation, cost advantage | Aggressive revenue recognition | Stable trend + matching OCF = genuine; sudden jump + weak OCF = suspect |
| Margin below peers | Strategic low pricing for market share | Pricing power lost, cost structure deteriorated | Revenue accelerating correspondingly = strategic; revenue flat = structural problem |
| CCC shorter than peers | Superior supply chain management | Squeezing suppliers or selectively recognizing | Check if payable days are far above industry norm |
| CCC longer than peers | Deliberate stockpiling (expecting demand) | Products not selling, customers not paying | Check inventory composition (raw vs finished) + receivable aging |

### Multi-Metric Cross-Reading

| Pattern | Likely interpretation |
| --- | --- |
| High margin + high OCF | Genuine operational efficiency |
| High margin + low OCF | Aggressive recognition or receivable quality issue |
| Revenue growing + margin declining | Scaling without efficiency gains, or price competition |
| Revenue flat + margin jumping | One-time benefit or product mix shift — decompose per Step 5 |

### Trend vs Snapshot

Compare the company's 8-12 quarter trend against the industry's trend:
1. Company direction: improving, flat, or deteriorating?
2. Industry direction: expanding or contracting?
3. Gap: company improving faster than industry = strengthening competitiveness; slower = losing share.

### Cyclical Industry Adjustment

For cyclical industries (semiconductors, shipping, construction, commodities), use full-cycle averages (3-7 years) as benchmarks. Single-period snapshots during peaks or troughs carry cyclical bias. Label the current cycle position before drawing conclusions.

Distinguish **supply shock** (reverses in 1-2 quarters after event resolves) from **cyclical swing** (persists for years). Using shock-period figures as benchmarks overstates normal performance.
