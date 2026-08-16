# Signal Engine

Discovery half of the investing setup: watches trend and social data for topics
moving before the market has priced them, and pushes a short daily digest.

Rescued here from a chat session, where it was the only copy. **Two scripts are
still missing** and the pipeline cannot run without them:

| File | Status |
|---|---|
| `.github/workflows/collect.yml` | present |
| `scripts/send_digest.py` | present |
| `scripts/collect_trends.py` | **missing** - Google Trends + Reddit + RSS, computes velocity and info_gap_score |
| `scripts/generate_analysis.py` | **missing** - Claude API pass over the top signals |
| `requirements.txt` | **missing** - referenced by the workflow |
| `docs/investment-strategy.md` | present |

Recover the two scripts from the chat session that produced them before that
session ages out. Until then the workflow will fail at its first step.

## How it fits with the rest of the repo

Three stages, and this is only the first:

```
discovery            validation                 monitoring
signal-engine/  ->   theses/data/          ->   theses/*.md
                     SEC XBRL pipeline          thesis tracker
```

The engine answers *what is moving*. It cannot tell whether a company is real,
whether its financials support the story, or whether the move is already priced
in - that is what the SEC pipeline in `theses/data/` is for, and what a thesis
file records once a name is worth following.

The strategy doc frames this as three conditions: criticality, information gap,
and demand inflection. The engine covers the first two. **Demand inflection is
what `theses/data/leading_indicators.py` measures** - inventory days, purchase
obligations, customer concentration, hyperscaler capex.

## Wire in ticker validation

`send_digest.py` currently pushes `potential_tickers` from the model straight to
a phone with nothing checking them. See `theses/data/README.md` - the validator
is standard-library only and copies in unchanged:

```python
from validate_tickers import annotate
tickers = annotate(sig.get("potential_tickers", []) or [])
```

## Known gaps

- **No deduplication.** A keyword trending for five days sends five identical
  digests. `get_analyzed_signals()` filters on today only, with no memory of
  what was already pushed. This is how a system earns being ignored.
- **`signal_outcomes` is never written.** The table exists in the schema and
  nothing populates it, so there is no hit rate and no way to calibrate. The
  strategy doc calls for an eight-week calibration period; without backfill that
  period produces no measurement.
- **Silent failure.** The workflow uploads logs on failure and notifies nobody.
  It could be broken for weeks unnoticed.
- **Schedule.** `cron: '0 18 * * *'` is commented as 02:00 Taiwan time, but the
  owner is in Australia, where it lands at 04:00 AEST.

## Secrets

Set as GitHub Actions secrets, never committed: `SUPABASE_URL`, `SUPABASE_KEY`,
`REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `ANTHROPIC_API_KEY`,
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
