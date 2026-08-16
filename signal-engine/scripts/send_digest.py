"""
send_digest.py
Social Signal Engine — Layer 1 推送 agent（最後一塊）

在 generate_analysis.py 跑完後執行（GitHub Actions 排最後，或每日早上 8 點）。
把今天分析好的前 5 個訊號，推成一則精簡的 Telegram 訊息。

設計原則：
- 最多 5 個訊號，超過就是噪音
- watchlist 命中標 ⚡
- 每個訊號 = 一句摘要 + 潛在標的 + 階段 + 出場訊號
- 沒有訊號時，推一則「今日無高分訊號」也是有價值的資訊

環境變數（GitHub Secrets）：
  SUPABASE_URL / SUPABASE_KEY
  TELEGRAM_BOT_TOKEN   ← 跟 @BotFather 拿
  TELEGRAM_CHAT_ID     ← 你的 chat id（跟 @userinfobot 拿）
"""

import os
import logging
from datetime import datetime, timezone

import requests
from supabase import create_client, Client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

TOP_N = 5
STAGE_ZH = {
    "emerging":        "🌱 萌芽期（資訊差最大）",
    "growing":         "📈 成長期",
    "near_mainstream": "⚠️ 接近主流（快出場）",
}


def init_supabase() -> Client:
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


# ─────────────────────────────────────────
# 取今日已分析的前 N 名訊號
# ─────────────────────────────────────────
def get_analyzed_signals(sb: Client, n: int = TOP_N) -> list[dict]:
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
# 組裝 Telegram 訊息（HTML 格式）
# ─────────────────────────────────────────
def build_message(signals: list[dict]) -> str:
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if not signals:
        return (f"📡 <b>今日社交訊號摘要</b>｜{date_str}\n\n"
                f"今天沒有達到門檻的高分訊號。\n"
                f"（velocity &lt; 20% 或無有效分析）\n\n"
                f"沒有訊號也是一種訊號——市場平靜，不必勉強動作。")

    lines = [f"📡 <b>今日社交訊號摘要</b>｜{date_str}\n"]

    for i, sig in enumerate(signals, 1):
        kw       = (sig.get("keywords") or {}).get("keyword", "?")
        analysis = sig.get("claude_analysis") or {}
        velocity = sig.get("velocity_score", 0)
        info_gap = sig.get("info_gap_score", 0)
        stage    = STAGE_ZH.get(analysis.get("stage", ""), analysis.get("stage", "?"))
        summary  = analysis.get("summary", "")
        exit_sig = analysis.get("exit_trigger", "")
        hits     = analysis.get("watchlist_hits", [])

        # 潛在標的（優先顯示供應鏈受益者，那才是資訊差價值）
        tickers = sig.get("potential_tickers", []) or []
        ticker_str = "、".join(tickers[:5]) if tickers else "（無明確標的）"

        block = [f"\n<b>{i}. {kw}</b>"]
        block.append(f"　速度 +{velocity:.0f}%｜資訊差 {info_gap:.0f}/100")
        block.append(f"　{stage}")
        if summary:
            block.append(f"　💡 {summary}")
        block.append(f"　🎯 {ticker_str}")
        if hits:
            block.append(f"　⚡ <b>Watchlist 命中：{'、'.join(hits)}</b>")
        if exit_sig:
            block.append(f"　🚪 出場：{exit_sig}")

        lines.append("\n".join(block))

    lines.append(f"\n\n<i>共 {len(signals)} 個訊號。這是研究參考，不是進場指令。</i>")
    return "\n".join(lines)


# ─────────────────────────────────────────
# 推送到 Telegram
# ─────────────────────────────────────────
def send_telegram(text: str) -> bool:
    token   = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    url     = f"https://api.telegram.org/bot{token}/sendMessage"

    try:
        r = requests.post(url, json={
            "chat_id":    chat_id,
            "text":       text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }, timeout=20)
        r.raise_for_status()
        log.info("✅ Telegram 推送成功")
        return True
    except Exception as e:
        log.error(f"Telegram 推送失敗：{e}")
        if 'r' in dir():
            log.error(f"回應：{r.text}")
        return False


def main():
    log.info("=== 推送 agent 開始 ===")
    sb      = init_supabase()
    signals = get_analyzed_signals(sb)
    log.info(f"待推送訊號：{len(signals)} 個")

    message = build_message(signals)
    send_telegram(message)

    log.info("=== 推送完成 ===")


if __name__ == "__main__":
    main()
