"""
generate_analysis.py
Social Signal Engine — Layer 1 分析 agent

在 collect_trends.py 跑完後執行（GitHub Actions 排在其後，或每日 03:00）。
把冷冰冰的 velocity 數字，變成「哪支股票、為什麼、什麼階段、何時出場」的投資 brief。
這是整個系統唯一需要 Claude 智慧的地方——等於把「手動問 Claude 分析」自動化。

流程：
1. 從 signals 表挑出今天 info_gap_score 前 5 高的訊號
2. 每個訊號連同趨勢數據丟給 Claude API
3. Claude 回傳結構化 JSON（受益公司 / 階段 / 出場訊號）
4. 比對 watchlist，標注 ⚡ 命中
5. 把分析寫回 signals 表的 claude_analysis 欄

環境變數（GitHub Secrets）：
  SUPABASE_URL / SUPABASE_KEY
  ANTHROPIC_API_KEY   ← 與 Vela 同一個 Anthropic 帳號即可
"""

import os
import json
import logging
from datetime import datetime, timezone

import anthropic
from supabase import create_client, Client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

MODEL      = "claude-sonnet-4-6"
TOP_N      = 5      # 每天只分析前 5 名，控制成本與噪音
MIN_VELOCITY = 20   # velocity 低於此值不analyze（弱訊號）


# ─────────────────────────────────────────
# 初始化
# ─────────────────────────────────────────
def init_supabase() -> Client:
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


def init_claude() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


# ─────────────────────────────────────────
# 取今日前 N 名訊號（附關鍵字資訊）
# ─────────────────────────────────────────
def get_top_signals(sb: Client, n: int = TOP_N) -> list[dict]:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = (
        sb.table("signals")
        .select("*, keywords(keyword, category, language, region)")
        .gte("created_at", f"{today}T00:00:00Z")
        .gte("velocity_score", MIN_VELOCITY)
        .order("info_gap_score", desc=True)
        .limit(n)
        .execute()
    ).data
    log.info(f"今日符合條件訊號：{len(rows)} 個")
    return rows


# ─────────────────────────────────────────
# 取 watchlist（用於命中比對）
# ─────────────────────────────────────────
def get_watchlist_tickers(sb: Client) -> set[str]:
    rows = sb.table("watchlist").select("ticker").execute().data
    return {r["ticker"].upper() for r in rows}


# ─────────────────────────────────────────
# Claude 分析單一訊號
# ─────────────────────────────────────────
SYSTEM_PROMPT = """你是一個社交套利分析師，專門找被市場忽視的趨勢和受益公司的連結。

你的分析框架：
- 「直接受益」：這個趨勢直接提升該公司的營收
- 「供應鏈受益」：趨勢帶動上游原料/零件/服務需求（這類最有資訊差價值）
- 「競爭受損」：這個趨勢對哪些公司是負面的

判斷趨勢階段：
- emerging：只在垂直社群/非英語媒體討論，主流財經零報導（資訊差最大）
- growing：開始出現在非財經主流媒體
- near_mainstream：財經媒體開始注意，分析師快追上（接近出場點）

重要原則：
- 優先找「供應鏈上游、市場還沒定價」的二層受益者（像 Nittobo、華通那種），
  而不是人人皆知的龍頭股
- 龍頭股（NVDA/TSM 等）若資訊差已消失，標注為「已定價，僅供參考」
- 誠實評估：如果這個趨勢找不到清楚的上市受益者，就說找不到

回覆必須是純 JSON，不要加任何其他文字、不要 markdown 圍欄。"""

USER_TEMPLATE = """以下是一個偵測到的趨勢訊號：

關鍵字：{keyword}
類別：{category}
語言/地區：{language} / {region}
趨勢速度：+{velocity:.1f}%（最近 7 天 vs 之前 30 天，互斥基線）
資訊差距離：{info_gap:.1f}/100（越高代表市場越不知道）
財經媒體覆蓋度：{news_count} 篇（過去 30 天）

請以以下 JSON 格式回覆：
{{
  "summary": "用一句話說明這個趨勢是什麼",
  "stage": "emerging | growing | near_mainstream",
  "direct_beneficiaries": [
    {{"ticker": "string", "company": "string", "exchange": "NYSE|NASDAQ|ASX|TSE|TWO",
      "reason": "為何受益", "confidence": 1-10}}
  ],
  "supply_chain_beneficiaries": [
    {{"ticker": "string", "company": "string", "reason": "上游受益原因（資訊差價值最高）"}}
  ],
  "mainstream_timeline": "預計幾週後出現在財經媒體",
  "exit_trigger": "什麼事件代表資訊差消失（出場訊號）",
  "key_risk": "最大的看錯風險",
  "overall_confidence": 1-10
}}"""


def analyze_signal(claude: anthropic.Anthropic, signal: dict) -> dict | None:
    kw = signal.get("keywords") or {}
    user_msg = USER_TEMPLATE.format(
        keyword    = kw.get("keyword", "unknown"),
        category   = kw.get("category", ""),
        language   = kw.get("language", "en"),
        region     = kw.get("region", "US"),
        velocity   = signal.get("velocity_score", 0),
        info_gap   = signal.get("info_gap_score", 0),
        news_count = signal.get("news_count_30d", 0),
    )

    try:
        resp = claude.messages.create(
            model      = MODEL,
            max_tokens = 1500,
            system     = SYSTEM_PROMPT,
            messages   = [{"role": "user", "content": user_msg}],
        )
        text = resp.content[0].text.strip()

        # 防禦：萬一 Claude 加了 markdown 圍欄
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        return json.loads(text)

    except json.JSONDecodeError as e:
        log.error(f"JSON 解析失敗 [{kw.get('keyword')}]: {e}")
        return None
    except Exception as e:
        log.error(f"Claude 分析失敗 [{kw.get('keyword')}]: {e}")
        return None


# ─────────────────────────────────────────
# 標注 watchlist 命中
# ─────────────────────────────────────────
def tag_watchlist_hits(analysis: dict, watchlist: set[str]) -> list[str]:
    tickers = set()
    for b in analysis.get("direct_beneficiaries", []):
        if b.get("ticker"):
            tickers.add(b["ticker"].upper())
    for b in analysis.get("supply_chain_beneficiaries", []):
        if b.get("ticker"):
            tickers.add(b["ticker"].upper())
    return sorted(tickers & watchlist)


# ─────────────────────────────────────────
# 寫回 signals 表
# ─────────────────────────────────────────
def save_analysis(sb: Client, signal_id: str, analysis: dict,
                  tickers: list[str], stage: str) -> None:
    try:
        sb.table("signals").update({
            "claude_analysis":   analysis,
            "potential_tickers": tickers,
            "stage":             stage,
        }).eq("id", signal_id).execute()
    except Exception as e:
        log.error(f"寫回分析失敗 [{signal_id}]: {e}")


# ─────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────
def main():
    log.info("=== 分析 agent 開始 ===")
    sb        = init_supabase()
    claude    = init_claude()
    watchlist = get_watchlist_tickers(sb)
    log.info(f"watchlist 共 {len(watchlist)} 支")

    signals = get_top_signals(sb)
    if not signals:
        log.info("今日無符合條件訊號，結束。")
        return

    for sig in signals:
        kw = (sig.get("keywords") or {}).get("keyword", "?")
        log.info(f"--- 分析：{kw} (gap={sig.get('info_gap_score')}) ---")

        analysis = analyze_signal(claude, sig)
        if not analysis:
            continue

        # 收集所有提到的 ticker（不只 watchlist 命中）
        all_tickers = []
        for b in analysis.get("direct_beneficiaries", []):
            if b.get("ticker"):
                all_tickers.append(b["ticker"].upper())
        for b in analysis.get("supply_chain_beneficiaries", []):
            if b.get("ticker"):
                all_tickers.append(b["ticker"].upper())

        hits = tag_watchlist_hits(analysis, watchlist)
        if hits:
            analysis["watchlist_hits"] = hits
            log.info(f"⚡ Watchlist 命中：{', '.join(hits)}")

        save_analysis(
            sb, sig["id"], analysis,
            sorted(set(all_tickers)),
            analysis.get("stage", "emerging"),
        )
        log.info(f"✅ {kw}｜階段={analysis.get('stage')}｜"
                 f"信心={analysis.get('overall_confidence')}｜"
                 f"標的={sorted(set(all_tickers))}")

    log.info("=== 分析完成 ===")


if __name__ == "__main__":
    main()
