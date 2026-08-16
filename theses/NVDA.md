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
    status: unverified
    trend: unknown
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
risks:
  - id: taiwan
    claim: "Taiwan Strait conflict or blockade"
    note: "Single point of failure - effectively all production sits with TSMC"
    severity: critical
  - id: custom-silicon
    claim: "Customers displace NVIDIA with in-house accelerators"
    note: "Google TPU, Amazon Trainium; watch disclosed share of internal workloads"
    severity: high
  - id: capex-cycle
    claim: "AI capital expenditure cycle peaks"
    note: "Would hit volume and pricing together"
    severity: high
exit_triggers:
  - "Any pillar rated deteriorating for two consecutive quarters"
  - "Gross margin falls below 65%"
  - "Taiwan Strait risk materialises - reassess immediately, do not wait for a quarter"
---

# NVDA - Investment Thesis

> **Status: draft.** The rationale, horizon and sell conditions below were
> stated by the owner; the pillars, tests, numeric thresholds and valuation
> anchors were derived by Claude from SEC filings. The 65% gross-margin
> trigger in particular is a placeholder and needs the owner's own number.
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
| 1 | Hyperscaler capex keeps growing | Combined MSFT / GOOGL / AMZN / META capex, year over year | Unverified |
| 2 | NVIDIA holds training-silicon lead | No competitor takes durable double-digit training share | Unverified |
| 3 | Gross margin holds >= 70% | Reported gross margin each quarter | On track - 71.1% (FY2026), **declining** |

Pillars 1 and 2 are marked unverified because neither has been measured yet.
Filling them in is the first job of the next review, not something to assume.

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

The owner also holds SMH, QQQ, AIQ and BOTZ. NVIDIA is roughly 20.8% of SMH,
9.6% of BOTZ and 8.8% of QQQ, so the effective position is larger than the
direct holding. SMH in particular is about 48% NVDA + TSM + AVGO + AMD + MU -
all five held individually as well, so it concentrates rather than diversifies
this position.

Position sizing has not been supplied, so true exposure is unquantified.

## Exit triggers

1. Any pillar rated **deteriorating** for two consecutive quarters
2. Gross margin **falls more than 5pts in a single fiscal year** - review
   regardless of the absolute level. FY2023 fell 8pts from 64.9% to 56.9% in one
   year; a level-only rule would not have fired until the damage was done.
3. Gross margin falls below **65%** *(placeholder - owner to confirm)*. The
   number has a referent - 64.9% was the pre-AI peak, so breaching it means the
   AI-era pricing premium is fully gone - but it tolerates 6pts of compression
   from here, which is a large drawdown to sit through. A tighter **70%** is the
   floor of the AI era and would fire as an early warning instead.
4. Taiwan Strait risk materialises - reassess immediately, do not wait for a
   scheduled review

A single threshold cannot serve as both an alert and an exit. Trigger 2 is the
early signal, trigger 3 the exit; the owner sets where each sits.

## Update log

| Date | Development | Pillar affected | Impact | Action | Conviction |
|---|---|---|---|---|---|
| 2026-08-16 | Thesis opened. FY2026 revenue $215.9B (+65.5%), gross margin 71.1%. LTM revenue $253.5B as of Q1 FY2027. | 3 | Establishes baseline | None | Medium |

## Open items

- [ ] Owner to confirm or replace the 65% gross-margin exit trigger
- [ ] Measure pillar 1: pull hyperscaler capex from MSFT / GOOGL / AMZN / META filings
- [ ] Measure pillar 2: find a citable source for training-silicon share
- [ ] Supply position sizes so portfolio exposure can be quantified
- [ ] Run `/dcf NVDA` to derive a target price rather than leaving it unset
