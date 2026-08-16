#!/usr/bin/env python3
"""Leading indicators for the NVDA thesis, straight from SEC XBRL.

Gross margin is an output. By the time it moves, whatever caused it moved
several quarters earlier. These three run ahead of it:

  Purchase obligations   what NVIDIA has committed to buy from its supply
                         chain - the company's own bet on future demand
  Inventory days         builds before demand weakness shows in revenue
  Hyperscaler capex      the demand side of pillar 1, measured rather than
                         assumed

Customer concentration would belong here too, but NVIDIA discloses it as
narrative text in the 10-K rather than tagging it, so it cannot be pulled
this way. It needs reading the filing.

Run from the directory holding cf_<TICKER>.json companyfacts dumps.
"""
import json
from datetime import date

HYPERSCALERS = ['MSFT', 'GOOGL', 'AMZN', 'META']
CAPEX = ['PaymentsToAcquirePropertyPlantAndEquipment',
         'PaymentsToAcquireProductiveAssets']


def facts(t):
    return json.load(open(f'cf_{t}.json'))['facts']['us-gaap']


def rows(g, concepts, instant=False):
    out = []
    for c in concepts:
        node = g.get(c)
        if not node:
            continue
        for f in node['units'].get('USD', []):
            has_start = bool(f.get('start'))
            if instant == has_start:
                continue
            e = date.fromisoformat(f['end'])
            days = (e - date.fromisoformat(f['start'])).days if has_start else 0
            out.append({'end': e, 'val': f['val'], 'days': days,
                        'form': f.get('form'), 'concept': c})
    return sorted(out, key=lambda r: r['end'])


def latest_annual(g, concepts):
    r = [x for x in rows(g, concepts) if 330 <= x['days'] <= 400
         and x['form'] in ('10-K', '20-F')]
    return max(r, key=lambda x: x['end']) if r else None


def annual_series(g, concepts):
    seen = {}
    for x in rows(g, concepts):
        if 330 <= x['days'] <= 400 and x['form'] in ('10-K', '20-F'):
            seen[x['end']] = x['val']
    return sorted(seen.items())


def report():
    out = {}
    g = facts('NVDA')

    # --- purchase obligations: NVIDIA's own forward bet -------------------
    po = rows(g, ['PurchaseObligation'], instant=True)
    if po:
        by_date = sorted({x['end']: x['val'] for x in po}.items())
        out['purchase_obligations'] = [
            {'asof': str(d), 'usd': v} for d, v in by_date[-6:]]

    # --- inventory days ---------------------------------------------------
    inv = rows(g, ['InventoryNet'], instant=True)
    cogs_q = [x for x in rows(g, ['CostOfRevenue', 'CostOfGoodsAndServicesSold'])
              if 80 <= x['days'] <= 100]
    days = []
    for i in sorted({x['end']: x['val'] for x in inv}.items())[-8:]:
        d, v = i
        near = [c for c in cogs_q if abs((c['end'] - d).days) <= 5]
        if not near:
            continue
        q = near[-1]['val']
        days.append({'asof': str(d), 'inventory_usd': v, 'quarter_cogs_usd': q,
                     'days_of_inventory': round(v / (q / 91.0), 1)})
    out['inventory_days'] = days

    # --- pillar 1: hyperscaler capex, measured ---------------------------
    cap = {}
    for t in HYPERSCALERS:
        try:
            s = annual_series(facts(t), CAPEX)
        except FileNotFoundError:
            continue
        if s:
            cap[t] = [{'fye': str(d), 'usd': v} for d, v in s[-3:]]
    out['hyperscaler_capex'] = cap

    if cap:
        years = {}
        for t, series in cap.items():
            for e in series:
                years.setdefault(e['fye'][:4], {})[t] = e['usd']
        agg = {y: sum(v.values()) for y, v in years.items()
               if len(v) == len(cap)}
        out['hyperscaler_capex_total'] = [
            {'year': y, 'usd': agg[y]} for y in sorted(agg)]
    return out


if __name__ == '__main__':
    r = report()
    B = 1e9

    print('PURCHASE OBLIGATIONS  (NVIDIA committed spend with its supply chain)')
    prev = None
    for e in r.get('purchase_obligations', []):
        d = f'  {(e["usd"]/prev-1)*100:+.0f}%' if prev else ''
        print(f'  {e["asof"]}   ${e["usd"]/B:8.2f}B{d}')
        prev = e['usd']

    print('\nINVENTORY DAYS  (inventory / daily cost of revenue)')
    for e in r.get('inventory_days', []):
        print(f'  {e["asof"]}   ${e["inventory_usd"]/B:6.2f}B   '
              f'{e["days_of_inventory"]:5.1f} days')

    print('\nHYPERSCALER CAPEX  (pillar 1 - the demand side)')
    for t, series in r.get('hyperscaler_capex', {}).items():
        vals = '  '.join(f'{e["fye"][:4]}: ${e["usd"]/B:6.1f}B' for e in series)
        print(f'  {t:6} {vals}')
    tot = r.get('hyperscaler_capex_total', [])
    if tot:
        print('\n  Combined:')
        prev = None
        for e in tot:
            d = f'   {(e["usd"]/prev-1)*100:+.1f}% YoY' if prev else ''
            print(f'    {e["year"]}   ${e["usd"]/B:7.1f}B{d}')
            prev = e['usd']

    json.dump(r, open('leading_indicators.json', 'w'), indent=1)
