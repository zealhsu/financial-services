# CLAUDE.md — Social Signal Engine

> 這個檔案讓 Claude Code 自動理解本專案。開發時它會先讀這裡。

## 這是什麼

Social Signal Engine 是一個**投資訊號偵測系統**，核心理念是
Chris Camillo 的社交套利（social arbitrage）：
在資訊變成市場共識之前，從社群訊號中發現被低估的投資機會。

不是會計工具、不是自動交易機器人。它只做一件事：
**偵測趨勢 → 分析受益公司 → 推送給人類決策。判斷永遠由人做。**

## 核心哲學（改動程式碼時必須遵守）

1. **資訊差優先**：只找「市場還沒定價」的訊號。已被 CNBC 報導的 = 出場訊號，不是進場。
2. **上游優於龍頭**：優先找供應鏈上游、冷門的二層受益者（像 Nittobo、華通），
   而不是人人皆知的 NVDA/TSM。
3. **中文是差異化優勢**：台灣/亞洲社群訊號，西方投資者看不到，這是語言套利。
4. **不自動下單**：系統只做資訊整合與推送，不碰任何交易 API。
5. **專注勝過鋪滿**：訊號寧缺勿濫，每日最多推 5 個。噪音是敵人。

## 架構（Layer 1，已完成）

```
collect_trends.py    收集：Google Trends + Reddit + 台媒 RSS
      ↓              計算 velocity（近7天 vs 前30天互斥基線）+ info_gap_score
generate_analysis.py 分析：Claude API 找供應鏈受益公司，回結構化 JSON
      ↓              比對 watchlist，標注 ⚡ 命中
send_digest.py       推送：每早 Telegram，最多 5 訊號
```

排程：GitHub Actions 每日 UTC 18:00（台灣凌晨 2 點）一條龍跑完。

## 資料流與關鍵設計

- **Google Trends 分數是視窗內相對值**：每天正規化基準不同，
  逐日存單點不可比。所以 velocity 在單次 90 天查詢的視窗內直接算，
  **GT 不存 trend_snapshots**。只有絕對值來源（Reddit 貼文數、RSS 命中數）才存快照。
- **velocity 用互斥基線**：近 7 天 vs 之前 30 天（day -37 ~ -8），
  不是近 7 天 vs 含自己的 30 天（會自我稀釋 23%）。
- **info_gap_score**：velocity 高但 news_count 低 = 高分（視窗還開著）。
- **pytrends 會被 429**：GitHub Actions 是 datacenter IP，Google 封得兇。
  請求間隔 60s + 隨機抖動；校準期只跑 30 個關鍵字。

## 資料庫（Supabase / PostgreSQL）

- `keywords`：監控關鍵字（含 language/region，UNIQUE(keyword,region)）
- `trend_snapshots`：只存 reddit/rss 絕對值快照
- `signals`：每日計算結果（velocity/info_gap/claude_analysis/potential_tickers/stage）
- `watchlist`：個人觀察名單（status: watching/positioned/exited）
- `signal_outcomes`：訊號後續股價追蹤（校準期算命中率的核心）

完整 schema 見 `scripts/schema.sql`。

## 環境變數

```
SUPABASE_URL / SUPABASE_KEY          （service_role key）
REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET / REDDIT_USER_AGENT
ANTHROPIC_API_KEY
TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID
```

## 現在的階段

**8 週校準期**：先跑 30 個高優勢關鍵字，用 signal_outcomes 記錄
「訊號後 4 週股價是否漲 >10%」，算命中率。**校準期只觀察不投資。**
命中率 > 40% 才擴充關鍵字池（完整 145 個見 social-signal-engine-mvp.md）。

## 開發時常見任務

- 加 collector（PTT/Dcard 中文社群）→ 學 fetch_rss_hits 的模式
- 自動回填 signal_outcomes（抓 4 週後股價）→ 需要股價 API（可考慮 yfinance）
- 出場警報（watchlist 中 positioned 標的的 news 暴增）→ 反向監控
- 換推送管道（Telegram → email）→ 改 send_digest.py

## 不要做的事

- 不要接自動交易 API
- 不要為了「多抓一點」而放寬 velocity 門檻（噪音會淹沒訊號）
- 不要把龍頭股當主要推薦（那些資訊差早沒了）
- 不要 commit 任何 API key
