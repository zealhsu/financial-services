#!/usr/bin/env python3
"""Pull comps inputs for a peer set straight from SEC XBRL companyfacts."""
import json
from datetime import date

ANNUAL_FORMS = ('10-K', '20-F')
TICKERS = ['NVDA', 'AMD', 'AVGO', 'MRVL', 'INTC', 'ARM']

# concept fallbacks, most specific first
FLOW = {
    'revenue': ['RevenueFromContractWithCustomerExcludingAssessedTax', 'Revenues',
                'RevenueFromContractWithCustomerIncludingAssessedTax'],
    'gross_profit': ['GrossProfit'],
    'op_income': ['OperatingIncomeLoss'],
    'da': ['DepreciationDepletionAndAmortization', 'DepreciationAmortizationAndAccretionNet',
           'DepreciationAndAmortization', 'DepreciationNonproduction', 'Depreciation'],
    'net_income': ['NetIncomeLoss'],
}
STOCK = {
    'cash': ['CashAndCashEquivalentsAtCarryingValue'],
    'sti': ['ShortTermInvestments', 'MarketableSecuritiesCurrent',
            'AvailableForSaleSecuritiesDebtSecuritiesCurrent'],
    'debt_lt': ['LongTermDebtNoncurrent', 'LongTermDebt'],
    'debt_st': ['LongTermDebtCurrent', 'DebtCurrent'],
}


def units(facts, concept):
    node = facts.get('us-gaap', {}).get(concept)
    if not node:
        return []
    for u in ('USD', 'shares', 'pure'):
        if u in node['units']:
            return node['units'][u]
    return []


def annual(facts, concepts):
    """Most recent ~12-month period from a 10-K, with its end date."""
    best = None
    for c in concepts:
        for f in units(facts, c):
            if not f.get('start') or f.get('form') not in ANNUAL_FORMS:
                continue
            s, e = date.fromisoformat(f['start']), date.fromisoformat(f['end'])
            days = (e - s).days
            if not (330 <= days <= 400):
                continue
            if best is None or e > best['end']:
                best = {'val': f['val'], 'end': e, 'concept': c, 'fy': f.get('fy')}
    return best


def prior_year(facts, concepts, latest_end):
    """The comparable period one year before latest_end, for a growth rate."""
    target = latest_end.replace(year=latest_end.year - 1)
    best, gap = None, 9999
    for c in concepts:
        for f in units(facts, c):
            if not f.get('start') or f.get('form') not in ANNUAL_FORMS:
                continue
            s, e = date.fromisoformat(f['start']), date.fromisoformat(f['end'])
            if not (330 <= (e - s).days <= 400):
                continue
            d = abs((e - target).days)
            if d < gap and d < 45:
                best, gap = f['val'], d
    return best


def latest_instant(facts, concepts, on_or_before):
    """Balance-sheet value at the fiscal year end we are using."""
    best, gap = None, 9999
    for c in concepts:
        for f in units(facts, c):
            if f.get('start') or f.get('form') not in ANNUAL_FORMS:
                continue
            e = date.fromisoformat(f['end'])
            d = abs((e - on_or_before).days)
            if d < gap and d <= 10:
                best, gap = f['val'], d
    return best


def shares_outstanding(facts):
    node = facts.get('dei', {}).get('EntityCommonStockSharesOutstanding')
    if not node:
        return None
    rows = node['units'].get('shares', [])
    return max(rows, key=lambda r: r['end'])['val'] if rows else None


out = {}
for t in TICKERS:
    facts = json.load(open(f'cf_{t}.json'))['facts']
    rec = {}
    rev = annual(facts, FLOW['revenue'])
    if not rev:
        print(f'{t}: no revenue found')
        continue
    fye = rev['end']
    rec['fye'] = fye.isoformat()
    rec['revenue'] = rev['val']
    rec['revenue_concept'] = rev['concept']
    pr = prior_year(facts, FLOW['revenue'], fye)
    rec['revenue_prior'] = pr
    rec['growth'] = (rev['val'] / pr - 1) if pr else None

    for k in ('gross_profit', 'op_income', 'da', 'net_income'):
        a = annual(facts, FLOW[k])
        rec[k] = a['val'] if a and abs((a['end'] - fye).days) <= 10 else None

    for k, cs in STOCK.items():
        rec[k] = latest_instant(facts, cs, fye)

    rec['shares'] = shares_outstanding(facts)
    out[t] = rec

json.dump(out, open('raw.json', 'w'), indent=1, default=str)

print(f"{'':6} {'FYE':>12} {'Revenue':>12} {'Growth':>8} {'GrossPft':>11} "
      f"{'OpInc':>11} {'D&A':>9} {'NetInc':>11} {'Shares':>10}")
for t, r in out.items():
    g = f"{r['growth']*100:.1f}%" if r['growth'] is not None else 'n/a'
    def b(x): return f"{x/1e9:.2f}" if x else 'n/a'
    print(f"{t:6} {r['fye']:>12} {b(r['revenue']):>12} {g:>8} {b(r['gross_profit']):>11} "
          f"{b(r['op_income']):>11} {b(r['da']):>9} {b(r['net_income']):>11} "
          f"{(r['shares']/1e6 if r['shares'] else 0):>9.0f}M")
