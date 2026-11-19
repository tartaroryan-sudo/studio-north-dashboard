# Studio North monthly dashboard

Path A, FAQ 4 — “Replay the report as a month-by-month dashboard.”

The dashboard asks whether Studio North is moving in the right direction by replaying 24 monthly snapshots, January 2024–December 2025. Open **dashboard.html** directly in a browser. Use Next month, Previous month, the dropdown, or the slider. No server or account is needed for the downloaded dashboard. Download this repository as a ZIP, extract it, then open dashboard.html.

[Demonstration video (2:30)](demo.mp4) · [Original executive report](baseline-report.pdf)

## Rebuild with Python and uv

Requires Python 3.12 and uv.

```sh
uv sync --frozen
uv run --frozen python build.py
```

This precomputes snapshots. Clicking a month performs no fitting. The only Python dependency is DuckDB, pinned by uv.lock. The HTML contains its own data, styles and JavaScript. Place baseline-report.pdf alongside dashboard.html to use its report link.

## What is shown

- Revenue and contribution by as-of month, with operating acquisition spend.
- Contractual retention by first-paid cohort and zero-based calendar-month age, using the original acquired-customer denominator.
- Every joining cohort's four acquisition-time channel-by-need groups.
- Historical average CAC, observed discounted contribution, cash balance, and observed payback.
- Completed holdout results and current incremental CAC.
- Original report forecasts at the December 2025 snapshot, with forecast share and historical-CAC payback distinguished.

## Historical forecast policy and recommendation timing

This implementation uses the explicit FAQ 4 fallback in the slide notes. Earlier months show observed results. It does **not** fit historical forecasts, and it does **not** apply the December model to earlier months. Missing historical forecasts are labeled unavailable. Observed 12-receipt contribution is shown when the full horizon has occurred. Partial contribution is labeled partial.

December 2025 is the first snapshot in this implementation with an eligible full value forecast and current experimental costs. It supports prioritizing search / build skills: July's contribution value is $284.04 before CAC versus December iCAC of $150.68, a $133.36 point surplus. The added buyers are assumed to match July's value path, with no value change for would-be buyers. The earliest historical month that could have supported that recommendation remains **unknown** without historical refits. A dated event occurring earlier does not establish earlier support for a forward-looking recommendation.

Observed newer-cohort economics improve at common ages. The original PDF's primary seasonally matched comparison is January–June 2024 versus January–June 2025 after six receipts: retention 52.2% versus 61.6%, historical CAC approximately $108 versus $85, and cash after acquisition approximately −$1 versus $46 per original customer.

## Baseline and as-of integrity

The source is [the Studio North lab](https://github.com/longxiutian/customer-economics-lab/tree/df6d62a7739a1f04de69a61a474812a04694810c), commit df6d62a7739a1f04de69a61a474812a04694810c. FAQ 4 is in docs/companion-slides.md of that revision.

The eight original CSVs, completed report PDF and selected saved tables are preserved in baseline.zip, which the builder expands into baseline/ when needed. Every build verifies their SHA-256 hashes in baseline-lock.json. The PDF is unchanged. The original MIT license is included in baseline/LICENSE. schema.json preserves the released input types, and 01_views.sql is copied unchanged from the lab.

Each cutoff is the first day of the next month in UTC, exclusive for operational events. Timestamped payments, refunds, renewals, acquisition credit, profiles, product records, survey responses and spending are filtered before executing the original SQL. Holdout outcomes become available when their complete 31-day window ends at or before that boundary. Baseline attributes must have been recorded before the cutoff.

The build:
1. Produces all 24 monthly snapshots separately.
2. Reconciles every final retention, revenue, contribution and cash row to the saved lab tables.
3. Physically truncates the eight source CSVs at June 2025 month-end and verifies identical results.
4. Writes dist/verification.json.

The latest twelve-month forecasts are the exact saved cohort_valuation.csv values from this run, not refits. Earlier forecasts are absent. The dashboard intentionally presents an interactive subset of the report's exhibits. The full PDF remains the source for parameters, uncertainty, seasonal standardization, methods and citations.

## Definitions and scope

USD, UTC, data version 5.1. Final observation cutoff January 1, 2026 exclusive. Contribution deducts discounts, refunds and nonmarketing variable costs. Discounted value uses 12 receipt months at 1% monthly; the joining-month receipt is discounted at t=1. Payback uses undiscounted contribution and one-based receipt months. Cash-to-date can cover more than 12 observed months, while value is capped at 12.

Historical average CAC is operating acquisition spending divided by first-paid customers. It is different from experimental iCAC. The separate acquisition research budget is $44,000 per monthly wave and is outside operating accounts. Fixed operating costs are outside the data.

## Demonstration

Watch demo.mp4 (approximately 2½ minutes, synthetic narration and captions). It demonstrates advancing a month, observing January 2024 cohort payback between June and July, restricting completed experiment windows, and interpreting the final acquisition recommendation.
