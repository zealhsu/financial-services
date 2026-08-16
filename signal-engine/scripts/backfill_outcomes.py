"""
backfill_outcomes.py
Social Signal Engine — 校準期的量尺

schema.sql 建了 signal_outcomes 表，但沒有任何程式寫它。
結果是：8 週校準期跑完，命中率是空的，「準確率 > 40% 才擴充關鍵字池」
這條規則永遠不會有數字可以判斷。這支腳本就是補上那件事。

做兩件事，都是冪等的（每天重跑不會重複、不會覆寫已填的欄位）：

1. 新訊號 → 建 outcome 列，記下訊號當日收盤價
2. 舊訊號 → 時間到了就補 1 週 / 4 週 / 12 週的價格，4 週那格填好時判定 hit

判定：4 週漲幅 > HIT_THRESHOLD（預設 10%）= 命中。
門檻寫在這裡而不是散在查詢裡，因為改門檻等於改整個校準結論，
必須是一個看得見、要動手改的數字。

用法：
  python scripts/backfill_outcomes.py            # 回填
  python scripts/backfill_outcomes.py --report   # 只印命中率，不寫入

環境變數：SUPABASE_URL / SUPABASE_KEY
"""

import logging
import os
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone

from supabase import Client, create_client

from prices import close_on_or_before, fetch_series

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

HIT_THRESHOLD = 0.10          # 4 週漲幅超過這個 = 命中
HORIZONS = {                  # 欄位名 → 訊號後幾天
    "price_1w": 7,
    "price_4w": 28,
    "price_12w": 84,
}
PRIMARY_HORIZON = "price_4w"  # 判定 hit 用哪一格
MAX_SIGNAL_AGE_DAYS = 120     # 超過 12 週 + 緩衝就不再看，該填的都填完了


# ─────────────────────────────────────────
# 初始化
# ─────────────────────────────────────────
def init_supabase() -> Client:
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


# ─────────────────────────────────────────
# 取需要追蹤的訊號
# ─────────────────────────────────────────
def get_trackable_signals(sb: Client) -> list[dict]:
    """有分析過、有標的、且還在 12 週追蹤窗內的訊號。"""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=MAX_SIGNAL_AGE_DAYS))
    rows = (
        sb.table("signals")
        .select("id, created_at, potential_tickers, claude_analysis,"
                " keywords(keyword)")
        .gte("created_at", cutoff.isoformat())
        .not_.is_("potential_tickers", "null")
        .order("created_at", desc=True)
        .execute()
    ).data
    return [r for r in rows if r.get("potential_tickers")]


def get_existing_outcomes(sb: Client, signal_ids: list[str]) -> dict[tuple, dict]:
    """{(signal_id, ticker): row}，一次撈完，避免每個標的一次查詢。"""
    if not signal_ids:
        return {}
    out: dict[tuple, dict] = {}
    # Supabase 的 in_ 對超長清單會爆 URL 長度，分批。
    for i in range(0, len(signal_ids), 50):
        rows = (
            sb.table("signal_outcomes")
            .select("*")
            .in_("signal_id", signal_ids[i:i + 50])
            .execute()
        ).data
        for r in rows:
            out[(r["signal_id"], r["ticker"])] = r
    return out


# ─────────────────────────────────────────
# 交易所推斷（給非美股用）
# ─────────────────────────────────────────
def exchange_for(analysis: dict | None, ticker: str) -> str | None:
    """從 claude_analysis 裡找這個 ticker 標注的交易所。

    只有 direct_beneficiaries 帶 exchange 欄位；supply_chain 那組沒有，
    找不到就回 None，prices.py 會當成美股處理——這對這個引擎產出的
    絕大多數標的是對的。
    """
    for b in (analysis or {}).get("direct_beneficiaries", []) or []:
        if (b.get("ticker") or "").upper() == ticker.upper():
            return b.get("exchange")
    return None


# ─────────────────────────────────────────
# 單一 (訊號, 標的) 的回填
# ─────────────────────────────────────────
def build_row(signal: dict, ticker: str, existing: dict | None,
              today: date) -> dict | None:
    """回傳要 upsert 的列；沒有任何新東西可寫就回 None。"""
    signal_date = datetime.fromisoformat(
        signal["created_at"].replace("Z", "+00:00")).date()

    # 還缺哪幾格？已經填好的不重算——價格是歷史事實，不會變，
    # 重抓只是多打 API，還可能被 Stooq 限流。
    wanted = {
        col: signal_date + timedelta(days=days)
        for col, days in HORIZONS.items()
        if (existing or {}).get(col) is None and signal_date + timedelta(days=days) <= today
    }
    need_entry = (existing or {}).get("price_at_signal") is None
    if not wanted and not need_entry:
        return None

    exch = exchange_for(signal.get("claude_analysis"), ticker)
    # 一次抓完整區間，三個時點從同一份序列取，一個標的一天只打一次。
    series = fetch_series(ticker, signal_date - timedelta(days=10), today, exch)
    if not series:
        log.warning(f"  {ticker}: 查無價格（symbol 無法解析或資料源失敗）")
        if existing:
            return None
        return {
            "signal_id": signal["id"],
            "ticker": ticker.upper(),
            "note": "unresolved: no price series",
        }

    row = {"signal_id": signal["id"], "ticker": ticker.upper()}

    entry = (existing or {}).get("price_at_signal")
    if entry is None:
        entry = close_on_or_before(series, signal_date)
        if entry is None:
            log.warning(f"  {ticker}: 訊號日無收盤價，跳過")
            return None
        row["price_at_signal"] = entry
        row["note"] = f"stooq; entry {signal_date.isoformat()}"

    for col, target in wanted.items():
        px = close_on_or_before(series, target)
        if px is not None:
            row[col] = px

    # hit 只在主要評估點（4 週）填好的那一刻判定一次。
    if PRIMARY_HORIZON in row and entry:
        row["hit"] = (row[PRIMARY_HORIZON] / entry - 1) > HIT_THRESHOLD

    if len(row) <= 2:          # 只有 signal_id + ticker，沒有新資料
        return None
    return row


# ─────────────────────────────────────────
# 命中率報告
# ─────────────────────────────────────────
def report(sb: Client) -> None:
    rows = sb.table("signal_outcomes").select("*").execute().data
    judged = [r for r in rows if r.get("hit") is not None]
    pending = [r for r in rows
               if r.get("hit") is None and r.get("price_at_signal") is not None]
    unresolved = [r for r in rows if r.get("price_at_signal") is None]

    log.info("=" * 52)
    log.info("校準期進度")
    log.info(f"  已判定      {len(judged):>4} 筆")
    log.info(f"  追蹤中      {len(pending):>4} 筆（未滿 4 週）")
    log.info(f"  無法解析    {len(unresolved):>4} 筆（symbol 查不到價格）")

    if not judged:
        log.info("  尚無命中率——第一個訊號滿 4 週後才會有數字。")
        log.info("=" * 52)
        return

    hits = sum(1 for r in judged if r["hit"])
    rate = hits / len(judged)
    log.info(f"  命中率      {rate:.1%}  ({hits}/{len(judged)})"
             f"  門檻 4 週 > {HIT_THRESHOLD:.0%}")

    verdict = ("達標——可以考慮擴充關鍵字池" if rate > 0.40
               else "未達 40%——先別擴充關鍵字池，也先別拿真錢進場")
    log.info(f"  判定        {verdict}")

    top = Counter(r["ticker"] for r in judged if r["hit"]).most_common(5)
    if top:
        log.info(f"  最常命中    {', '.join(f'{t}×{n}' for t, n in top)}")

    # 樣本數太小的時候，命中率這個數字本身沒有意義，要講出來。
    if len(judged) < 20:
        log.info(f"  ⚠️ 樣本只有 {len(judged)} 筆，這個比率還不能當結論。")
    log.info("=" * 52)


# ─────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────
def main() -> int:
    if "--report" in sys.argv:
        report(init_supabase())
        return 0

    log.info("=== outcome 回填開始 ===")
    sb = init_supabase()
    today = datetime.now(timezone.utc).date()

    signals = get_trackable_signals(sb)
    log.info(f"追蹤窗內訊號：{len(signals)} 個")
    if not signals:
        log.info("沒有可追蹤的訊號，結束。")
        return 0

    existing = get_existing_outcomes(sb, [s["id"] for s in signals])
    log.info(f"已有 outcome 列：{len(existing)} 筆")

    pending: list[dict] = []
    for sig in signals:
        kw = (sig.get("keywords") or {}).get("keyword", "?")
        for ticker in sig.get("potential_tickers") or []:
            row = build_row(sig, ticker,
                            existing.get((sig["id"], ticker.upper())), today)
            if row:
                pending.append(row)
                filled = [k for k in row if k.startswith("price_") or k == "hit"]
                log.info(f"  {kw} / {ticker}: {', '.join(filled) or 'unresolved'}")

    if not pending:
        log.info("沒有新的價格要寫入。")
        report(sb)
        return 0

    # 依欄位組合分組後才 upsert。PostgREST 會把一個批次裡的所有列
    # 對齊成同一組欄位，缺的補 NULL——把「這次只補 price_12w」的列和
    # 「這次要寫 price_at_signal」的列混在一起送，會把已經填好的
    # price_at_signal 洗成 NULL。一批只送欄位完全相同的列就沒這問題。
    #
    # 這裡刻意不吞例外——寫入失敗必須讓 workflow 紅掉，否則校準資料會
    # 靜靜地少掉幾天，而那正是這支腳本要修的病。
    groups: dict[frozenset, list[dict]] = {}
    for row in pending:
        groups.setdefault(frozenset(row), []).append(row)

    for batch in groups.values():
        for i in range(0, len(batch), 100):
            sb.table("signal_outcomes").upsert(
                batch[i:i + 100], on_conflict="signal_id,ticker").execute()
    log.info(f"✅ 寫入 {len(pending)} 筆（{len(groups)} 個欄位組合）")

    report(sb)
    log.info("=== 回填完成 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
