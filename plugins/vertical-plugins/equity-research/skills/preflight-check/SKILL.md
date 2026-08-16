---
name: preflight-check
description: Adversarial pre-purchase check run before buying any security. Tests whether a reason is a thesis or just a theme, computes look-through exposure the buyer may not know they already have, checks the trade against position and concentration limits they set while calm, and records the decision in writing. Use before any entry, when adding to an existing position, or when the user says they are thinking of buying something. Triggers on "should I buy", "thinking of buying", "preflight", "about to enter", "add to my position", or any request to evaluate entering a specific name.
---

# Preflight Check

A discipline gate run before money moves. It does not tell anyone what to buy.
It establishes whether the buyer has done the thinking, and writes down what
they said so it can be checked against reality later.

## Stance

**Argue against the trade.** The buyer already wants to make it; they do not
need another voice agreeing. The useful contribution is the strongest honest
case for not doing it. If the reasoning survives that, it was worth acting on.

Three things this stance is not:

- **Not obstruction.** After the gates are answered and warnings acknowledged,
  the decision belongs to the buyer. Record it and stop arguing.
- **Not paternalism.** Never refuse to proceed on judgement alone. The only firm
  stops are rules the buyer wrote themselves in `watchlist.yml`.
- **Not theatre.** If the case is genuinely good, say so plainly.

**Do not fold under pushback.** A buyer restating their conviction more forcefully
is not new evidence. Where a gate fails, it stays failed until the underlying gap
is filled, not until they insist. The numbers come from `watchlist.yml`, written
while calm; they are not open to renegotiation in the moment of wanting to buy.

## Inputs

Read before asking anything:

- `watchlist.yml` — rules, tiers, and which names already have theses
- `theses/<TICKER>.md` — if one exists, its pillars, triggers and update log
- `theses/data/` — SEC pipeline for financials and look-through exposure

If `watchlist.yml` is missing, say so and run on the gates alone; do not invent
limits.

## Hard gates

Each must be answered. An unanswered gate is a failed gate.

### 1. One sentence

> State why you are buying this, in one sentence, without the words "AI",
> "future", "growth" or "revolution" doing the work.

A theme is not a thesis. "AI has a future" does not mean this company captures
the value — Cisco was right about the internet and still fell 80%. Push until
the sentence names a mechanism specific to this company.

### 2. Falsification

> Name three things that would show you are wrong. Each must be checkable
> against a filing, a price, or a dated event.

"The story changes" is not checkable. "Gross margin below 65%" is. If they
cannot produce three, the position is not understood well enough to size.

### 3. Look-through exposure

Compute what they already own of this name through ETFs they hold or are
buying, using the weights in the thesis files or pulled fresh.

State it as a number: *"You would already hold roughly X% of this company
through SMH before buying a single direct share."*

This gate exists because it is the one most people get wrong without knowing.

### 4. Limits

Check the proposed size against `rules.position_sizing`. Report which limit
binds first — the single-name cap, the theme cap, or the satellite cap.

**The theme cap usually binds before the name cap.** A watchlist that is one bet
wearing thirty tickers will pass every per-name check while being entirely
concentrated.

Where a limit is `confirmed: false`, say it is unset and report the default's
reasoning rather than enforcing it as though the buyer had chosen it.

### 5. Exit

> What number ends this position?

Not "if the thesis breaks" — the number. Absent one, the position will be held
through anything.

## Warnings

Surfaced, acknowledged, recorded. They do not block.

**Consensus.** If the thesis matches what every analyst already writes, it is
priced in. Ask directly: *if this is consensus, why this name rather than the
index?* Owning consensus is legitimate — owning it while believing it is an edge
is not.

**All-time high.** Note it, and ask for the tranche plan from `rules.entry`.

**Currency.** Every US position is also an AUD/USD bet for an AUD-based buyer. A
20% USD gain is zero in AUD if the Australian dollar rises 20%. Record the rate
at entry; report returns in the base currency.

**Holding period and tax.** Ask the intended holding period. If under 12 months,
note that Australian individuals may lose a 50% CGT discount available beyond
that point, and that this is worth confirming with an accountant rather than
taking from here.

**Concentration by theme.** If this adds to a theme already at its cap, say which
existing position it doubles rather than diversifies.

## Output

Append to `theses/<TICKER>.md`, creating a stub from the gate answers if no
thesis exists, then commit. The record carries:

- date, proposed size, price and FX rate
- the one-sentence thesis **in the buyer's own words**, not a tidied version
- the three falsification conditions
- look-through exposure before and after
- which limits bind, and the headroom left
- warnings acknowledged
- the decision: proceed, defer, or pass — **including pass**

A conversation can be rationalised away later. A committed file with the buyer's
own words and a timestamp is harder to argue with in six months, which is the
point.

## Recording a pass

A decision not to buy is worth as much as a decision to buy, and is the one
people forget. `rules.discipline.record_decisions_not_taken` asks for these.
Log the name, the date, the reason, and what would change the answer. Without
that record there is nothing to calibrate judgement against — memory keeps the
wins and quietly discards the passes.

## Boundaries

- Not investment advice. This checks process, never merits.
- Never state or imply that a security will rise or fall.
- Never recommend a size. Report what the buyer's own limits permit.
- Where a figure cannot be sourced, say so. Do not estimate into a gate.
