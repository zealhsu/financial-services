# SEC Filings Data Extraction Reference

**When to Use:** Only reference this file when a model template specifically requires pulling data from SEC filings (10-K, 10-Q). For templates that provide data directly or use other data sources, this reference is not needed.

---

## Extracting Data from SEC Filings (10-K / 10-Q)

When populating a model template with public company data, extract financials directly from SEC filings.

### Step 0: Set a User-Agent

**Every request to `sec.gov` and `data.sec.gov` must send a descriptive `User-Agent` header.** SEC's fair-access policy asks for a declared identity with contact details, and requests that look like a bare scripting client are rejected with `403` before any data is returned. A default `curl` or `curl/8.x` agent fails; any descriptive string succeeds.

```bash
UA="Firm Name research (contact: analyst@example.com)"
curl -H "User-Agent: $UA" "https://data.sec.gov/api/xbrl/companyfacts/CIK0001045810.json"
```

A `403` here means the header is missing or looks automated, not that the filing is unavailable. Keep requests under 10 per second.

### Step 1: Locate the Filing

**Prefer the XBRL API over the HTML filing.** SEC publishes every tagged figure as JSON, which removes the document parsing step entirely:

| Endpoint | Returns |
|---|---|
| `https://www.sec.gov/files/company_tickers.json` | Ticker to CIK map for every registrant |
| `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json` | Every tagged fact, all periods, one company |
| `https://data.sec.gov/api/xbrl/companyconcept/CIK##########/us-gaap/<Concept>.json` | One concept's full history |

CIK must be zero-padded to 10 digits. Each fact carries `start`, `end`, `form`, `fy` and `val`, so annual figures are the rows where `form` is `10-K` (or `20-F` for a foreign private issuer) and the period spans roughly 365 days.

Fall back to the filing documents when a figure is narrative or untagged:

1. Use SEC EDGAR: `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=[TICKER]&type=10-K`
2. For quarterly data, use `type=10-Q`

**Concept names are not consistent across filers.** Always search several tags and take the most recent match rather than accepting the first tag that returns anything -- a filer may have retired a tag years ago and left stale data behind it. Two traps worth naming:

- **Revenue** appears as `RevenueFromContractWithCustomerExcludingAssessedTax` for most filers but `Revenues` for others.
- **D&A** is a combined `DepreciationDepletionAndAmortization` for some filers, while others tag `Depreciation` and `AmortizationOfIntangibleAssets` separately. Taking only the first understates D&A, and therefore EBITDA, for any company carrying material acquisition intangibles.

### Step 2: Identify Filing Currency

Before extracting data, identify the reporting currency:
- Check the cover page or header for reporting currency
- Look at statement headers (e.g., "in thousands of U.S. dollars")
- Review Note 1 (Summary of Significant Accounting Policies)

**Common Currency Indicators**

| Indicator | Currency |
|-----------|----------|
| $, USD | US Dollar |
| €, EUR | Euro |
| £, GBP | British Pound |
| ¥, JPY | Japanese Yen |
| ¥, CNY, RMB | Chinese Yuan |
| CHF | Swiss Franc |
| CAD, C$ | Canadian Dollar |

Set model currency to match filing; document in Assumptions tab.

### Step 3: Navigate to Financial Statements

Within the 10-K or 10-Q, locate:
- **Item 8** (10-K) or **Item 1** (10-Q): Financial Statements
- Key sections to extract:
  - Consolidated Statements of Operations (Income Statement)
  - Consolidated Balance Sheets
  - Consolidated Statements of Cash Flows
  - Notes to Financial Statements (for schedule details)

### Step 4: Data Extraction Mapping

**Income Statement (from Consolidated Statements of Operations)**

| Filing Line Item | Model Line Item |
|------------------|-----------------|
| Net revenues / Net sales | Revenue |
| Cost of goods sold | COGS |
| Selling, general and administrative | SG&A |
| Depreciation and amortization | D&A |
| Interest expense, net | Interest Expense |
| Income tax expense | Taxes |
| Net income | Net Income |

**Balance Sheet (from Consolidated Balance Sheets)**

| Filing Line Item | Model Line Item |
|------------------|-----------------|
| Cash and cash equivalents | Cash |
| Accounts receivable, net | AR |
| Inventories | Inventory |
| Property, plant and equipment, net | PP&E (Net) |
| Total assets | Total Assets |
| Accounts payable | AP |
| Short-term debt / Current portion of LT debt | Current Debt |
| Long-term debt | LT Debt |
| Retained earnings | Retained Earnings |
| Total stockholders' equity | Total Equity |

**Cash Flow Statement (from Consolidated Statements of Cash Flows)**

| Filing Line Item | Model Line Item |
|------------------|-----------------|
| Net income | Net Income |
| Depreciation and amortization | D&A |
| Changes in accounts receivable | ΔAR |
| Changes in inventories | ΔInventory |
| Changes in accounts payable | ΔAP |
| Capital expenditures | CapEx |
| Proceeds from issuance of common stock | Equity Issuance |
| Proceeds from / Repayments of debt | Debt activity |
| Dividends paid | Dividends |

### Step 5: Extract Supporting Detail from Notes

For schedules, pull from Notes to Financial Statements:
- **Note: Debt** → Maturity schedule, interest rates, covenants
- **Note: Property, Plant & Equipment** → Gross PP&E, accumulated depreciation, useful lives
- **Note: Revenue** → Segment breakdowns, geographic splits
- **Note: Leases** → Operating vs. finance lease obligations

### Step 6: Historical Data Requirements

Extract 3 years of historical data minimum:
- 10-K provides 3 years of IS/CF, 2 years of BS
- For 3rd year BS, pull from prior year's 10-K
- Use 10-Qs to fill in quarterly granularity if needed

### Data Extraction Checklist

- Identify reporting currency and scale (thousands, millions)
- 3 years historical Income Statement
- 3 years historical Cash Flow Statement
- 3 years historical Balance Sheet
- Verify IS Net Income = CF starting Net Income (each year)
- Verify BS Cash = CF Ending Cash (each year)
- Extract debt maturity schedule from notes
- Extract D&A detail or useful life assumptions
- Note any non-recurring / one-time items to normalize

### Handling Common Filing Variations

| Variation | How to Handle |
|-----------|---------------|
| D&A embedded in COGS/SG&A | Pull D&A from Cash Flow Statement |
| "Other" line items are material | Check notes for breakdown |
| Restatements | Use restated figures, note in assumptions |
| Fiscal year ≠ calendar year | Label with fiscal year end (e.g., FYE Jan 2025) |
| Non-USD reporting currency | Adapt model currency to match filing |
