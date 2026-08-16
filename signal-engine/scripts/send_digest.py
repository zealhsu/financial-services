"""
send_digest.py
Social Signal Engine — Layer 1 推送 agent（最後一塊）

在 generate_analysis.py / backfill_outcomes.py 跑完後執行。
把今天分析好的訊號，去重後推成一則精簡的 ntfy 通知。

設計原則：
- 最多 5 個訊號，超過就是噪音
- 推過的關鍵字進入冷卻期，除非它升級了（見下方去重規則）
- watchlist 命中標 ⚡
- 每個訊號 = 一句摘要 + 潛在標的 + 階段 + 出場訊號
- 沒有訊號時仍然推一則，但用低優先度，不震動

為什麼是 ntfy 不是 Telegram：
  ntfy 不用註冊帳號、不用 bot token、沒有「bot 不能主動開對話、
  人類必須先傳訊息給它」那條規則（那是 Telegram 最常卡住的一步）。
  代價是 topic 名稱等於密碼——取一個猜不到的。

環境變數（GitHub Secrets）：
  SUPABASE_URL / SUPABASE_KEY
  NTFY_TOPIC     ← 你自己取的 topic 名稱，等同密碼
  NTFY_SERVER    ← 選用，自架時才需要，預設 https://ntfy.sh
  NTFY_TOKEN     ← 選用，topic 有設存取控制時才需要
"""

import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from supabase import Client, create_client

from validate_tickers import annotate

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

TOP_N = 5
CANDIDATE_POOL = 25       # 多撈一些，去重刷掉之後才補得滿 5 個

# 去重：推過的關鍵字冷卻幾天
COOLDOWN_DAYS = 7
# 冷卻期內要「升級」到什麼程度才破例再推
ESCALATION_GAP_RATIO = 1.5   # info_gap 比上次推的時候高 50% 以上

STAGE_ZH = {
    "emerging":        "🌱 萌芽期（資訊差最大）",
    "growing":         "📈 成長期",
    "near_mainstream": "⚠️ 接近主流（快出場）",
}
STAGE_RANK = {"emerging": 0, "growing": 1, "near_mainstream": 2}

# ntfy.sh 單則訊息上限 4096 bytes，留一點餘裕。
MAX_BYTES = 3800


def init_supabase() -> Client:
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


# ─────────────────────────────────────────
# 取今日已分析的候選訊號
# ─────────────────────────────────────────
def get_analyzed_signals(sb: Client, n: int = CANDIDATE_POOL) -> list[dict]:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = (
        sb.table("signals")
        .select("*, keywords(keyword, language, region)")
        .gte("created_at", f"{today}T00:00:00Z")
        .not_.is_("claude_analysis", "null")
        .order("info_gap_score", desc=True)
        .limit(n)
        .execute()
    ).data
    return rows


# ─────────────────────────────────────────
# 去重
# ─────────────────────────────────────────
def load_push_history(sb: Client, days: int = COOLDOWN_DAYS) -> dict[str, dict]:
    """{keyword_id: 最近一次推送的紀錄}。冷卻窗內的才撈。"""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = (
        sb.table("digest_log")
        .select("keyword_id, info_gap_score, stage, pushed_at")
        .gte("pushed_at", since)
        .order("pushed_at", desc=True)
        .execute()
    ).data

    latest: dict[str, dict] = {}
    for r in rows:                      # 已按時間倒序，第一筆就是最近的
        latest.setdefault(r["keyword_id"], r)
    return latest


def should_push(sig: dict, last: dict | None) -> tuple[bool, str]:
    """(要不要推, 理由)。

    純粹的「推過就不再推」會在訊號真正重要的那一刻閉嘴——一個關鍵字
    從 emerging 走到 near_mainstream，那是出場訊號，正是最需要看到的
    時候。所以是冷卻期 + 升級破例，不是永久靜音。
    """
    if last is None:
        return True, "new"

    prev_stage = STAGE_RANK.get(last.get("stage") or "", -1)
    curr_stage = STAGE_RANK.get(
        (sig.get("claude_analysis") or {}).get("stage") or "", -1)
    if curr_stage > prev_stage >= 0:
        return True, f"stage {last.get('stage')} → {(sig['claude_analysis'] or {}).get('stage')}"

    prev_gap = last.get("info_gap_score") or 0
    curr_gap = sig.get("info_gap_score") or 0
    if prev_gap > 0 and curr_gap >= prev_gap * ESCALATION_GAP_RATIO:
        return True, f"info_gap {prev_gap:.0f} → {curr_gap:.0f}"

    days_ago = ""
    if last.get("pushed_at"):
        try:
            then = datetime.fromisoformat(last["pushed_at"].replace("Z", "+00:00"))
            days_ago = f"，{(datetime.now(timezone.utc) - then).days} 天前推過"
        except ValueError:
            pass
    return False, f"冷卻中{days_ago}"


def dedupe(signals: list[dict], history: dict[str, dict],
           n: int = TOP_N) -> tuple[list[dict], int]:
    """回傳 (要推的訊號, 被冷卻擋掉的數量)。"""
    keep, suppressed = [], 0
    for sig in signals:
        ok, why = should_push(sig, history.get(sig.get("keyword_id")))
        kw = (sig.get("keywords") or {}).get("keyword", "?")
        if ok:
            if len(keep) < n:
                log.info(f"  推送 {kw}（{why}）")
                keep.append(sig)
        else:
            suppressed += 1
            log.info(f"  略過 {kw}（{why}）")
    return keep, suppressed


def record_pushes(sb: Client, signals: list[dict]) -> None:
    """推送成功後才寫。失敗就寫的話，明天會把今天沒送到的訊號靜音掉。"""
    if not signals:
        return
    rows = [{
        "keyword_id":     s.get("keyword_id"),
        "signal_id":      s.get("id"),
        "info_gap_score": s.get("info_gap_score"),
        "stage":          (s.get("claude_analysis") or {}).get("stage"),
        "pushed_at":      datetime.now(timezone.utc).isoformat(),
    } for s in signals]
    try:
        sb.table("digest_log").insert(rows).execute()
    except Exception as e:
        # 這裡失敗只會讓明天重推一次，不值得讓整個 workflow 紅掉。
        log.error(f"digest_log 寫入失敗（明天可能重推）：{e}")


# ─────────────────────────────────────────
# Ticker 驗證（防幻覺）
# ─────────────────────────────────────────
def mark_unverified(tickers: list[str]) -> list[str]:
    """對照 SEC 註冊清單標注查不到的 ticker。

    驗證失敗（SEC 連不上且無快取）時原樣回傳——寧可少一個標記，
    也不要因為驗證器掛掉就整份 digest 推不出去。
    """
    if not tickers:
        return tickers
    try:
        return annotate(tickers)
    except Exception as e:
        log.warning(f"ticker 驗證跳過：{e}")
        return tickers


# ─────────────────────────────────────────
# 組裝訊息（純文字——ntfy 各家 client 的 markdown 支援不一致）
# ─────────────────────────────────────────
def build_message(signals: list[dict], suppressed: int = 0) -> str:
    if not signals:
        body = ["今天沒有新的高分訊號。"]
        if suppressed:
            body.append(f"（{suppressed} 個仍在冷卻期，代表趨勢還在但沒有新進展）")
        else:
            body.append("（velocity < 20% 或無有效分析）")
        body.append("")
        body.append("沒有訊號也是一種訊號——市場平靜，不必勉強動作。")
        return "\n".join(body)

    blocks = []
    for i, sig in enumerate(signals, 1):
        kw       = (sig.get("keywords") or {}).get("keyword", "?")
        analysis = sig.get("claude_analysis") or {}
        velocity = sig.get("velocity_score", 0)
        info_gap = sig.get("info_gap_score", 0)
        stage    = STAGE_ZH.get(analysis.get("stage", ""), analysis.get("stage", "?"))
        summary  = analysis.get("summary", "")
        exit_sig = analysis.get("exit_trigger", "")
        hits     = analysis.get("watchlist_hits", [])

        # 潛在標的（優先顯示供應鏈受益者，那才是資訊差價值）。
        # 這些 ticker 是 Claude 生成的，可能是幻覺。對照 SEC 註冊清單，
        # 查不到的標 ⚠️——不刪除（ETF 和台股本來就不在那份清單裡）。
        tickers = mark_unverified(sig.get("potential_tickers", []) or [])
        ticker_str = "、".join(tickers[:5]) if tickers else "（無明確標的）"

        block = [f"{i}. {kw}",
                 f"   速度 +{velocity:.0f}%｜資訊差 {info_gap:.0f}/100",
                 f"   {stage}"]
        if summary:
            block.append(f"   💡 {summary}")
        block.append(f"   🎯 {ticker_str}")
        if hits:
            block.append(f"   ⚡ Watchlist 命中：{'、'.join(hits)}")
        if exit_sig:
            block.append(f"   🚪 出場：{exit_sig}")
        blocks.append("\n".join(block))

    footer = [f"共 {len(signals)} 個訊號。這是研究參考，不是進場指令。"]
    if suppressed:
        footer.append(f"另有 {suppressed} 個在冷卻期未推。")
    footer.append("⚠️ = 不在 SEC 註冊清單（可能是幻覺，也可能是 ETF／台股／新上市）。")

    return _fit("\n\n".join(blocks) + "\n\n" + "\n".join(footer), blocks, footer)


def _fit(text: str, blocks: list[str], footer: list[str]) -> str:
    """超過 ntfy 上限就從最後一個訊號開始砍，而不是攔腰截斷。

    截在一半的訊號比少一個訊號更糟——讀的人不知道自己看到的是完整的還是
    被切掉的，而排在後面的本來就是資訊差較低的那些。
    """
    if len(text.encode()) <= MAX_BYTES:
        return text
    kept = list(blocks)
    while kept:
        dropped = len(blocks) - len(kept)
        tail = footer + [f"（另有 {dropped} 個訊號因長度未列出）"]
        candidate = "\n\n".join(kept) + "\n\n" + "\n".join(tail)
        if len(candidate.encode()) <= MAX_BYTES:
            return candidate
        kept.pop()
    return "訊號內容過長，無法組成通知。請直接查 Supabase signals 表。"


def build_title(signals: list[dict]) -> str:
    date_str = datetime.now(timezone.utc).strftime("%m-%d")
    if not signals:
        return f"社交訊號 {date_str}｜今日無新訊號"
    hits = sum(1 for s in signals
               if (s.get("claude_analysis") or {}).get("watchlist_hits"))
    if hits:
        return f"⚡ 社交訊號 {date_str}｜{len(signals)} 則，{hits} 個 watchlist 命中"
    return f"社交訊號 {date_str}｜{len(signals)} 則"


def build_priority(signals: list[dict]) -> int:
    """1=min 3=default 5=max。

    沒訊號的日子用 2（進通知欄但不震動）——每天都響的通知會被關掉，
    而被關掉的通知等於沒有這個系統。
    """
    if not signals:
        return 2
    for s in signals:
        analysis = s.get("claude_analysis") or {}
        if analysis.get("watchlist_hits"):
            return 5
        if analysis.get("stage") == "near_mainstream":
            return 4     # 出場訊號，值得吵一下
    return 3


# ─────────────────────────────────────────
# 推送到 ntfy
# ─────────────────────────────────────────
def send_ntfy(title: str, message: str, priority: int = 3,
              tags: list[str] | None = None) -> bool:
    """用 JSON body 發布，不用 header 帶欄位。

    ntfy 的 X-Title 走 HTTP header，而 header 只保證 ASCII——中文標題
    塞進去會變亂碼。JSON body 是 UTF-8，沒有這個問題。
    """
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        log.error("NTFY_TOPIC 未設定，無法推送")
        return False

    # `or`, not a get() default: 未設定的 GitHub secret 會以空字串送進來，
    # 不是「這個 key 不存在」，所以 default 永遠不會生效。
    server = (os.environ.get("NTFY_SERVER") or "https://ntfy.sh").rstrip("/")
    payload = {
        "topic":    topic,
        "title":    title,
        "message":  message,
        "priority": priority,
        "tags":     tags or ["satellite"],
    }
    headers = {"Content-Type": "application/json; charset=utf-8"}
    token = os.environ.get("NTFY_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(
        server, data=json.dumps(payload).encode("utf-8"),
        headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            r.read()
        log.info(f"✅ ntfy 推送成功（priority={priority}）")
        return True
    except urllib.error.HTTPError as e:
        log.error(f"ntfy 推送失敗 HTTP {e.code}：{e.read().decode('utf-8', 'replace')[:200]}")
        return False
    except Exception as e:
        log.error(f"ntfy 推送失敗：{e}")
        return False


def main() -> int:
    log.info("=== 推送 agent 開始 ===")
    sb = init_supabase()

    candidates = get_analyzed_signals(sb)
    log.info(f"今日候選訊號：{len(candidates)} 個")

    history = load_push_history(sb)
    log.info(f"冷卻窗（{COOLDOWN_DAYS} 天）內推過的關鍵字：{len(history)} 個")

    signals, suppressed = dedupe(candidates, history)
    log.info(f"待推送 {len(signals)} 個，冷卻擋掉 {suppressed} 個")

    ok = send_ntfy(
        build_title(signals),
        build_message(signals, suppressed),
        build_priority(signals),
        tags=["zap"] if any((s.get("claude_analysis") or {}).get("watchlist_hits")
                            for s in signals) else ["satellite"],
    )
    if ok:
        record_pushes(sb, signals)

    log.info("=== 推送完成 ===")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
