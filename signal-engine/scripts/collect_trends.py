"""
collect_trends.py — v2（架構審查修正版）
Social Signal Engine — Layer 1 資料收集腳本

每日 UTC 18:00（台灣凌晨 2 點）由 GitHub Actions 執行。

── v2 修正（P0 + P1）──────────────────────────────
P0-1  Google Trends 單視窗計算：
      GT 分數是查詢視窗內的相對值（視窗最高點=100），
      每天的正規化基準不同 → 逐日存單點不可比。
      v2 改為：每天抓完整 90 天序列，同視窗內直接算 velocity，
      不再為 GT 存 trend_snapshots。
P0-2  關鍵字縮減至校準集（28 個）由 schema.sql 控制。
P1-1  台媒 RSS collector：中文關鍵字改用今周刊/DigiTimes 等
      RSS 命中數（Reddit 搜中文近乎零結果）。
P1-2  Velocity 互斥基線：最近 7 天 vs 之前 30 天（day -37 ~ -8），
      不再讓 7 天樣本稀釋自己的基線。
P1-3  防 429：GT 請求間隔 60 秒 + 0~30 秒隨機抖動。
────────────────────────────────────────────────

環境變數（GitHub Secrets）:
  SUPABASE_URL / SUPABASE_KEY
  REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET / REDDIT_USER_AGENT
"""

import os
import time
import random
import logging
from datetime import datetime, timezone

from pytrends.request import TrendReq
import praw
import feedparser
from supabase import create_client, Client

# ─────────────────────────────────────────
# 設定
# ─────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# GT 防封鎖間隔（秒）
GT_SLEEP_BASE   = 60
GT_SLEEP_JITTER = 30

# 台灣媒體 RSS 來源（中文關鍵字的訊號來源）
# 可自行增減；feedparser 對壞掉的 feed 會優雅降級
TAIWAN_RSS_FEEDS = [
    "https://www.businesstoday.com.tw/rss/list/80407",   # 今周刊 焦點新聞
    "https://www.digitimes.com.tw/rss/daily.xml",         # DigiTimes
    "https://money.udn.com/rssfeed/news/1001/5591/5612",  # 經濟日報 科技
    "https://technews.tw/feed/",                          # 科技新報
]


# ─────────────────────────────────────────
# 初始化
# ─────────────────────────────────────────
def init_supabase() -> Client:
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


def init_reddit() -> praw.Reddit:
    return praw.Reddit(
        client_id     = os.environ["REDDIT_CLIENT_ID"],
        client_secret = os.environ["REDDIT_CLIENT_SECRET"],
        user_agent    = os.environ.get("REDDIT_USER_AGENT", "social-signal-bot/2.0"),
    )


# ─────────────────────────────────────────
# Google Trends：抓 90 天序列（單視窗）
# ─────────────────────────────────────────
def fetch_google_trends(keyword: str, region: str = "US") -> list[float]:
    """
    回傳同一視窗內的 90 天每日序列。
    這個序列在「視窗內」是自洽可比的——velocity 必須在這裡直接算，
    不能存單點跨日比較（每天的正規化基準不同）。
    """
    try:
        pt = TrendReq(hl="en-US", tz=360, timeout=(10, 25))
        pt.build_payload([keyword], timeframe="today 3-m", geo=region)
        df = pt.interest_over_time()

        if df.empty or keyword not in df.columns:
            log.warning(f"GT 無資料：{keyword}")
            return []

        scores = [float(s) for s in df[keyword].tolist()]
        log.info(f"GT [{keyword}] {len(scores)} 筆（單視窗）")
        return scores

    except Exception as e:
        log.error(f"GT 錯誤 [{keyword}]: {e}")
        return []


# ─────────────────────────────────────────
# Velocity：互斥基線（P1-2 修正）
# ─────────────────────────────────────────
def calculate_velocity(daily_scores: list[float]) -> float:
    """
    最近 7 天均值 vs 之前 30 天均值（day -37 ~ day -8，互斥）。
    舊版拿 7 天跟「包含這 7 天的 30 天」比，訊號被自我稀釋 ~23%。
    """
    if len(daily_scores) < 37:
        return 0.0

    recent_7d   = daily_scores[-7:]
    baseline_30 = daily_scores[-37:-7]

    avg_recent   = sum(recent_7d)   / len(recent_7d)
    avg_baseline = sum(baseline_30) / len(baseline_30)
    base         = avg_baseline if avg_baseline > 0 else 1.0

    return ((avg_recent - avg_baseline) / base) * 100


# ─────────────────────────────────────────
# Reddit：英文關鍵字的討論熱度（絕對值，可存）
# ─────────────────────────────────────────
def fetch_reddit_score(reddit: praw.Reddit, keyword: str) -> float:
    try:
        results = list(reddit.subreddit("all").search(
            keyword, sort="new", time_filter="day", limit=50,
        ))
        if not results:
            return 0.0
        total = sum(max(p.score, 1) for p in results)
        weighted = float(len(results)) * (total / len(results))
        log.info(f"Reddit [{keyword}] {len(results)} 篇，加權 {weighted:.1f}")
        return weighted
    except Exception as e:
        log.error(f"Reddit 錯誤 [{keyword}]: {e}")
        return 0.0


# ─────────────────────────────────────────
# 台媒 RSS：中文關鍵字的命中數（P1-1 新增）
# ─────────────────────────────────────────
def fetch_rss_hits(keyword: str, feeds: list[str] = TAIWAN_RSS_FEEDS) -> float:
    """
    掃描台灣媒體 RSS，計算 keyword 在標題+摘要的命中篇數。
    絕對值 → 可存 snapshot 跨日累積，之後可對 RSS 序列算 velocity。
    中文關鍵字含空格時，拆詞後「全部出現」才算命中
    （例：「南電 ABF」→ 標題需同時含「南電」和「ABF」）。
    """
    terms = [t for t in keyword.split() if t]
    hits  = 0
    for url in feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                text = f"{entry.get('title','')} {entry.get('summary','')}"
                if all(t in text for t in terms):
                    hits += 1
        except Exception as e:
            log.warning(f"RSS feed 失敗 {url}: {e}")
    log.info(f"RSS [{keyword}] 命中 {hits} 篇")
    return float(hits)


# ─────────────────────────────────────────
# 媒體覆蓋度（Info Gap 的分母）
# ─────────────────────────────────────────
def estimate_news_count(reddit: praw.Reddit, keyword: str, language: str) -> int:
    """
    英文 → Reddit 財經版（investing/stocks/finance）月內結果數
    中文 → 台媒 RSS 命中數 ×5 放大（RSS 池小，校準係數可調）
    這是 proxy；之後可換 Google News RSS 提升精度。
    """
    if language == "zh":
        return int(fetch_rss_hits(keyword) * 5)
    try:
        finance_subs = "investing+stocks+finance+SecurityAnalysis"
        results = list(reddit.subreddit(finance_subs).search(
            keyword, sort="relevance", time_filter="month", limit=50,
        ))
        return len(results)
    except Exception as e:
        log.error(f"新聞估算失敗 [{keyword}]: {e}")
        return 0


def calculate_info_gap(velocity: float, news_count: int) -> float:
    if velocity <= 0:
        return 0.0
    saturation = min(news_count / 50.0, 1.0)
    return min(velocity * (1.0 - saturation), 100.0)


# ─────────────────────────────────────────
# Supabase 寫入
# ─────────────────────────────────────────
def save_snapshot(sb: Client, keyword_id: str, platform: str, score: float):
    """只存「絕對值」來源：reddit / rss。GT 不存（相對值不可跨日比）。"""
    try:
        sb.table("trend_snapshots").insert({
            "keyword_id": keyword_id, "platform": platform,
            "score": score,
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception as e:
        log.error(f"snapshot 失敗 [{keyword_id}/{platform}]: {e}")


def save_signal(sb: Client, keyword_id: str, velocity: float,
                info_gap: float, news_count: int):
    try:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        sb.table("signals").delete().eq("keyword_id", keyword_id)\
          .gte("created_at", f"{today}T00:00:00Z").execute()
        sb.table("signals").insert({
            "keyword_id": keyword_id,
            "velocity_score": round(velocity, 2),
            "info_gap_score": round(info_gap, 2),
            "news_count_30d": news_count,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception as e:
        log.error(f"signal 失敗 [{keyword_id}]: {e}")


# ─────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────
def main():
    log.info("=== Social Signal Engine v2 收集開始 ===")
    sb     = init_supabase()
    reddit = init_reddit()

    kws = sb.table("keywords").select("*").eq("is_active", True).execute().data
    log.info(f"{len(kws)} 個 active 關鍵字")

    for kw in kws:
        kid, keyword = kw["id"], kw["keyword"]
        region   = kw.get("region", "US")
        language = kw.get("language", "en")
        log.info(f"--- {keyword} [{region}/{language}] ---")

        # 1) GT 單視窗 velocity（中英文皆抓，中文用 geo=TW）
        gt_series = fetch_google_trends(keyword, region)
        velocity  = calculate_velocity(gt_series)

        # 2) 社群熱度：英文走 Reddit，中文走台媒 RSS（絕對值才存 snapshot）
        if language == "zh":
            heat = fetch_rss_hits(keyword)
            save_snapshot(sb, kid, "rss", heat)
        else:
            heat = fetch_reddit_score(reddit, keyword)
            save_snapshot(sb, kid, "reddit", heat)

        # 3) 媒體覆蓋度 → Info Gap
        news_count = estimate_news_count(reddit, keyword, language)
        info_gap   = calculate_info_gap(velocity, news_count)

        # 4) 寫入訊號
        save_signal(sb, kid, velocity, info_gap, news_count)
        log.info(f"✅ {keyword} | v={velocity:.1f}% | gap={info_gap:.1f} | news={news_count}")

        # 5) 防 429：60s + 隨機抖動（P1-3）
        time.sleep(GT_SLEEP_BASE + random.uniform(0, GT_SLEEP_JITTER))

    log.info("=== 收集完成 ===")


if __name__ == "__main__":
    main()
