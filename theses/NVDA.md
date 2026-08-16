---
ticker: NVDA
company: NVIDIA Corporation
position: long
opened: 2026-08-16
conviction: medium
review_cadence: quarterly
horizon: thesis-driven
owner_stated_rationale: "AI future"
valuation_asof: 2026-04-26
valuation_basis: LTM
pillars:
  - id: hyperscaler-capex
    claim: "Hyperscaler capital expenditure keeps growing"
    test: "Combined MSFT / GOOGL / AMZN / META capex rises year over year"
    status: on-track
    trend: rising
    latest: 357.5e9
    latest_period: "2025 (rolling - fiscal years differ)"
    prior: 217.3e9
    measured: 2026-08-16
    note: "+64.5% YoY. Microsoft's fiscal year ends June while the others end
      December, so the combined figure is a rolling mix - good as a trend signal,
      not a precise total." 
  - id: training-share
    claim: "NVIDIA holds its lead in training silicon on the CUDA moat"
    test: "No competitor takes durable double-digit share of training workloads"
    status: unverified
    trend: unknown
  - id: gross-margin
    claim: "Gross margin holds at or above 70%"
    test: "Reported gross margin >= 70% each quarter"
    status: on-track
    trend: declining
    latest: 0.711
    latest_period: FY2026
    prior: 0.750
    prior_period: FY2025
    history_note: "19 years of 10-K history: low 34.3% (FY2009), median 56.9%, high 75.0% (FY2025). Pre-AI peak was 64.9% (FY2022)."
leading_indicators:
  - id: inventory-days
    claim: "Inventory builds ahead of a demand turn"
    latest: 114.7
    unit: days
    latest_period: 2026-04-26
    prior: 78.0
    prior_period: 2024-10-27
    status: watch
    note: "Nearly doubled. Consistent with building for a product ramp while
      revenue still grows 65%, but this is the series that shows a demand turn
      before gross margin does."
  - id: purchase-obligations
    claim: "NVIDIA's own committed spend with its supply chain"
    latest: 45.77e9
    latest_period: 2025-07-27
    status: watch
    stale: true
    note: "Growth decelerated from +35% to mid single digits. Not tagged in
      filings after 2025-07, so the series is stale - re-check whether a later
      filing restores the tag."
risks:
  - id: taiwan
    claim: "Taiwan Strait conflict or blockade"
    note: "Single point of failure - effectively all production sits with TSMC"
    severity: critical
  - id: custom-silicon
    claim: "Customers displace NVIDIA with in-house accelerators"
    note: "Google TPU, Amazon Trainium. Sharpened by concentration: the largest
      direct customer went from 13% of revenue in FY2024 to 22% in FY2026, and
      the hyperscalers most able to buy at that scale are the same ones building
      their own silicon."
    severity: high
    concentration:
      largest_direct_customer: {FY2024: 0.13, FY2025: 0.12, FY2026: 0.22}
      top_two_FY2026: 0.36
      receivables_top_three: {2026-01-25: 0.56, 2025-01-26: 0.33}
      source: "FY2026 10-K, narrative disclosure - not XBRL-tagged" 
  - id: capex-cycle
    claim: "AI capital expenditure cycle peaks"
    note: "Would hit volume and pricing together"
    severity: high
# `metric` / `op` / `threshold` make a rule executable. weekly_check.py
# evaluates only triggers carrying all three; the rest stay prose for a human,
# and the script reports them as unevaluated rather than silently ignoring them.
exit_triggers:
  - id: pillar-deterioration
    rule: "Any pillar rated deteriorating for two consecutive quarters"
    kind: exit
    evaluated_by: human
  - id: margin-rate-of-change
    rule: "Gross margin falls more than 5pts in a single fiscal year, at any level"
    kind: alert
    metric: gross_margin_yoy_delta
    op: "<="
    threshold: -0.05
    rationale: "FY2023 fell 8pts in one year; a level-only rule fires too late"
  - id: margin-alert
    rule: "Gross margin falls below 70%"
    kind: alert
    status: confirmed
    metric: gross_margin
    op: "<"
    threshold: 0.70
    referent: "Floor of the AI era (FY2024-26 ran 71.1-75.0%)"
  - id: margin-level
    rule: "Gross margin falls below 65%"
    kind: exit
    status: confirmed
    metric: gross_margin
    op: "<"
    threshold: 0.65
    referent: "64.9% was the pre-AI peak (FY2022)"
    note: "Owner-confirmed 2026-08-16. Company-specific - do NOT reuse this level
      for another name. Across the peer set 70% would put AVGO, AMD, MRVL and INTC
      in permanent breach; derive each threshold from that company's own history."
  - id: taiwan
    rule: "Taiwan Strait risk materialises - reassess immediately, do not wait for a scheduled review"
    kind: escalate
    evaluated_by: human
---

# NVDA - Investment Thesis

> **Status: draft.** The rationale, horizon and sell conditions were stated by
> the owner, and the margin thresholds were confirmed by the owner on
> 2026-08-16. The pillars, tests and valuation anchors were derived by Claude
> from SEC filings.
>
> One of three pillars is still unmeasured, there is no forward estimate or
> consensus figure anywhere in this file, and no target price has been modelled.
> It is a discipline for tracking whether a position's reasons still hold - not
> a complete investment process.
>
> **This is analyst work product, not investment advice.**

## Thesis statement

Long NVIDIA on continued expansion of AI training and inference compute
demand, with NVIDIA retaining pricing power and share through the CUDA
software ecosystem.

The owner's stated reason was "for AI future". That is a theme, not a thesis
- the pillars below are the checkable form of it. AI having a future does not
by itself mean NVIDIA captures the value; Cisco was right about the internet
and still lost 80%.

## Pillars

| # | Pillar | How it gets tested | Status |
|---|---|---|---|
| 1 | Hyperscaler capex keeps growing | Combined MSFT / GOOGL / AMZN / META capex, year over year | **On track** - $357.5B, +64.5% |
| 2 | NVIDIA holds training-silicon lead | No competitor takes durable double-digit training share | Unverified |
| 3 | Gross margin holds >= 70% | Reported gross margin each quarter | On track - 71.1% (FY2026), **declining** |

### Pillar 1, measured 2026-08-16

| | 2024 | 2025 |
|---|---|---|
| Microsoft | $44.5B | $115.9B |
| Amazon | $83.0B | $131.8B |
| Alphabet | $52.5B | $91.4B |
| Meta | $37.3B | $69.7B |
| **Combined** | **$217.3B** | **$357.5B (+64.5%)** |

Capex from each company's cash flow statement. Microsoft's fiscal year ends in
June while the other three end in December, so the combined figure is a rolling
mix - sound as a trend signal, not a precise total.

Pillar 2 stays unverified. Training-silicon share has no free authoritative
source, and guessing it would be worse than leaving the gap visible.

### Pillar 3 in historical context

Nineteen years of gross margin as filed, from the 10-Ks:

| Era | Range | Note |
|---|---|---|
| FY2008-2011 | 34.3% - 45.6% | Trough is FY2009, the all-time low |
| FY2012-2022 | 51.4% - 64.9% | The long climb. FY2022's 64.9% is the pre-AI peak |
| FY2023 | 56.9% | Crypto demand shock - **an 8pt fall in a single year** |
| FY2024-2026 | 71.1% - 75.0% | The AI era |

Median across the whole period is 56.9%.

Two things follow. First, margin is **already compressing**: 75.0% in FY2025 to
71.1% in FY2026, down 3.9pts, making FY2026 the weakest of the three AI years.
The pillar is on track but the trend is not flat, and the frontmatter records it
as declining rather than stable.

Second, FY2023 is the precedent worth holding onto. The fall from 64.9% to 56.9%
happened in one year. Any threshold set on the absolute level alone will
therefore trigger late - by the time the level confirms the damage, the change
has already happened. That is why the exit triggers below carry a
rate-of-change rule as well as a level.

## Leading indicators

Gross margin is an output. Whatever moves it moved several quarters earlier, so
pillar 3 confirms a change rather than warning of one. These two run ahead of it
and are pulled from the same filings by `data/leading_indicators.py`.

**Inventory days** - inventory over daily cost of revenue:

| | Inventory | Days |
|---|---|---|
| Oct 2024 | $7.65B | 78.0 |
| Apr 2025 | $11.33B | 59.3 |
| Jul 2025 | $14.96B | 105.6 |
| Oct 2025 | $19.78B | 118.8 |
| Apr 2026 | $25.80B | 114.7 |

Inventory is up close to four times in fifteen months and days on hand have
roughly doubled. Two readings fit: building ahead of a product ramp, which is
consistent with revenue still growing 65%, or demand softening while supply
keeps arriving. The first is more likely today. The point of tracking it is that
**this series distinguishes them before gross margin does** - if revenue growth
decelerates while days keep climbing, the second reading is the right one.

**Purchase obligations** - what NVIDIA has committed to buy from its supply
chain, and so its own bet on future demand:

| As of | Committed | Change |
|---|---|---|
| Jul 2024 | $39.78B | +35% |
| Oct 2024 | $42.04B | +6% |
| Jan 2025 | $45.08B | +7% |
| Apr 2025 | $43.52B | -3% |
| Jul 2025 | $45.77B | +5% |

Growth decelerated from +35% to mid single digits. **The series is stale** - the
tag stops appearing after July 2025, so this is not a current reading and the
next review should check whether a later filing restores it.

Customer concentration belongs in this section and is missing. NVIDIA discloses
it as narrative text rather than tagging it, so it cannot be pulled from the
XBRL API and needs the filing read directly.

## Risks

| # | Risk | Why it matters | Severity |
|---|---|---|---|
| 1 | **Taiwan Strait conflict** | Effectively all production sits with TSMC. No second source exists at this node. | Critical |
| 2 | Customer custom silicon | Google TPU and Amazon Trainium displace merchant GPUs for internal workloads | High |
| 3 | Capex cycle peaks | Volume and pricing compress together | High |

Risk 1 is the sharpened version of the owner's "war or obstacles". It is worth
stating precisely because it is the one risk in this position that is both
plausible and unhedgeable by diversifying within semiconductors - every peer in
the comp set depends on the same fabs.

### Customer concentration, read from the FY2026 10-K

Not XBRL-tagged, so this had to come from the filing text.

| Share of total revenue | FY2024 | FY2025 | FY2026 |
|---|---|---|---|
| Largest direct customer | 13% | 12% | **22%** |
| Second largest | - | 11% | 14% |
| Top two combined | - | ~23% | **36%** |

Receivables concentrate harder still: three direct customers were 25%, 18% and
13% of the balance at 25 Jan 2026 - **56% between them** - against two customers
at 17% and 16% a year earlier.

This materially sharpens risk 2 rather than sitting beside it. A single customer
at 22% of revenue is a different exposure from one at 13%, and the buyers able
to purchase at that scale are the same hyperscalers developing their own
accelerators. The concentration and the substitution risk are the same risk seen
twice.

Two further points from the same disclosure. NVIDIA states that an unnamed "AI
research and deployment company" contributed a meaningful amount of revenue by
buying cloud services *through* its customers - an indirect exposure that does
not appear in the direct-customer table at all. And revenue from outside the
United States fell from 41% to 31% of the total, so the customer base is
concentrating geographically at the same time.

## Valuation anchor

LTM basis, as of each company's most recent filed quarter. Prices are delayed
quotes from 2026-08-16.

| | LTM Revenue | LTM EBITDA | EV/Revenue | EV/EBITDA | P/E |
|---|---|---|---|---|---|
| **NVDA** | $253.5B | $165.5B | **21.5x** | **32.9x** | 34x |
| AVGO | $75.5B | $41.4B | 24.5x | 44.7x | 64x |
| MRVL | $8.7B | $2.5B | 22.2x | 76.5x | 76x |
| AMD | $41.3B | $6.8B | 19.7x | 120.7x | 128x |
| ARM | $5.2B | $1.1B | 56.6x | 255.7x | 283x |
| INTC | $57.0B | $12.3B | 9.2x | 42.9x | n/a (loss) |

NVIDIA is the cheapest quality name in its own peer set on EBITDA, while
growing fastest and carrying a 65% EBITDA margin. That is the valuation
observation supporting the position - not a target price. No target price is
set here because none has been derived from a model; `/dcf NVDA` would be the
way to produce one.

## Portfolio context

The owner also holds SMH, QQQ, AIQ and BOTZ, so the effective position is larger
than the direct holding.

| ETF | NVDA weight | Source |
|---|---|---|
| SMH | ~20.8% | Estimated - issuer site blocks automated access |
| BOTZ | **9.371%** | Global X, first-hand |
| QQQ | ~8.8% | Estimated - not yet pulled first-hand |
| AIQ | **2.946%** | Global X, first-hand |

SMH is about 48% NVDA + TSM + AVGO + AMD + MU - all five held individually as
well, so it concentrates rather than diversifies this position. AIQ at 2.9%
across 93 holdings is the only one of the four genuinely diversifying away from
it.

The two first-hand figures came in close to the earlier search-sourced
estimates, but the same check found a search result had Broadcom's peer ABB as
BOTZ's largest holding when it is actually Keyence at 10.8%. SMH and QQQ stay
flagged as estimates until pulled from the issuer.

Position sizing has not been supplied, so true exposure is unquantified.

## Exit triggers

1. Any pillar rated **deteriorating** for two consecutive quarters
2. Gross margin **falls more than 5pts in a single fiscal year** - review
   regardless of the absolute level. FY2023 fell 8pts from 64.9% to 56.9% in one
   year; a level-only rule would not have fired until the damage was done.
3. Gross margin falls below **70%** - alert only. This is the floor of the AI
   era; breaching it means the premium is loosening, and the job is to find out
   why (mix, competition, a one-off) rather than to act.
4. Gross margin falls below **65%** - exit. 64.9% was the pre-AI peak, so
   breaching it means the AI-era pricing premium is fully gone and pillar 3 has
   failed. Owner-confirmed 2026-08-16.
5. Taiwan Strait risk materialises - reassess immediately, do not wait for a
   scheduled review

A single threshold cannot serve as both an alert and an exit, which is what made
an isolated 65% feel arbitrary. Triggers 2 and 3 are the early signals; trigger 4
is the exit.

**These levels are specific to NVIDIA and must not be reused.** Gross margin is a
function of business model, and the peer set spans 34.8% (Intel, which owns its
fabs) to 97.5% (Arm, which licenses IP). Applying NVIDIA's 70% across the
watchlist would put Broadcom, AMD, Marvell and Intel in permanent breach -
Broadcom's best year ever was 68.9%. Derive every threshold from that company's
own filed history: its normal band, and the level it fell to when its business
last broke.

## Update log

| Date | Development | Pillar affected | Impact | Action | Conviction |
|---|---|---|---|---|---|
| 2026-08-16 | Thesis opened. FY2026 revenue $215.9B (+65.5%), gross margin 71.1%. LTM revenue $253.5B as of Q1 FY2027. | 3 | Establishes baseline | None | Medium |
| 2026-08-16 | Pillar 1 measured for the first time: combined hyperscaler capex $357.5B in 2025 against $217.3B in 2024, +64.5%. | 1 | Confirms - moves from unverified to on-track | None | Medium |
| 2026-08-16 | Margin thresholds confirmed by owner at 70% alert / 65% exit. | 3 | No change to status | None | Medium |
| 2026-08-16 | Customer concentration read from the FY2026 10-K: largest direct customer 22% of revenue against 13% two years earlier; top two 36%; three customers 56% of receivables. | Risk 2 | **Weakens** - concentration and custom-silicon substitution are the same exposure | None | Medium |
| 2026-08-16 | ETF weights pulled first-hand where possible: BOTZ 9.371%, AIQ 2.946%. SMH and QQQ still estimated. | - | Refines portfolio context | None | Medium |
| 2026-08-16 | Leading indicators added. Inventory days roughly doubled (78.0 to 114.7) and purchase-obligation growth decelerated from +35% to +5%. Neither breaches a trigger; both are logged as watch. | 3 | Disconfirming evidence, does not yet weaken the pillar | None | Medium |

## Open items

- [x] Owner to confirm the gross-margin triggers - set at 70% alert / 65% exit
- [x] Measure pillar 1 - combined hyperscaler capex, +64.5%
- [ ] Measure pillar 2: find a citable source for training-silicon share. No free
      authoritative source exists; this is the one gap that needs paid data
- [x] Read the 10-K for customer concentration - done, and it worsened risk 2
- [ ] Pull SMH and QQQ weights first-hand; VanEck blocks automated access, so
      this needs a manual export or a different route
- [ ] Check whether a filing after Jul 2025 restores the PurchaseObligation tag
- [ ] Write a variant view. The thesis as stated is consensus, so it carries no
      edge - decide whether that is acceptable or the position should be an
      index instead
- [ ] Supply position sizes so portfolio exposure can be quantified
- [ ] Run `/dcf NVDA` to derive a target price rather than leaving it unset
