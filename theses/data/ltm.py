#!/usr/bin/env python3
"""Roll each peer forward to a last-twelve-months basis.

The latest 10-K is up to three quarters stale in a set growing this fast --
NVIDIA booked 81.6bn in one quarter against a 215.9bn fiscal year -- so
multiples struck on the annual figure overstate every denominator.

LTM = latest fiscal year + year-to-date current year - year-to-date prior year.
Only YTD figures are needed, and those are tagged on every 10-Q.
"""
import json
from datetime import date

ANNUAL = ('10-K', '20-F')
TICKERS = ['NVDA', 'AMD', 'AVGO', 'MRVL', 'INTC', 'ARM']
CONCEPTS = {
    'revenue': ['RevenueFromContractWithCustomerExcludingAssessedTax', 'Revenues'],
    'gross_profit': ['GrossProfit'],
    'op_income': ['OperatingIncomeLoss'],
    'net_income': ['NetIncomeLoss', 'ProfitLoss'],
    'da_combined': ['DepreciationDepletionAndAmortization'],
    'dep': ['Depreciation'],
    'amort': ['AmortizationOfIntangibleAssets'],
}


def periods(g, concepts, forms=None):
    """Every tagged duration for a concept: (start, end, days, value, form)."""
    out = []
    for c in concepts:
        node = g.get(c)
        if not node:
            continue
        for f in node['units'].get('USD', []):
            if not f.get('start'):
                continue
            if forms and f.get('form') not in forms:
                continue
            s, e = date.fromisoformat(f['start']), date.fromisoformat(f['end'])
            out.append((s, e, (e - s).days, f['val'], f.get('form')))
    return sorted(set(out))


def latest_fy(g, concepts):
    fy = [p for p in periods(g, concepts, ANNUAL) if 330 <= p[2] <= 400]
    return max(fy, key=lambda p: p[1]) if fy else None


def ytd_at(g, concepts, fy_start, upto_end):
    """Longest year-to-date period starting at fy_start, ending by upto_end."""
    c = [p for p in periods(g, concepts)
         if abs((p[0] - fy_start).days) <= 5 and p[1] <= upto_end and p[2] <= 320]
    return max(c, key=lambda p: p[2]) if c else None


def ltm(g, concepts):
    """Returns (value, as_of_date, basis) or None."""
    fy = latest_fy(g, concepts)
    if not fy:
        return None
    fy_start, fy_end, _, fy_val, _ = fy
    # current-year YTD: periods starting just after the last fiscal year end
    nxt = [p for p in periods(g, concepts)
           if abs((p[0] - fy_end).days) <= 8 and p[2] <= 320]
    if not nxt:
        return fy_val, fy_end, 'FY (no interim filed since)'
    cur = max(nxt, key=lambda p: p[1])
    prior = ytd_at(g, concepts, fy_start, fy_end)
    # match the prior-year stub to the same length as the current one
    cands = [p for p in periods(g, concepts)
             if abs((p[0] - fy_start).days) <= 5 and abs(p[2] - cur[2]) <= 12]
    if cands:
        prior = min(cands, key=lambda p: abs(p[2] - cur[2]))
    if not prior:
        return fy_val, fy_end, 'FY (no comparable prior stub)'
    return fy_val + cur[3] - prior[3], cur[1], f'LTM to {cur[1]}'


out = {}
for t in TICKERS:
    g = json.load(open(f'cf_{t}.json'))['facts']['us-gaap']
    rec = {}
    for k, cs in CONCEPTS.items():
        r = ltm(g, cs)
        rec[k] = {'val': r[0], 'asof': str(r[1]), 'basis': r[2]} if r else None
    # D&A: combined tag when the filer uses it, else depreciation + amortisation
    if rec['da_combined']:
        rec['da'] = rec['da_combined']
    else:
        d = rec['dep']['val'] if rec['dep'] else 0
        a = rec['amort']['val'] if rec['amort'] else 0
        src = rec['dep'] or rec['amort']
        rec['da'] = {'val': d + a, 'asof': src['asof'] if src else None,
                     'basis': 'dep + amort'} if (d or a) else None
    out[t] = rec

json.dump(out, open('ltm.json', 'w'), indent=1)

print(f"{'':6}{'LTM Revenue':>14}{'as of':>13}{'LTM EBITDA':>13}{'LTM NetInc':>12}  basis")
for t, r in out.items():
    rev, oi, da, ni = r['revenue'], r['op_income'], r['da'], r['net_income']
    eb = (oi['val'] + da['val']) if oi and da else None
    print(f"{t:6}{rev['val']/1e9:>12.2f}B{rev['asof']:>13}"
          f"{(eb/1e9 if eb else 0):>11.2f}B{(ni['val']/1e9 if ni else 0):>10.2f}B"
          f"  {rev['basis']}")
