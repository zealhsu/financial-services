#!/usr/bin/env python3
"""Download SEC companyfacts for a ticker set.

The other scripts here read `cf_<TICKER>.json` from the working directory and
nothing in the repo produced them - they were fetched by hand. That is fine
interactively and useless on a schedule, so this is the missing step.

SEC requires a descriptive User-Agent naming a real contact, and returns 403
without one. Set SEC_USER_AGENT; there is no default, because a wrong one gets
the whole IP blocked rather than just failing this run.

  python3 fetch.py                 # the default set
  python3 fetch.py NVDA MSFT       # specific tickers
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

TICKER_MAP_URL = 'https://www.sec.gov/files/company_tickers.json'
FACTS_URL = 'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json'

# NVDA and its peer set, plus the four hyperscalers pillar 1 is measured from.
DEFAULT_TICKERS = ['NVDA', 'AMD', 'AVGO', 'MRVL', 'INTC', 'ARM',
                   'MSFT', 'GOOGL', 'AMZN', 'META']

# SEC asks for no more than 10 requests/second. This is far under that; the
# limit that actually bites is being rude, not being fast.
DELAY_SECONDS = 0.5


def user_agent():
    ua = os.environ.get('SEC_USER_AGENT')
    if not ua:
        sys.exit('SEC_USER_AGENT is not set. SEC returns 403 without a '
                 'descriptive User-Agent naming a real contact, e.g.\n'
                 '  export SEC_USER_AGENT="Thesis Tracker you@example.com"')
    return ua


def get(url, ua):
    req = urllib.request.Request(url, headers={
        'User-Agent': ua, 'Accept-Encoding': 'gzip, deflate'})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
        if r.headers.get('Content-Encoding') == 'gzip':
            import gzip
            raw = gzip.decompress(raw)
    return json.loads(raw)


def cik_map(ua):
    raw = get(TICKER_MAP_URL, ua)
    return {v['ticker'].upper(): str(v['cik_str']).zfill(10)
            for v in raw.values()}


def main(tickers):
    ua = user_agent()
    ciks = cik_map(ua)
    missing, failed, ok = [], [], []

    for t in tickers:
        cik = ciks.get(t.upper())
        if not cik:
            # Not an SEC registrant under this symbol - an ETF or a foreign
            # listing. Report it; do not pretend the fetch succeeded.
            missing.append(t)
            print(f'{t:6} not in SEC ticker file')
            continue
        try:
            facts = get(FACTS_URL.format(cik=cik), ua)
        except urllib.error.HTTPError as e:
            failed.append(t)
            print(f'{t:6} HTTP {e.code}')
            continue
        except (urllib.error.URLError, OSError) as e:
            failed.append(t)
            print(f'{t:6} {e}')
            continue
        path = f'cf_{t.upper()}.json'
        with open(path, 'w') as f:
            json.dump(facts, f)
        ok.append(t)
        n = len(facts.get('facts', {}).get('us-gaap', {}))
        print(f'{t:6} CIK {cik}  {n} us-gaap concepts  -> {path}')
        time.sleep(DELAY_SECONDS)

    if missing:
        print(f'\nnot found: {", ".join(missing)}')
    if failed:
        print(f'failed: {", ".join(failed)}')

    # One peer timing out must not cancel the week's check - the downstream
    # script degrades per metric and reports what it could not measure. Only a
    # total failure is worth failing the job over, because then there is
    # nothing to measure and a green run would be a lie.
    if not ok:
        print('nothing fetched')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:] or DEFAULT_TICKERS))
