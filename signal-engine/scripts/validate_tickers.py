#!/usr/bin/env python3
"""Check ticker symbols against SEC's registrant list before acting on them.

Written to be copied into another repo as-is: standard library only, no
imports from anything else here.

WHY THIS EXISTS

An LLM asked to name "companies that benefit from <trend>" will sometimes
invent a plausible-looking symbol, and a digest that pushes it straight to a
phone gives a hallucination the same standing as a real holding. The failure
is worst exactly where a social-arbitrage system is most useful: an LLM
fact-checking from training data misses recent listings, so the newest
spin-offs, SPACs and IPOs -- the ones worth finding early -- are the ones it
most often calls fake.

SEC publishes the authoritative list free at
https://www.sec.gov/files/company_tickers.json.

WHAT THIS TEST CAN AND CANNOT DO

It is one-way. A symbol present in the file is a real registrant. A symbol
absent from it is *unconfirmed*, not fake -- the file covers operating
companies and some ETF trusts, so QQQ and SPY appear while SMH, BOTZ, AIQ and
UFO do not, and nothing listed outside the US (ASX, TWSE) appears at all.
Dual-class symbols also differ from their common form: Moog trades as MOG.A
and MOG.B, so a bare "MOG" will not resolve.

So: flag the unconfirmed, never silently drop them. Suppressing them would
throw away every ETF and every Taiwan-listed name in a watchlist.
"""
import json
import os
import time
import urllib.request

SEC_TICKERS_URL = 'https://www.sec.gov/files/company_tickers.json'
CACHE_PATH = os.environ.get('SEC_TICKER_CACHE', '/tmp/sec_company_tickers.json')
CACHE_TTL_SECONDS = 7 * 24 * 3600

# SEC rejects requests without a descriptive User-Agent, and rejects ones that
# look like a bare scripting client, with a 403 before any data is returned.
USER_AGENT = os.environ.get(
    'SEC_USER_AGENT', 'social-signal-engine (contact: set SEC_USER_AGENT)')

_cache = None


def _download(path):
    req = urllib.request.Request(SEC_TICKERS_URL,
                                 headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    with open(path, 'wb') as f:
        f.write(data)
    return json.loads(data)


def load_registry(force_refresh=False):
    """{TICKER: {'name': ..., 'cik': ...}} for every SEC registrant."""
    global _cache
    if _cache is not None and not force_refresh:
        return _cache

    raw = None
    fresh = (os.path.exists(CACHE_PATH)
             and time.time() - os.path.getmtime(CACHE_PATH) < CACHE_TTL_SECONDS)
    if fresh and not force_refresh:
        try:
            raw = json.load(open(CACHE_PATH))
        except (json.JSONDecodeError, OSError):
            raw = None
    if raw is None:
        try:
            raw = _download(CACHE_PATH)
        except Exception:
            # A stale cache beats failing shut: without it every symbol would
            # come back unconfirmed and the whole digest would look broken.
            if os.path.exists(CACHE_PATH):
                raw = json.load(open(CACHE_PATH))
            else:
                raise

    _cache = {v['ticker'].upper(): {'name': v['title'],
                                    'cik': str(v['cik_str']).zfill(10)}
              for v in raw.values()}
    return _cache


def validate(tickers):
    """Resolve each symbol. status is 'verified' or 'unconfirmed'."""
    reg = load_registry()
    out = {}
    for t in tickers:
        key = (t or '').strip().upper()
        hit = reg.get(key)
        if hit:
            out[t] = {'status': 'verified', 'name': hit['name'],
                      'cik': hit['cik']}
        else:
            out[t] = {'status': 'unconfirmed', 'name': None, 'cik': None}
    return out


def annotate(tickers, marker=' ⚠️'):
    """Ticker strings for display, unconfirmed ones marked.

    Order is preserved and nothing is dropped - an ETF or a Taiwan-listed name
    is legitimately absent from SEC's list and must still reach the reader.
    """
    res = validate(tickers)
    return [t if res[t]['status'] == 'verified' else f'{t}{marker}'
            for t in tickers]


def split(tickers):
    """(verified, unconfirmed) - for callers that want to rank, not just mark."""
    res = validate(tickers)
    v = [t for t in tickers if res[t]['status'] == 'verified']
    u = [t for t in tickers if res[t]['status'] != 'verified']
    return v, u


if __name__ == '__main__':
    import sys
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        print('usage: validate_tickers.py NVDA INFQ SMH ...')
        sys.exit(0)
    reg = load_registry()
    print(f'SEC registrants: {len(reg):,}\n')
    for t, r in validate(args).items():
        if r['status'] == 'verified':
            print(f'  {t:8} verified     CIK {r["cik"]}  {r["name"]}')
        else:
            print(f'  {t:8} unconfirmed  not an SEC registrant under this '
                  f'symbol - may be an ETF, a non-US listing, or dual-class')
