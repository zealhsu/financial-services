#!/usr/bin/env python3
"""Build the semis comps table from the extracted SEC XBRL facts."""
import json
from datetime import date

ANNUAL = ('10-K', '20-F')
TICKERS = ['NVDA', 'AMD', 'AVGO', 'MRVL', 'INTC', 'ARM']
NAMES = {'NVDA': 'NVIDIA', 'AMD': 'Advanced Micro Devices', 'AVGO': 'Broadcom',
         'MRVL': 'Marvell Technology', 'INTC': 'Intel', 'ARM': 'Arm Holdings'}

# Delayed quotes off the user's CommSec watchlist, 2026-08-16 ~04:00 AEST.
PRICE = {'NVDA': 225.205, 'AMD': 503.670, 'AVGO': 391.480,
         'MRVL': 220.010, 'INTC': 102.770, 'ARM': 277.530}
PRICE_ASOF = '2026-08-16 (delayed)'


def rows(g, concept):
    node = g.get(concept)
    return node['units'].get('USD', []) if node else []


def annual_rows(g, concept):
    out = []
    for f in rows(g, concept):
        if not f.get('start') or f.get('form') not in ANNUAL:
            continue
        s, e = date.fromisoformat(f['start']), date.fromisoformat(f['end'])
        if 330 <= (e - s).days <= 400:
            out.append((e, f['val']))
    return out


def at_fye(g, concept, fye, tol=10):
    cand = [(e, v) for e, v in annual_rows(g, concept) if abs((e - fye).days) <= tol]
    return max(cand)[1] if cand else None


def da_total(g, fye):
    """DD&A is the combined figure when a filer tags it. Broadcom and AMD tag
    depreciation and intangible amortisation separately instead, and taking only
    the first understates Broadcom's D&A by about 8bn."""
    combined = at_fye(g, 'DepreciationDepletionAndAmortization', fye)
    if combined:
        return combined, 'DepreciationDepletionAndAmortization'
    dep = at_fye(g, 'Depreciation', fye) or 0
    amort = at_fye(g, 'AmortizationOfIntangibleAssets', fye) or 0
    if dep or amort:
        return dep + amort, 'Depreciation + AmortizationOfIntangibleAssets'
    return None, None


def net_income(g, fye):
    for c in ('NetIncomeLoss', 'ProfitLoss',
              'NetIncomeLossAvailableToCommonStockholdersBasic'):
        v = at_fye(g, c, fye)
        if v is not None:
            return v, c
    return None, None


raw = json.load(open('raw.json'))
comps = {}
for t in TICKERS:
    g = json.load(open(f'cf_{t}.json'))['facts']['us-gaap']
    r = raw[t]
    fye = date.fromisoformat(r['fye'])

    da, da_src = da_total(g, fye)
    ni, ni_src = net_income(g, fye)

    rev, gp, oi = r['revenue'], r['gross_profit'], r['op_income']
    ebitda = (oi + da) if (oi is not None and da is not None) else None
    cash = (r['cash'] or 0) + (r['sti'] or 0)
    debt = (r['debt_lt'] or 0) + (r['debt_st'] or 0)
    mcap = PRICE[t] * r['shares']
    ev = mcap + debt - cash

    comps[t] = {
        'name': NAMES[t], 'fye': r['fye'], 'price': PRICE[t], 'shares': r['shares'],
        'revenue': rev, 'growth': r['growth'],
        'gross_margin': gp / rev if gp else None,
        'ebitda': ebitda, 'ebitda_margin': ebitda / rev if ebitda else None,
        'net_income': ni, 'da': da, 'da_source': da_src, 'ni_source': ni_src,
        'cash': cash, 'debt': debt, 'mcap': mcap, 'ev': ev,
        'ev_rev': ev / rev if rev else None,
        'ev_ebitda': ev / ebitda if ebitda and ebitda > 0 else None,
        'pe': mcap / ni if ni and ni > 0 else None,
    }

json.dump(comps, open('comps.json', 'w'), indent=1, default=str)

B = 1e9
def f(x, p=1, suf=''):
    return 'n/a' if x is None else f'{x:,.{p}f}{suf}'

print(f'{"":6}{"FYE":>11}{"Rev($B)":>9}{"Grw":>7}{"GM":>7}{"EBITDA":>9}{"EBM":>7}'
      f'{"NI($B)":>9}{"MCap($B)":>10}{"EV($B)":>9}{"EV/Rev":>8}{"EV/EBI":>8}{"P/E":>7}')
for t, c in comps.items():
    print(f'{t:6}{c["fye"]:>11}{f(c["revenue"]/B):>9}'
          f'{f(c["growth"]*100 if c["growth"] else None,0,"%"):>7}'
          f'{f(c["gross_margin"]*100 if c["gross_margin"] else None,0,"%"):>7}'
          f'{f(c["ebitda"]/B if c["ebitda"] else None):>9}'
          f'{f(c["ebitda_margin"]*100 if c["ebitda_margin"] else None,0,"%"):>7}'
          f'{f(c["net_income"]/B if c["net_income"] else None):>9}'
          f'{f(c["mcap"]/B,0):>10}{f(c["ev"]/B,0):>9}'
          f'{f(c["ev_rev"]):>8}{f(c["ev_ebitda"]):>8}{f(c["pe"],0):>7}')

print('\nD&A source used:')
for t, c in comps.items():
    print(f'  {t:6} {f(c["da"]/B if c["da"] else None)}B  <- {c["da_source"]}')
print('\nNet income source:')
for t, c in comps.items():
    print(f'  {t:6} {c["ni_source"] or "NOT FOUND"}')
