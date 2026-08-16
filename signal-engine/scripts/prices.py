"""Daily closing prices, free and without an API key.

WHY NOT yfinance

yfinance scrapes an endpoint Yahoo does not document and periodically changes.
It breaks without warning, and a calibration record that silently stops being
written is worse than one that was never started. Stooq publishes a plain CSV
endpoint that has been stable for years and needs no key and no dependency, so
it is the primary source here. yfinance is used only as a fallback, and only if
it happens to be installed.

WHAT RESOLVES AND WHAT DOES NOT

Stooq suffixes a symbol by market: `nvda.us`, `2313.tw`, `bhp.au`. US coverage
is complete for the names this engine produces. Non-US coverage is patchier, and
an unresolvable symbol must be recorded as unresolvable rather than guessed at -
a fabricated price would poison the hit rate the calibration period exists to
measure.
"""
import csv
import io
import logging
import urllib.error
import urllib.request
from datetime import date, timedelta

log = logging.getLogger(__name__)

STOOQ_URL = "https://stooq.com/q/d/l/"

# Exchange codes as they appear in `signals.claude_analysis`, mapped to Stooq's
# market suffix. Anything not listed falls back to `.us`, which is right for the
# overwhelming majority of what the analysis step returns.
EXCHANGE_SUFFIX = {
    "NYSE": "us",
    "NASDAQ": "us",
    "AMEX": "us",
    "TSE": "tw",     # Taiwan Stock Exchange
    "TWO": "tw",     # Taipei Exchange
    "ASX": "au",
}

_series_cache: dict[tuple[str, str], dict[date, float]] = {}


def stooq_symbol(ticker: str, exchange: str | None = None) -> str:
    suffix = EXCHANGE_SUFFIX.get((exchange or "").upper(), "us")
    return f"{ticker.strip().lower()}.{suffix}"


def fetch_series(ticker: str, start: date, end: date,
                 exchange: str | None = None) -> dict[date, float]:
    """{date: close} over [start, end]. Empty dict if the symbol does not resolve.

    Trading days only - the caller must not assume every calendar date is a key.
    """
    sym = stooq_symbol(ticker, exchange)
    key = (sym, f"{start}:{end}")
    if key in _series_cache:
        return _series_cache[key]

    url = (f"{STOOQ_URL}?s={sym}&d1={start:%Y%m%d}&d2={end:%Y%m%d}&i=d")
    series: dict[date, float] = {}
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "social-signal-engine/2.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode("utf-8", "replace")

        # Stooq answers a bad symbol with a 200 and the body "No data",
        # and a rate limit with "Exceeded the daily hits limit". Neither is
        # an HTTP error, so both have to be detected by reading the body.
        head = body[:80].strip().lower()
        if head.startswith("no data") or "exceeded" in head:
            log.warning(f"Stooq 無資料/被限流 [{sym}]: {body[:60].strip()}")
            return _fallback(ticker, start, end, series)

        for row in csv.DictReader(io.StringIO(body)):
            try:
                series[date.fromisoformat(row["Date"])] = float(row["Close"])
            except (KeyError, ValueError):
                continue

    except (urllib.error.URLError, OSError) as e:
        log.warning(f"Stooq 連線失敗 [{sym}]: {e}")
        return _fallback(ticker, start, end, series)

    if not series:
        return _fallback(ticker, start, end, series)

    _series_cache[key] = series
    return series


def _fallback(ticker: str, start: date, end: date,
              series: dict[date, float]) -> dict[date, float]:
    """yfinance, only if the environment happens to have it."""
    try:
        import yfinance  # noqa: F401
    except ImportError:
        return series
    try:
        import yfinance as yf
        df = yf.Ticker(ticker).history(
            start=start.isoformat(), end=(end + timedelta(days=1)).isoformat())
        if df is None or df.empty:
            return series
        for ts, close in df["Close"].items():
            series[ts.date()] = float(close)
        log.info(f"yfinance 回補 [{ticker}] {len(series)} 筆")
    except Exception as e:
        log.warning(f"yfinance 也失敗 [{ticker}]: {e}")
    return series


def close_on_or_before(series: dict[date, float], target: date,
                       lookback_days: int = 10) -> float | None:
    """Last close at or before `target`.

    Weekends, public holidays and trading halts all mean the exact date may not
    be a trading day. Ten days back covers a long weekend plus a holiday week;
    beyond that the symbol is better treated as having no price than as having a
    stale one.
    """
    for i in range(lookback_days + 1):
        hit = series.get(target - timedelta(days=i))
        if hit is not None:
            return hit
    return None
