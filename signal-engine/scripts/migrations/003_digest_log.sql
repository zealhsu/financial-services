-- ============================================================
-- 003 — digest_log：推送去重的記憶
--
-- 在 Supabase Dashboard > SQL Editor 執行一次。
--
-- 為什麼需要：send_digest.py 原本只查「今天的訊號」，對推過什麼沒有記憶。
-- 一個關鍵字熱 5 天 = 5 則一模一樣的通知。兩週後這個系統就會被關掉，
-- 而被關掉的通知等於沒有這個系統。
--
-- 規則不是「推過就永久靜音」——一個關鍵字從 emerging 走到
-- near_mainstream，那是出場訊號，正是最需要看到的時候。所以是
-- 冷卻期（7 天）+ 升級破例（階段前進，或 info_gap 高出 50%）。
-- ============================================================

CREATE TABLE IF NOT EXISTS digest_log (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  keyword_id     UUID REFERENCES keywords(id) ON DELETE CASCADE,
  -- collect_trends.py 每天會刪掉當天的 signals 列再重插，
  -- 所以這裡用 SET NULL：訊號列沒了，推送紀錄還在。
  -- 去重真正的鍵是 keyword_id，不是 signal_id。
  signal_id      UUID REFERENCES signals(id) ON DELETE SET NULL,
  info_gap_score FLOAT,
  stage          TEXT,
  pushed_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_digest_log_keyword
  ON digest_log (keyword_id, pushed_at DESC);

-- 驗證
SELECT COUNT(*) AS pushes, COUNT(DISTINCT keyword_id) AS keywords FROM digest_log;
