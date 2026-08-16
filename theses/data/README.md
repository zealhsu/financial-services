# theses/data

Extraction scripts and their output. Every figure quoted in a thesis should be
re-derivable from here rather than taken on trust.

| File | What it does |
|---|---|
| `extract.py` | Pulls revenue, margins, balance-sheet items per company from SEC XBRL |
| `ltm.py` | Rolls each company onto a last-twelve-months basis |
| `build_comps.py` | Assembles the peer comparison and multiples |
| `leading_indicators.py` | Purchase obligations, inventory days, hyperscaler capex |
| `validate_tickers.py` | Checks symbols against SEC's registrant list |

All of them need a descriptive `SEC_USER_AGENT`; SEC answers `403` without one.

```bash
export SEC_USER_AGENT="Your Name (contact: you@example.com)"
```

## validate_tickers.py

Standard library only and no imports from this repo, so it can be copied into
another project unchanged.

```bash
python3 validate_tickers.py NVDA INFQ SMH ZZQQXX
```

```python
from validate_tickers import annotate, split, validate

annotate(['NVDA', 'ZZQQXX'])   # ['NVDA', 'ZZQQXX ⚠️']
split(['NVDA', 'SMH'])         # (['NVDA'], ['SMH'])
validate(['NVDA'])             # {'NVDA': {'status': 'verified', 'name': ..., 'cik': ...}}
```

### The test is one-way

A symbol **present** in SEC's list is a real registrant. A symbol **absent**
is *unconfirmed*, not fake:

| Symbol | Result | Why |
|---|---|---|
| `NVDA` | verified | Operating company, files 10-K |
| `QQQ` | verified | Trust that files with SEC |
| `SMH`, `BOTZ`, `AIQ`, `UFO` | unconfirmed | ETFs whose trust does not register under that symbol |
| `MOG` | unconfirmed | Moog trades dual-class as `MOG.A` / `MOG.B` |
| `2313`, `NDQ` | unconfirmed | TWSE and ASX listings are outside SEC's remit |

So **mark the unconfirmed, never silently drop them** - suppressing them would
throw away every ETF and every non-US name in a watchlist.

### Integrating with a signal digest

Where a pipeline pushes LLM-suggested tickers to a phone, the symbols should be
checked first. One import and one line:

```python
from validate_tickers import annotate

tickers = sig.get("potential_tickers", []) or []
tickers = annotate(tickers)                      # <- add this
ticker_str = "、".join(tickers[:5]) if tickers else "（無明確標的）"
```

Add a legend to the message so the marker means something to the reader:

```
⚠️ = 未在 SEC 註冊清單中（可能是 ETF、台股或美股以外標的，需自行確認）
```

An LLM asked to name beneficiaries of a trend will occasionally invent a
plausible symbol, and a digest that pushes it unmarked gives a hallucination the
same standing as a real holding. The failure is worst exactly where this kind of
system is most useful: an LLM fact-checking from its training data misses recent
listings, so the newest spin-offs, SPACs and IPOs -- the ones worth finding early
-- are the ones it most often calls fake.

Measured against one hand-checked list of seven "confirmed fake" symbols, five
turned out to be real SEC registrants, all of them 2025-2026 listings.
