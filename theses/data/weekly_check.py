#!/usr/bin/env python3
"""Re-measure every thesis against fresh SEC data and update it in place.

WHY THIS IS NOT AN LLM

The frontmatter in a thesis file is a machine contract: pillars carry a `test`
and a `latest`, exit triggers carry `metric` / `op` / `threshold`. Comparing a
fresh number against a recorded threshold is arithmetic. Handing that to a
model adds cost, latency and a small chance of a wrong number on the one
computation that gates a sell decision. So the numbers are computed here, and
the prose stays where a human wrote it.

Triggers that are genuinely a matter of judgement - "Taiwan Strait risk
materialises" - carry `evaluated_by: human` and are reported as unevaluated
every run. Silence on those would read as "checked, fine".

  python3 weekly_check.py               # measure, rewrite files, notify
  python3 weekly_check.py --dry-run     # measure and print, change nothing

Environment:
  SEC_USER_AGENT   required by fetch.py
  NTFY_TOPIC       optional - no topic, no push, everything else still runs
"""
import argparse
import json
import os
import re
import sys
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

import leading_indicators

HERE = Path(__file__).resolve().parent
THESES = HERE.parent

ANNUAL_FORMS = ('10-K', '20-F')
REVENUE = ['RevenueFromContractWithCustomerExcludingAssessedTax', 'Revenues',
           'RevenueFromContractWithCustomerIncludingAssessedTax']

# How much a value must move before it is worth a line in the update log.
# Without this every run rewrites the file with noise in the last decimal and
# the git history stops being readable.
MATERIAL = {'gross_margin': 0.002, 'inventory_days': 1.0,
            'hyperscaler_capex': 1e9}


# ─────────────────────────────────────────
# Metrics
# ─────────────────────────────────────────
def _facts(ticker):
    path = HERE / f'cf_{ticker}.json'
    if not path.exists():
        return None
    return json.load(open(path))['facts']


def _annual_series(facts, concepts):
    """[(end_date, value)] for annual periods, oldest first."""
    seen = {}
    for c in concepts:
        node = facts.get('us-gaap', {}).get(c)
        if not node:
            continue
        for f in node['units'].get('USD', []):
            if not f.get('start') or f.get('form') not in ANNUAL_FORMS:
                continue
            s, e = date.fromisoformat(f['start']), date.fromisoformat(f['end'])
            if 330 <= (e - s).days <= 400:
                seen[e] = f['val']
    return sorted(seen.items())


def gross_margin(ticker):
    """(margin, fiscal_year_end, yoy_change_in_margin_points)."""
    facts = _facts(ticker)
    if not facts:
        return None
    rev = dict(_annual_series(facts, REVENUE))
    gp = dict(_annual_series(facts, ['GrossProfit']))
    both = sorted(set(rev) & set(gp))
    if not both:
        return None

    latest = both[-1]
    margin = gp[latest] / rev[latest]
    delta = None
    if len(both) >= 2:
        prev = both[-2]
        delta = margin - (gp[prev] / rev[prev])
    return {'value': margin, 'asof': latest.isoformat(), 'yoy_delta': delta}


def indicators():
    """Reuse leading_indicators.report(), which reads the same cf_*.json."""
    cwd = os.getcwd()
    os.chdir(HERE)
    try:
        return leading_indicators.report()
    finally:
        os.chdir(cwd)


def measure(ticker):
    """Every metric this script knows how to compute, for one ticker."""
    out = {}
    gm = gross_margin(ticker)
    if gm:
        out['gross_margin'] = gm
        if gm['yoy_delta'] is not None:
            out['gross_margin_yoy_delta'] = {
                'value': gm['yoy_delta'], 'asof': gm['asof']}

    if ticker == 'NVDA':
        # Pillar 1 and the inventory series are NVDA-specific by construction:
        # hyperscaler capex is the demand side of *this* thesis, not a general
        # metric. Another ticker would need its own definition, not this one.
        try:
            ind = indicators()
        except Exception as e:
            print(f'  leading indicators unavailable: {e}', file=sys.stderr)
            return out

        inv = ind.get('inventory_days') or []
        if inv:
            out['inventory_days'] = {'value': inv[-1]['days_of_inventory'],
                                     'asof': inv[-1]['asof']}
        tot = ind.get('hyperscaler_capex_total') or []
        if tot:
            latest = tot[-1]
            out['hyperscaler_capex'] = {'value': latest['usd'],
                                        'asof': latest['year']}
            if len(tot) >= 2:
                out['hyperscaler_capex_prior'] = {'value': tot[-2]['usd'],
                                                  'asof': tot[-2]['year']}
        po = ind.get('purchase_obligations') or []
        if po:
            out['purchase_obligations'] = {'value': po[-1]['usd'],
                                           'asof': po[-1]['asof']}
    return out


# ─────────────────────────────────────────
# Frontmatter: read with yaml, write with surgical edits
# ─────────────────────────────────────────
def split_frontmatter(text):
    m = re.match(r'^---\n(.*?)\n---\n', text, re.S)
    if not m:
        return None, text
    return yaml.safe_load(m.group(1)), text


def set_field(text, block_id, field, value):
    """Set `field` inside the YAML list item whose `id:` is block_id.

    Deliberately not a yaml round-trip. yaml.dump would reflow the whole
    frontmatter - dropping the comments, re-wrapping every folded string,
    reordering nothing but changing every line - and turn each weekly run into
    a diff nobody can read. A targeted edit keeps the diff to what moved.
    """
    lines = text.split('\n')
    start = None
    for i, line in enumerate(lines):
        if re.match(rf'^(\s*)-\s+id:\s*{re.escape(block_id)}\s*$', line):
            start = i
            indent = len(line) - len(line.lstrip())
            break
    if start is None:
        return text, False

    # The block runs until the next list item at the same indent, or a dedent.
    end = len(lines)
    for j in range(start + 1, len(lines)):
        stripped = lines[j].lstrip()
        if not stripped:
            continue
        cur = len(lines[j]) - len(stripped)
        if cur <= indent and (stripped.startswith('- ') or cur < indent):
            end = j
            break

    rendered = f'{field}: {value}'
    field_indent = ' ' * (indent + 2)
    for j in range(start + 1, end):
        if re.match(rf'^\s*{re.escape(field)}:', lines[j]):
            if lines[j].strip() == rendered:
                return text, False
            lines[j] = field_indent + rendered
            return '\n'.join(lines), True

    lines.insert(end, field_indent + rendered)
    return '\n'.join(lines), True


def fmt(metric, value):
    if metric in ('gross_margin',):
        return f'{value:.4f}'
    if metric in ('hyperscaler_capex', 'purchase_obligations'):
        return f'{value:.4g}'
    return f'{value:.1f}'


# ─────────────────────────────────────────
# The check
# ─────────────────────────────────────────
# Which measured metric backs which pillar / indicator id.
BINDINGS = {
    'gross-margin': 'gross_margin',
    'hyperscaler-capex': 'hyperscaler_capex',
    'inventory-days': 'inventory_days',
    'purchase-obligations': 'purchase_obligations',
}

OPS = {'<': lambda a, b: a < b, '<=': lambda a, b: a <= b,
       '>': lambda a, b: a > b, '>=': lambda a, b: a >= b}


def check_thesis(path, dry_run=False):
    text = path.read_text()
    fm, _ = split_frontmatter(text)
    if not fm or not fm.get('ticker'):
        return None

    ticker = fm['ticker']
    print(f'\n=== {ticker} ===')
    measured = measure(ticker)
    if not measured:
        print('  no data - was fetch.py run?')
        return {'ticker': ticker, 'error': 'no data'}

    changes, fired, unevaluated = [], [], []

    # 1. Pillars and leading indicators - refresh `latest`, keep `prior`.
    for key in ('pillars', 'leading_indicators'):
        for block in fm.get(key) or []:
            metric = BINDINGS.get(block.get('id'))
            if not metric or metric not in measured:
                continue
            new = measured[metric]['value']
            old = block.get('latest')
            print(f'  {block["id"]:24} {old} -> {fmt(metric, new)}'
                  f'  (as of {measured[metric]["asof"]})')

            if old is not None and abs(new - float(old)) < MATERIAL.get(metric, 0):
                continue

            if old is not None:
                text, _ = set_field(text, block['id'], 'prior', fmt(metric, float(old)))
            text, ch = set_field(text, block['id'], 'latest', fmt(metric, new))
            text, _ = set_field(text, block['id'], 'latest_period',
                                measured[metric]['asof'])
            text, _ = set_field(text, block['id'], 'measured', str(date.today()))
            if ch:
                changes.append({'id': block['id'], 'metric': metric,
                                'old': old, 'new': new,
                                'asof': measured[metric]['asof']})

    # 2. Exit triggers.
    for trig in fm.get('exit_triggers') or []:
        metric, op, thr = trig.get('metric'), trig.get('op'), trig.get('threshold')
        if not (metric and op and thr is not None):
            unevaluated.append(trig)
            continue
        if metric not in measured:
            unevaluated.append(trig)
            print(f'  {trig["id"]:24} NOT MEASURABLE ({metric} unavailable)')
            continue
        val = measured[metric]['value']
        hit = OPS[op](val, thr)
        mark = '🔴 FIRED' if hit else 'ok'
        print(f'  {trig["id"]:24} {val:.4f} {op} {thr} -> {mark}')
        if hit:
            fired.append({**trig, 'value': val,
                          'asof': measured[metric]['asof']})

    if unevaluated:
        ids = ', '.join(t['id'] for t in unevaluated)
        print(f'  unevaluated (needs a human): {ids}')

    if (changes or fired) and not dry_run:
        text = append_log(text, changes, fired, unevaluated)
        path.write_text(text)
        print(f'  updated {path.name}')

    return {'ticker': ticker, 'changes': changes, 'fired': fired,
            'unevaluated': [t['id'] for t in unevaluated]}


def append_log(text, changes, fired, unevaluated):
    today = date.today().isoformat()
    lines = [f'\n### {today} - automated check\n']
    for f in fired:
        lines.append(f'- **{f["kind"].upper()}: {f["id"]}** - {f["rule"]}. '
                     f'Measured {f["value"]:.4f} as of {f["asof"]}.')
    for c in changes:
        old = f'{float(c["old"]):.4g}' if c['old'] is not None else 'unset'
        lines.append(f'- `{c["id"]}` {old} -> {c["new"]:.4g} '
                     f'(as of {c["asof"]})')
    if unevaluated:
        lines.append(f'- Not evaluated, needs a human: '
                     f'{", ".join(t["id"] for t in unevaluated)}.')
    lines.append('')

    marker = '## Update log'
    if marker in text:
        head, tail = text.split(marker, 1)
        # Insert directly under the heading so newest is first.
        nl = tail.index('\n')
        return head + marker + tail[:nl] + '\n' + '\n'.join(lines) + tail[nl:]
    return text + f'\n{marker}\n' + '\n'.join(lines)


# ─────────────────────────────────────────
# Notify
# ─────────────────────────────────────────
def notify(results):
    topic = os.environ.get('NTFY_TOPIC')
    if not topic:
        print('\nNTFY_TOPIC unset - no push sent')
        return

    fired = [(r['ticker'], f) for r in results for f in r.get('fired', [])]
    changed = [r for r in results if r.get('changes')]
    if not fired and not changed:
        return   # nothing moved; a weekly "nothing moved" push trains muting

    if fired:
        kinds = {f['kind'] for _, f in fired}
        priority = 5 if 'exit' in kinds else 4
        title = f'🔴 Thesis trigger: {", ".join(sorted({t for t, _ in fired}))}'
    else:
        priority = 3
        title = f'Thesis update: {", ".join(r["ticker"] for r in changed)}'

    body = []
    for ticker, f in fired:
        body.append(f'{ticker} {f["kind"].upper()} - {f["id"]}\n'
                    f'  {f["rule"]}\n'
                    f'  measured {f["value"]:.4f} as of {f["asof"]}')
    for r in changed:
        for c in r['changes']:
            old = f'{float(c["old"]):.4g}' if c['old'] is not None else 'unset'
            body.append(f'{r["ticker"]} {c["id"]}: {old} → {c["new"]:.4g}')
    body.append('\nNumbers only. The decision is yours; run preflight before acting.')

    payload = {'topic': topic, 'title': title, 'message': '\n'.join(body),
               'priority': priority, 'tags': ['chart_with_upwards_trend']}
    headers = {'Content-Type': 'application/json; charset=utf-8'}
    if os.environ.get('NTFY_TOKEN'):
        headers['Authorization'] = f'Bearer {os.environ["NTFY_TOKEN"]}'
    server = os.environ.get('NTFY_SERVER', 'https://ntfy.sh').rstrip('/')
    req = urllib.request.Request(server, data=json.dumps(payload).encode(),
                                 headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            r.read()
        print(f'\npushed (priority {priority})')
    except Exception as e:
        print(f'\nntfy push failed: {e}', file=sys.stderr)


def write_summary(results):
    """GitHub Actions job summary, so a run is legible without opening logs."""
    path = os.environ.get('GITHUB_STEP_SUMMARY')
    if not path:
        return
    out = [f'## Thesis check - {datetime.now(timezone.utc):%Y-%m-%d}\n']
    for r in results:
        out.append(f'### {r["ticker"]}')
        if r.get('error'):
            out.append(f'- {r["error"]}')
            continue
        for f in r.get('fired', []):
            out.append(f'- 🔴 **{f["kind"]}** `{f["id"]}` - {f["rule"]} '
                       f'(measured {f["value"]:.4f})')
        for c in r.get('changes', []):
            old = f'{float(c["old"]):.4g}' if c['old'] is not None else 'unset'
            out.append(f'- `{c["id"]}` {old} → {c["new"]:.4g}')
        if r.get('unevaluated'):
            out.append(f'- Needs a human: {", ".join(r["unevaluated"])}')
        if not (r.get('fired') or r.get('changes')):
            out.append('- No material change.')
        out.append('')
    with open(path, 'a') as f:
        f.write('\n'.join(out))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true',
                    help='measure and print, write nothing')
    args = ap.parse_args()

    files = sorted(p for p in THESES.glob('*.md') if p.name != 'README.md')
    if not files:
        print('no thesis files found')
        return 0

    results = [r for r in (check_thesis(p, args.dry_run) for p in files) if r]
    if not args.dry_run:
        notify(results)
        write_summary(results)

    fired = sum(len(r.get('fired', [])) for r in results)
    print(f'\n{len(results)} thesis file(s), {fired} trigger(s) fired')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
