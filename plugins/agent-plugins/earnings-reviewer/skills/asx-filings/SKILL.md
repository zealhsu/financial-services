---
name: asx-filings
description: Locate and extract financial data from ASX-listed company filings - Appendix 4E, Appendix 4D, annual reports, and Appendix 5B quarterlies. Use whenever modelling, valuing, or writing on an Australian-listed company, and in particular whenever a workflow would otherwise reach for SEC EDGAR on a name that does not file with the SEC. Triggers on ASX tickers, "ASX", "ASX-listed", "Australian listed", "Appendix 4E", "Appendix 4D", "Appendix 5B", "half-year report", "franking credits", or any request to value, model, or analyse a company trading in Australia.
---

# ASX Filings

## Why this skill exists

The modelling and research skills in this repo default to SEC EDGAR and to
10-K / 10-Q document structure. An ASX-listed company files with neither. Load
this skill instead of `references/sec-filings.md` when the subject trades in
Australia, and use the document map and line-item mapping below in place of
the SEC equivalents. Everything downstream - the model mechanics, the valuation
methodology, the note structure - is unchanged.

## Read this before building a quarterly model

**Most ASX companies report half-yearly, not quarterly.** This is the single
biggest structural difference from a US name, and it silently breaks any
workflow that assumes four reporting periods a year.

- A standard ASX industrial or financial reports **twice** a year: a half-year
  result and a full-year result.
- There is no ASX equivalent of the 10-Q. Do not build a 4-quarter historical
  series and do not promise Q1/Q3 numbers - they do not exist.
- The exception is **mining and oil and gas exploration entities**, which lodge
  an Appendix 5B cash flow report and a quarterly activities report every
  quarter. These cover cash flow and activity only; they are not full accounts.

When a skill or template asks for quarterly granularity on a standard ASX name,
say so explicitly and model half-yearly periods (1H / 2H) instead of inventing
quarters.

## Step 1: Locate the filing

Company announcements are the primary source:

- Announcement search: `https://www.asx.com.au/markets/trade-our-cash-market/announcements`
- Historical announcements: `https://www.asx.com.au/markets/trade-our-cash-market/historical-announcements`
- The ASX announcement search matches on the **first 3 characters of the ticker
  code** only, so expect to filter results by company name.

The company's own investor relations page is usually faster and better
organised than the ASX search, and carries the same lodged documents. Prefer it
when you know the company's domain.

## Step 2: Identify the right document

| Document | Listing Rule | Covers | Deadline | What it gives you |
|---|---|---|---|---|
| **Appendix 4E** (preliminary final report) | LR 4.3A | Full year | 2 months after year end | Headline full-year P&L, balance sheet, cash flow, dividend and franking detail. Fast, but preliminary. |
| **Annual Report** | Corporations Act / LR 4.5 | Full year | 3 months after year end (ASIC) | The full statutory accounts including all notes. Use this for anything requiring note-level detail. |
| **Appendix 4D** (half-year report) | LR 4.2A | Half year | 2 months after half-year end | Half-year accounts, reviewed by the auditor. |
| **Appendix 5B** (quarterly cash flow) | LR 5.5 | Quarter | 1 month after quarter end | Mining / oil and gas explorers only. Cash flow only, no P&L or balance sheet. |
| **Quarterly Activities Report** | LR 5.4 | Quarter | 1 month after quarter end | Mining / oil and gas explorers only. Operational narrative. |

Notes on the exceptions:

- Mining exploration entities do **not** lodge an Appendix 4E.
- Mining and oil and gas exploration entities have **75 days** for their
  half-year accounts rather than 2 months, and lodge the accounts directly
  rather than an Appendix 4D.

**Appendix 4E is preliminary.** It lands first and carries the headline
numbers, but the notes - debt maturity, segment splits, lease detail, useful
lives - only appear in the annual report. If the model needs a schedule, wait
for or go back to the annual report rather than guessing from the 4E.

## Step 3: Confirm the fiscal year end

Do not assume a December year end.

- **30 June is the most common Australian FYE.** A "FY25" result for such a
  company covers July 2024 to June 2025.
- Banks and a number of other issuers use different dates. Confirm from the
  cover page of the filing rather than assuming.
- Label every column with the fiscal year end explicitly (e.g. `FY25 (Jun-25)`)
  so a half-year column is never mistaken for a quarter.

## Step 4: Confirm currency and scale

Australian companies report under **AASB standards, which are IFRS-equivalent**
- not US GAAP. Reporting currency is usually AUD, but is not guaranteed: some
ASX-listed companies with offshore operations report in USD.

Check the cover page and the statement headers for both the currency and the
scale (`A$'000`, `A$m`). Set the model currency to match the filing and record
it in the Assumptions tab.

## Step 5: Map the line items

IFRS statement and line-item naming differs from US GAAP. The statements
themselves are also named differently:

| US GAAP / SEC name | IFRS / AASB name |
|---|---|
| Consolidated Statements of Operations | Statement of Profit or Loss and Other Comprehensive Income |
| Consolidated Balance Sheets | Statement of Financial Position |
| Consolidated Statements of Cash Flows | Statement of Cash Flows |
| Consolidated Statements of Stockholders' Equity | Statement of Changes in Equity |

**Income statement**

| Filing line item | Model line item |
|---|---|
| Revenue / Revenue from contracts with customers | Revenue |
| Cost of sales | COGS |
| Employee benefits expense | Included in SG&A or opex |
| Depreciation and amortisation expense | D&A |
| Finance costs | Interest Expense |
| Income tax expense | Taxes |
| Profit for the year / Profit after tax (NPAT) | Net Income |

**Balance sheet**

| Filing line item | Model line item |
|---|---|
| Cash and cash equivalents | Cash |
| Trade and other receivables | AR |
| Inventories | Inventory |
| Property, plant and equipment | PP&E (Net) |
| Right-of-use assets | Lease assets (keep separate from PP&E) |
| Total assets | Total Assets |
| Trade and other payables | AP |
| Borrowings (current) | Current Debt |
| Borrowings (non-current) | LT Debt |
| Lease liabilities | Lease obligations |
| Contributed equity / Issued capital | Share capital |
| Reserves | Reserves (no direct US equivalent - do not fold into retained earnings) |
| Retained earnings / Accumulated losses | Retained Earnings |
| Total equity | Total Equity |

**Cash flow statement**

Structure matches the US form closely. Note that under IFRS, interest and
dividends paid may be classified in operating or financing at the entity's
election - check which, and be consistent across years before computing FCF.

## Step 6: Handle franking credits

Australian dividend imputation has no US equivalent and is easy to miss.

- Dividends are declared with a **franking percentage**. A fully franked
  dividend carries a credit for tax already paid at the company level.
- Quote **both** the cash yield and the grossed-up yield when reporting yield
  to an Australian audience, and label which is which.
- The franking balance is disclosed in the notes and in the Appendix 4E.
- Do not adjust FCF for franking. It affects the shareholder's after-tax
  return, not the entity's cash flow. If a valuation reflects franking, state
  that as an explicit assumption rather than burying it in the discount rate.

## Extraction checklist

- Confirm fiscal year end and label periods accordingly
- Confirm reporting currency and scale
- Confirm whether the company reports half-yearly or is an explorer on
  quarterly Appendix 5Bs
- 3 years of historical P&L and cash flow
- 3 years of historical balance sheet (the annual report gives 2 - pull the
  third from the prior year's report)
- Verify P&L NPAT ties to the cash flow statement starting line
- Verify balance sheet cash ties to cash flow ending cash
- Pull borrowings maturity profile from the notes
- Separate lease liabilities and right-of-use assets from debt and PP&E
- Note franking percentage on declared dividends
- Note any non-recurring items and whether the company reports an
  "underlying" or "normalised" NPAT alongside statutory

## Common variations

| Variation | How to handle |
|---|---|
| Company reports "underlying" and statutory NPAT | Model statutory; show underlying as a reconciling memo line. Never mix the two across years. |
| Appendix 4E published, annual report not yet out | Use the 4E for headline numbers; flag that note-level schedules are pending rather than estimating them. |
| Explorer with no revenue | Appendix 5B cash flow is the only regular financial disclosure. A DCF is usually not the right tool - say so. |
| Dual-listed (ASX + another exchange) | Check whether the primary listing files elsewhere; a NYSE-listed name with a CDI on ASX will have SEC filings, so use `references/sec-filings.md`. |
| Stapled securities (common in A-REITs) | Financials are presented for the stapled group; confirm which entity the share count refers to before computing per-share figures. |
| Reporting currency is not AUD | Adapt model currency to the filing. Do not convert historicals to AUD unless the workflow explicitly asks. |
