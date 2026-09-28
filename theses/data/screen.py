#!/usr/bin/env python3
"""Screen any set of US-listed tickers on SEC fundamentals plus live market data.

The other scripts here were written around one peer set. This one takes any
list, so a batch of names seen in a partner slide or a news post can be put on
the same footing in one run: last-twelve-months revenue, growth, margins and
free cash flow from SEC XBRL, and market cap and one-year price action from
Nasdaq's public quote API.

WHAT IT DOES NOT DO

It does not rank anything as a buy. It reports what a business earns, how fast
it is growing, and what the market is currently paying for that. Whether the
price is right is a judgement, and "which of these goes up next quarter" is not
answerable from here or anywhere else.

  SEC_USER_AGENT="Name you@example.com" python3 screen.py ACN CRWD ...
  python3 screen.py --file tickers.txt --out result.json

Handles both taxonomies: us-gaap for domestic filers and ifrs-full for foreign
private issuers filing 20-F under IFRS. Multiples are only computed when the
filer reports in USD - a EUR revenue line against a USD market cap is a unit
error, not a multiple.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ANNUAL = ('10-K', '20-F', '40-F', '10-K/A', '20-F/A')

US = {
    'revenue': ['RevenueFromContractWithCustomerExcludingAssessedTax', 'Revenues',
                'RevenueFromContractWithCustomerIncludingAssessedTax',
                'RevenuesNetOfInterestExpense'],
    'gross_profit': ['GrossProfit'],
    'cost': ['CostOfRevenue', 'CostOfGoodsAndServicesSold'],
    'op_income': ['OperatingIncomeLoss'],
    'net_income': ['NetIncomeLoss', 'ProfitLoss'],
    'opcf': ['NetCashProvidedByUsedInOperatingActivities',
             'NetCashProvidedByUsedInOperatingActivitiesContinuingOperations'],
    'capex': ['PaymentsToAcquirePropertyPlantAndEquipment',
              'PaymentsToAcquireProductiveAssets'],
}
IFRS = {
    'revenue': ['Revenue', 'RevenueFromContractsWithCustomers'],
    'gross_profit': ['GrossProfit'],
    'cost': ['CostOfSales'],
    'op_income': ['ProfitLossFromOperatingActivities'],
    'net_income': ['ProfitLoss', 'ProfitLossAttributableToOwnersOfParent'],
    'opcf': ['CashFlowsFromUsedInOperatingActivities'],
    'capex': ['PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities',
              'PurchaseOfPropertyPlantAndEquipment'],
}


def ua():
    v = os.environ.get('SEC_USER_AGENT')
    if not v:
        sys.exit('SEC_USER_AGENT is not set (SEC returns 403 without it).')
    return v


def get_json(url, headers, timeout=60):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


# ─────────────────────────────────────────
# SEC
# ─────────────────────────────────────────
def cik_map():
    raw = get_json('https://www.sec.gov/files/company_tickers.json',
                   {'User-Agent': ua()})
    return {v['ticker'].upper(): (str(v['cik_str']).zfill(10), v['title'])
            for v in raw.values()}


def facts_for(ticker, cik, max_age_h=24):
    path = HERE / f'cf_{ticker}.json'
    if path.exists() and time.time() - path.stat().st_mtime < max_age_h * 3600:
        return json.load(open(path))['facts']
    data = get_json(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json',
                    {'User-Agent': ua()})
    json.dump(data, open(path, 'w'))
    time.sleep(0.25)
    return data['facts']


def durations(facts, taxonomy, concepts):
    """{(start, end): (value, form)} across concepts, first concept wins a period.

    Merging per period rather than taking the first concept that returns
    anything is what stops a retired tag from supplying a stale year.
    """
    tax = facts.get(taxonomy, {})
    out, unit_used = {}, None
    for c in concepts:
        node = tax.get(c)
        if not node:
            continue
        units = node.get('units', {})
        unit = 'USD' if 'USD' in units else next(iter(units), None)
        if unit is None:
            continue
        for f in units[unit]:
            if not f.get('start'):
                continue
            key = (date.fromisoformat(f['start']), date.fromisoformat(f['end']))
            if key not in out:
                out[key] = (f['val'], f.get('form'))
                unit_used = unit_used or unit
    return out, unit_used


def ltm(periods):
    """(ltm_value, prior_comparable, as_of, basis). None if no annual period."""
    annual = {k: v for k, v in periods.items()
              if 330 <= (k[1] - k[0]).days <= 400 and v[1] in ANNUAL}
    if not annual:
        return None
    fy = max(annual, key=lambda k: k[1])
    fy_val = annual[fy][0]
    fy_start_next = fy[1] + timedelta(days=1)

    # Year-to-date in the current fiscal year: starts the day after FY end.
    ytd = [k for k in periods
           if abs((k[0] - fy_start_next).days) <= 7 and k[1] > fy[1]
           and (k[1] - k[0]).days <= 320]
    prior_fy = [k for k in annual
                if abs((k[1] - (fy[1] - timedelta(days=365))).days) <= 20]
    prior_fy_val = annual[prior_fy[0]][0] if prior_fy else None

    if not ytd:
        return fy_val, prior_fy_val, fy[1], 'FY'

    cur = max(ytd, key=lambda k: k[1])
    dur = (cur[1] - cur[0]).days
    prev = [k for k in periods
            if abs((k[0] - fy[0]).days) <= 7
            and abs((k[1] - k[0]).days - dur) <= 10]
    if not prev:
        return fy_val, prior_fy_val, fy[1], 'FY'
    prev = min(prev, key=lambda k: abs((k[1] - (cur[1] - timedelta(days=365))).days))
    cur_v, prev_v = periods[cur][0], periods[prev][0]
    value = fy_val + cur_v - prev_v
    # Growth is judged on the most recent comparable window, not the stale FY.
    return value, (cur_v, prev_v), cur[1], 'LTM'


def fundamentals(facts):
    tax = 'us-gaap' if 'us-gaap' in facts else 'ifrs-full'
    cmap = US if tax == 'us-gaap' else IFRS
    out = {'taxonomy': tax}

    rev_p, cur = durations(facts, tax, cmap['revenue'])
    out['currency'] = cur
    r = ltm(rev_p)
    if not r:
        return out
    value, comp, asof, basis = r
    out.update(revenue=value, asof=asof.isoformat(), basis=basis)
    if isinstance(comp, tuple):
        out['growth'] = comp[0] / comp[1] - 1 if comp[1] else None
        out['growth_window'] = 'YTD vs prior YTD'
    elif comp:
        out['growth'] = value / comp - 1
        out['growth_window'] = 'FY vs prior FY'

    def one(key):
        p, _ = durations(facts, tax, cmap[key])
        x = ltm(p) if p else None
        return x[0] if x and x[2] == asof else None

    gp = one('gross_profit')
    if gp is None:
        cost = one('cost')
        gp = value - cost if cost is not None else None
    out['gross_profit'] = gp
    out['op_income'] = one('op_income')
    out['net_income'] = one('net_income')
    opcf, capex = one('opcf'), one('capex')
    out['fcf'] = opcf - capex if opcf is not None and capex is not None else None
    out['opcf'] = opcf
    for src, dst in (('gross_profit', 'gross_margin'), ('op_income', 'op_margin'),
                     ('net_income', 'net_margin'), ('fcf', 'fcf_margin')):
        v = out.get(src)
        out[dst] = v / value if v is not None and value else None
    return out


# ─────────────────────────────────────────
# Market data (Nasdaq public quote API)
# ─────────────────────────────────────────
NASDAQ_H = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}


def money(s):
    if not s or s in ('N/A', '--'):
        return None
    try:
        return float(str(s).replace('$', '').replace(',', ''))
    except ValueError:
        return None


def market(ticker):
    out = {}
    try:
        s = get_json(f'https://api.nasdaq.com/api/quote/{ticker}/summary?assetclass=stocks',
                     NASDAQ_H, 20)['data']['summaryData']
        out['market_cap'] = money(s.get('MarketCap', {}).get('value'))
        hl = (s.get('FiftTwoWeekHighLow', {}) or {}).get('value', '')
        if '/' in hl:
            hi, lo = (money(x) for x in hl.split('/'))
            out['wk52_high'], out['wk52_low'] = hi, lo
        out['sector'] = (s.get('Sector') or {}).get('value')
    except Exception as e:
        out['market_error'] = str(e)[:80]
    try:
        i = get_json(f'https://api.nasdaq.com/api/quote/{ticker}/info?assetclass=stocks',
                     NASDAQ_H, 20)['data']['primaryData']
        out['price'] = money(i.get('lastSalePrice'))
        out['price_asof'] = i.get('lastTradeTimestamp')
    except Exception:
        pass
    try:
        start = (date.today() - timedelta(days=372)).isoformat()
        h = get_json(f'https://api.nasdaq.com/api/quote/{ticker}/historical'
                     f'?assetclass=stocks&fromdate={start}&limit=400', NASDAQ_H, 20)
        rows = (h['data'] or {}).get('tradesTable', {}).get('rows') or []
        closes = [money(r['close']) for r in rows if money(r.get('close'))]
        if len(closes) > 200:              # newest first
            out['ret_1y'] = closes[0] / closes[-1] - 1
            import statistics
            daily = [closes[i] / closes[i + 1] - 1 for i in range(len(closes) - 1)]
            out['vol_1y'] = statistics.pstdev(daily) * (252 ** 0.5)
    except Exception:
        pass
    time.sleep(0.3)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('tickers', nargs='*')
    ap.add_argument('--file')
    ap.add_argument('--out', default=str(HERE / 'screen.json'))
    a = ap.parse_args()
    tickers = list(a.tickers)
    if a.file:
        tickers += [t.strip().upper() for t in open(a.file) if t.strip()
                    and not t.startswith('#')]
    ciks = cik_map()
    results = {}
    for t in tickers:
        rec = {'ticker': t}
        if t not in ciks:
            rec['error'] = 'not an SEC registrant'
        else:
            cik, title = ciks[t]
            rec['name'] = title
            try:
                rec.update(fundamentals(facts_for(t, cik)))
            except Exception as e:
                rec['error'] = f'fundamentals: {e}'[:120]
        rec.update(market(t))
        # A filer can stop tagging and keep trading. SAP's XBRL in companyfacts
        # ends in 2017; without this a nine-year-old revenue line produces a
        # multiple that looks perfectly normal.
        if rec.get('asof') and date.fromisoformat(rec['asof']) < date.today() - timedelta(days=450):
            rec['stale'] = True
        mc, rv = rec.get('market_cap'), rec.get('revenue')
        if mc and rv and rec.get('currency') == 'USD' and not rec.get('stale'):
            rec['ps'] = mc / rv
            ni, fcf = rec.get('net_income'), rec.get('fcf')
            rec['pe'] = mc / ni if ni and ni > 0 else None
            rec['fcf_yield'] = fcf / mc if fcf is not None else None
        results[t] = rec
        g = rec.get('growth')
        print(f"{t:6} rev={rv/1e9 if rv else 0:8.2f}B {rec.get('currency') or '':4} "
              f"g={g*100 if g is not None else float('nan'):6.1f}% "
              f"mcap={mc/1e9 if mc else 0:8.1f}B {rec.get('error','')}", flush=True)
    json.dump(results, open(a.out, 'w'), indent=1, default=str)
    print(f'\n{len(results)} tickers -> {a.out}')


if __name__ == '__main__':
    main()
