# Signal Engine

Discovery half of the investing setup: watches trend and social data for topics
moving before the market has priced them, and pushes a short daily digest.

Rescued here from a chat session, where it was the only copy. **All nine files
are now present** and the three Python scripts compile clean.

| File | Purpose |
|---|---|
| `scripts/collect_trends.py` | Google Trends + Reddit + Taiwanese RSS; computes velocity and info_gap_score |
| `scripts/generate_analysis.py` | Claude API pass over the top 5 signals; returns structured JSON |
| `scripts/send_digest.py` | Telegram push, top 5, once a day |
| `scripts/backfill_outcomes.py` | Writes `signal_outcomes`; computes the calibration hit rate |
| `scripts/prices.py` | Daily closes from Stooq, no key, no dependency |
| `scripts/schema.sql` | Supabase tables + 30 calibration keywords |
| `scripts/migrations/002_outcome_unique.sql` | Run once on an already-created database |
| `scripts/validate_tickers.py` | SEC registrant check, copied unchanged from `theses/data/` |
| `requirements.txt` | Pinned deps |
| `.github/workflows/collect.yml` | Daily schedule, three steps in order |
| `docs/investment-strategy.md` | The strategy this implements |
| `docs/upstream-context.md` | The engine's own CLAUDE.md — design rationale, kept verbatim |

The workflow under `signal-engine/.github/` is inert here; only workflows at the
repository root run. It ships with the engine for when it is deployed to its own
repo.

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

## Ticker validation - wired in

`send_digest.py` used to push `potential_tickers` from the model straight to a
phone with nothing checking them. It now runs them through
`validate_tickers.annotate()` first: symbols absent from SEC's registrant list
are marked `⚠️` rather than dropped, because an ETF or a Taiwan-listed name is
legitimately absent. If SEC is unreachable and no cache exists, the digest sends
unmarked rather than failing - a broken validator must not silence the engine.

## Design decisions worth not breaking

Taken from `docs/upstream-context.md`, because each looks like a bug until you
know why:

- **Google Trends scores are window-relative.** A score of 60 today and 60
  tomorrow are not the same quantity; each query renormalises to its own window
  maximum. So GT is deliberately *not* written to `trend_snapshots` - velocity is
  computed inside a single 90-day query. Only absolute sources (Reddit post
  counts, RSS hits) get snapshotted.
- **Velocity uses a mutually exclusive baseline**: last 7 days versus days -37 to
  -8. Comparing 7 days against a 30-day window that contains those same 7 days
  dilutes the signal by roughly 23%.
- **60s + jitter between Google Trends calls.** GitHub Actions runs on datacenter
  IPs, which pytrends gets 429'd from aggressively. This is why the calibration
  set is 30 keywords, not the full 145.

## Calibration - the measurement, now wired

The eight-week rule is: record whether each named ticker moved more than 10% in
the four weeks after its signal, and expand the keyword pool only above a 40% hit
rate. `signal_outcomes` was built for exactly that and nothing wrote to it, so the
calibration period would have ended with no number to judge against - the one
failure that makes the whole exercise pointless.

`backfill_outcomes.py` runs daily, after analysis and before the digest:

- new signals get an outcome row stamped with the close on the signal date
- older ones get `price_1w`, `price_4w`, `price_12w` filled as each date arrives
- `hit` is judged once, when `price_4w` lands: `price_4w / price_at_signal - 1 > 0.10`

It is idempotent - a filled column is never recomputed, because a historical
close is a fact that does not change and re-fetching only risks a rate limit. It
is also the one script that does **not** swallow its exceptions: a failed write
turns the workflow red, since quietly losing calibration days is the disease
being treated.

```bash
python scripts/backfill_outcomes.py            # backfill, then print the summary
python scripts/backfill_outcomes.py --report   # summary only, writes nothing
```

The report refuses to draw a conclusion from a small sample: under 20 judged
outcomes it prints the rate with a warning that it is not yet a result. Five
signals, three of which worked, is not a 60% hit rate.

Two honest limits. The threshold is a **raw** move, not measured against SMH or
QQQ - in a quarter where the whole AI complex rises 15%, a naive reading of the
hit rate credits the engine for the market's work. And a ticker that resolves to
no price series is recorded as `unresolved`, never estimated; ETFs and most
non-US listings land there, so the denominator is US single names.

## Known gaps

Ordered by how much they cost. None is fixed yet.

- **No deduplication.** A keyword trending for five days sends five identical
  digests. `get_analyzed_signals()` filters on today only, with no memory of what
  was already pushed. This is how a system earns being ignored.
- **Silent failure.** The workflow uploads logs on failure and notifies nobody. It
  could be broken for weeks unnoticed. Every script also catches its own
  exceptions and logs them, so a run where every Supabase write failed still exits
  0 and the digest arrives empty - indistinguishable from a genuinely quiet day.
- **Schedule.** `cron: '0 18 * * *'` is commented as 02:00 Taiwan time, but the
  owner is in Australia, where it lands at 04:00 AEST. Sydney sees daylight
  saving; UTC cron does not follow it, so the local arrival time shifts by an hour
  twice a year.
- **SDK pin is old.** `anthropic==0.39.0` dates from late 2024. The
  `messages.create()` call shape used in `generate_analysis.py` is stable, so it
  works, but the pin is roughly eighteen months behind. `MODEL` is
  `claude-sonnet-4-6`, which is a current model and correct for this job - a
  classification-and-extraction pass over one signal at a time.
- **RSS is fetched twice for Chinese keywords.** `estimate_news_count()` calls
  `fetch_rss_hits()` again on a keyword that already ran it, doubling the feed
  requests for every `zh` keyword.

## Deployment

The engine is not deployed from this repo - it needs its own, because the
workflow must live at a repository root to run.

1. **Supabase** - create a project, run `scripts/schema.sql` in the SQL editor,
   copy the project URL and the `service_role` secret.
2. **Reddit** - reddit.com/prefs/apps, create an app of type `script`, copy the
   client id and secret.
3. **Anthropic** - an API key. Cost is roughly $3-5/month at five analyses a day.
4. **Telegram** - see below.
5. **GitHub secrets** - `SUPABASE_URL`, `SUPABASE_KEY`, `REDDIT_CLIENT_ID`,
   `REDDIT_CLIENT_SECRET`, `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`,
   `TELEGRAM_CHAT_ID`. Never committed.
6. Run the workflow manually once from the Actions tab before trusting the
   schedule.

### Telegram

Three steps, and the third is the one that is easy to miss:

1. Message **@BotFather**, send `/newbot`, answer the two prompts. It returns a
   token of the form `123456789:AAE...`. That is `TELEGRAM_BOT_TOKEN`.
2. Message **@userinfobot**. It replies with your numeric user id. That is
   `TELEGRAM_CHAT_ID`.
3. **Open a chat with your own bot and send it any message.** A Telegram bot
   cannot start a conversation - it may only reply to a chat a human opened
   first. Skip this and `sendMessage` returns
   `403: bot can't initiate conversation with a user`, with everything else
   configured correctly.

Verify without running the pipeline:

```bash
curl -s "https://api.telegram.org/bot<TOKEN>/sendMessage" \
  -d chat_id=<CHAT_ID> -d text=test
```

`{"ok":true,...}` means all three steps are done.
