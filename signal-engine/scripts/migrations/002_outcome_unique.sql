-- ============================================================
-- 002 — signal_outcomes 加上 (signal_id, ticker) 唯一鍵
--
-- 在 Supabase Dashboard > SQL Editor 執行一次。
-- schema.sql 已經跑過的專案要跑這個；全新專案跑 schema.sql 就含了。
--
-- 為什麼需要：backfill_outcomes.py 每天重跑，靠 upsert 補齊
-- price_1w / price_4w / price_12w。沒有唯一鍵，upsert 退化成 insert，
-- 同一個 (訊號, 標的) 每天多一列，命中率會被重複計算灌爆。
-- ============================================================

-- 先清掉既有重複（保留最早建立的那筆——它才有正確的 price_at_signal）
DELETE FROM signal_outcomes a
USING signal_outcomes b
WHERE a.signal_id = b.signal_id
  AND a.ticker    = b.ticker
  AND a.created_at > b.created_at;

ALTER TABLE signal_outcomes
  DROP CONSTRAINT IF EXISTS uq_outcome_signal_ticker;

ALTER TABLE signal_outcomes
  ADD CONSTRAINT uq_outcome_signal_ticker UNIQUE (signal_id, ticker);

CREATE INDEX IF NOT EXISTS idx_outcomes_hit
  ON signal_outcomes (hit, created_at DESC);

-- 驗證
SELECT COUNT(*) AS outcomes, COUNT(hit) AS judged FROM signal_outcomes;
