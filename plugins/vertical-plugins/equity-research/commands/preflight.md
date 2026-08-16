---
description: Run the pre-purchase discipline check before entering a position
argument-hint: "[ticker, optionally with size, e.g. 'NVDA 3%']"
---

Load the `preflight-check` skill and run it against the named security.

Read `watchlist.yml` for the rules and tiers, and `theses/<TICKER>.md` if one
exists, before asking the user anything.

Argue against the trade. The user already wants to make it; the useful
contribution is the strongest honest case for not doing it. Do not fold if they
restate their conviction more forcefully -- that is not new evidence.

If no ticker is given, ask which security they are considering.
