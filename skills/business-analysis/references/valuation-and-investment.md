# Valuation and Investment Assessment

> **Role**: Operational reference for the `business-analysis` skill's Step 4 (Assess Capital Returns and Viability).
>
> **When to read**: When translating financial analysis into investment decisions — whether to invest, continue operating, or exit.

## Capital Return vs Labor Return

### Decomposition Steps

1. Estimate the owner's monthly labor hours (for owner-operated businesses).
2. Price the owner's labor at market rate for equivalent skill and hours.
3. Subtract imputed labor cost from operating profit.
4. Remaining amount = capital return on invested amount.
5. Annualize capital return / total investment = capital ROI.

### "Buying a Job" Test

If capital ROI after subtracting owner labor is near zero or negative, the business is a job purchase — returns come from labor, not capital. Compare:
- The imputed monthly wage against equivalent employment opportunities.
- The capital ROI against passive alternatives (index funds, term deposits).

If both are unfavorable, the investment thesis does not hold regardless of headline profit.

## Continue vs Exit

### Decision Formula

Monthly loss (including opportunity cost) x remaining contract months vs total exit cost.

- **Monthly loss**: Cash flow gap + capital opportunity cost (invested amount x annual return / 12).
- **Exit cost**: Lease penalty + franchise penalty + equipment disposal loss + severance.
- If cumulative continuation loss > exit cost, exit is cheaper.
- If remaining contract period < 12 months, completing the contract may cost less than early termination.

### Sunk Cost Rule

Already-paid franchise fees, renovation costs, and equipment original price do not enter the continue/exit calculation. These amounts are unrecoverable regardless of the decision. Evaluate only forward-looking costs and benefits.

## Valuation Method Selection

### By Stage and Model

| Stage | Preferred method | Why |
| --- | --- | --- |
| Seed | Milestone-based, pre-money negotiation | No revenue to value; valuation = negotiation |
| Growth | P/S (revenue multiple) | Unprofitable — earnings-based methods produce negative values |
| Mature | DCF, P/E, EV/EBITDA | Stable earnings and cash flow make projections reliable |
| Transformation | Net asset value, restructuring value | Earnings unreliable; asset liquidation value sets floor |

### Multiples Selection

| Multiple | Formula | Best for | Not suitable for |
| --- | --- | --- | --- |
| P/E | Price / EPS | Mature profitable companies | Loss-making companies (negative denominator) |
| EV/EBITDA | Enterprise Value / EBITDA | Cross-capital-structure comparison | Capital-light businesses (EBITDA = net income) |
| P/S | Price / Revenue per share | Growth companies without profit | Commodity businesses (revenue without margin is meaningless) |
| P/B | Price / Book value per share | Asset-heavy or financial companies | Tech/service companies (intangible assets dominate) |
| PEG | P/E / EPS growth rate | Adjusting P/E for growth differences | Unstable or negative growth |

### Normalized EPS

When earnings spike or drop due to one-time events, normalize before valuation:

1. **Identify one-time items**: Asset disposals, supply shock windfalls (e.g., disease-driven commodity price spike), accounting policy changes, restructuring charges.
2. **Estimate each item's impact** in EPS terms.
3. **Subtract one-time gains / add back one-time losses** to derive normalized EPS.
4. **Use normalized EPS as the valuation denominator**, not reported EPS.

Validation: If a company's P/E using reported EPS looks unusually cheap (e.g., 11x when industry norm is 15x), check whether the stock price already reflects the market's normalized view. The market often prices in normalization before reported earnings catch up.

### DCF Applicability

| Condition | DCF suitability |
| --- | --- |
| Stable, predictable FCF (mature company) | High — projections are reliable |
| High growth with uncertain terminal state | Medium — terminal value dominates (60-80% of total), high sensitivity |
| Pre-revenue or highly cyclical | Low — projections are speculation |

DCF sensitivity: A 1-percentage-point change in discount rate or terminal growth rate can shift valuation by 20-30%. Present DCF as a range, not a point estimate.
