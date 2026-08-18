# Report Reading Checklist

> **Role**: Operational reference for the `business-analysis` skill's Step 1 (Reconstruct the Numbers).
>
> **When to read**: When analyzing a P&L, three-statement financial report, or evaluating a small/medium business with limited financial data.

## P&L Reading

### Denominator Selection

1. Identify all revenue figures — customer spending vs store/company received amount.
2. Calculate the gap — the difference is platform commissions, payment processing fees, or intermediary cuts.
3. Recompute every cost percentage using both denominators.
4. Note which denominator each "industry benchmark" uses before comparing.
5. Flag any totals that do not add up — self-prepared reports frequently have attribution overlaps.

### Hidden Cost Identification

| Hidden cost | Typical range | Where it hides |
| --- | --- | --- |
| Equipment depreciation | Investment / useful life / 12 | Not listed (only maintenance appears) |
| Insurance | Actual premium / 12 | Below operating profit line |
| Inventory adjustment | Beginning + purchases - ending inventory | Report uses purchases, not COGS |
| Franchise royalties | PC ingredient markup vs market price | Embedded in ingredient cost |
| Loan interest | Outstanding loan x annual rate / 12 | Not in self-prepared P&L |
| Periodic renovation | Renovation cost / contract cycle / 12 | Not in monthly P&L |

### Profit Adjustment Table Template

| Item | Monthly impact |
| --- | --- |
| Reported operating profit | +X |
| Equipment depreciation (est.) | -X |
| Insurance reclassification | -X |
| Performance bonus | -X |
| Loan interest (if applicable) | -X |
| **Adjusted monthly profit** | **= sum** |

If adjusted profit flips positive to negative, flag as critical finding.

## Three-Statement Linkage

### Connection Check

- P&L net income feeds into retained earnings on the balance sheet.
- Capital expenditure becomes fixed assets on the balance sheet.
- New borrowing becomes liabilities on the balance sheet.
- Balance sheet equation: Assets = Liabilities + Equity. Imbalance = accounting error.

### Net Income vs Operating Cash Flow

| Condition | Interpretation |
| --- | --- |
| Both positive, similar magnitude | Healthy — profits convert to cash |
| Net income positive, OCF negative (1 quarter) | Check working capital swings — may be seasonal |
| Net income positive, OCF negative (2+ quarters) | Profit quality concern — investigate receivables, inventory, capitalization |
| OCF consistently exceeds net income | Normal — depreciation adds back non-cash expense |

Experience-based threshold: single-quarter divergence within 30% of net income is acceptable. Divergence exceeding 50% for two or more consecutive quarters warrants investigation.

### Free Cash Flow

FCF = Operating Cash Flow - Capital Expenditure.

| FCF pattern | Interpretation |
| --- | --- |
| Consistently positive | Self-sustaining |
| Negative during expansion | Acceptable if unit economics healthy |
| Negative in mature company | Structural problem — check CapEx/revenue ratio |
| Dividend exceeds FCF | Borrowing to pay dividends — unsustainable |

## Cash Flow Statement Breakdown

### Six Operating Patterns

| Operating | Investing | Financing | Status |
| --- | --- | --- | --- |
| + | - | - | Healthy mature |
| + | - | + | Aggressive expansion |
| + | + | - | Contraction / asset disposal |
| - | - | + | Burning + expanding OR crisis |
| - | + | + | Distress — selling assets + borrowing |
| - | + | - | Severe decline — cash depleting fast |

Distinguish "-/-/+" expansion from crisis: seed-stage CapEx/revenue > 30% with equity financing = expansion; mature company with operating loss + CapEx > 15% + short-term debt funding = crisis.

### CapEx / Depreciation Ratio

| Ratio | Interpretation |
| --- | --- |
| < 1.0 | Equipment aging |
| 1.0-1.3 | Maintenance level |
| 1.3-2.0 | Partial expansion |
| > 2.0 | Major expansion |

## SME Cross-Verification

### Bank Statement

Track month-end balance trend (3+ months). Flag irregular personal transfers. Compare deposits against reported revenue.

### Tax Filing

Compare VAT-reported revenue against P&L revenue. Compare input tax credits against reported purchases.

### On-Site Observation

Estimate daily revenue: customer count x average transaction. Compare headcount against reported payroll. Assess equipment condition against book value.

### Triangle Verdict

Cross-check all three sources. Largest discrepancy = where to investigate. Refusal to provide bank/tax records = information risk signal.
