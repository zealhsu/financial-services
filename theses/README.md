# Theses

Investment theses tracked across sessions, one file per position.

A cloud session gets a fresh container each time, so anything not committed
here is gone by the next one. These files are the persistence layer: the
dashboard and the scheduled review both read from them.

## Layout

```
theses/
  <TICKER>.md          thesis - YAML frontmatter (machine-read) + narrative
  data/
    *.json             extracted financials backing the valuation anchors
    *.py               the extraction scripts, so a figure can be re-derived
```

## Conventions

- **Frontmatter is the contract.** Pillars carry an `id`, a falsifiable
  `test`, a `status` and a `trend`. The dashboard renders these; the scheduled
  review updates them. Keep the keys stable.
- **A pillar with no test is not a pillar.** If nothing could show it false,
  it does not belong in the file.
- **Mark what is whose.** Owner-stated rationale and derived analysis are
  different things and are labelled as such. Placeholders Claude invented -
  thresholds especially - stay flagged until the owner confirms them.
- **Never delete update-log rows.** Disconfirming entries are the point.

## Data basis

Figures come from the SEC XBRL API (`data.sec.gov`), which is free and
carries as-filed audited numbers. Requests need a descriptive `User-Agent` or
SEC returns 403 - see `sec-filings.md` in the financial-analysis plugin.

Valuation is struck on **LTM**, not the latest fiscal year. In a set growing
20-65% a year the annual figure runs up to three quarters stale, which
overstates every denominator and flatters every multiple.

Not investment advice. Analyst work product for review by a qualified
professional.
