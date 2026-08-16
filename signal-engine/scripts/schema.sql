-- ============================================================
-- Social Signal Engine — Supabase Schema v2（架構審查修正版）
-- 在 Supabase Dashboard > SQL Editor 執行
--
-- v2 變更：
--   + keywords 加 UNIQUE(keyword, region)（重跑不再重複插入）
--   + trend_snapshots 的 platform 加入 'rss'（台媒來源）
--   + 新增 signal_outcomes 表（校準期準確率追蹤的核心）
--   + 種子關鍵字改為校準集 30 個（P0：防 429 + 降噪）
-- ============================================================

-- 1. 關鍵字清單
CREATE TABLE IF NOT EXISTS keywords (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  keyword     TEXT NOT NULL,
  category    TEXT,
  language    TEXT DEFAULT 'en',     -- 'en' | 'zh'
  region      TEXT DEFAULT 'US',     -- GT geo：'US' | 'TW' ...
  is_active   BOOLEAN DEFAULT true,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT uq_keyword_region UNIQUE (keyword, region)
);

-- 2. 趨勢快照（只存「絕對值」來源：reddit / rss）
--    Google Trends 是視窗內相對值，不存快照——velocity 在單視窗內直接算
CREATE TABLE IF NOT EXISTS trend_snapshots (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  keyword_id  UUID REFERENCES keywords(id) ON DELETE CASCADE,
  platform    TEXT CHECK (platform IN ('reddit', 'rss')),
  score       FLOAT NOT NULL DEFAULT 0,
  captured_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_snapshots_keyword_platform
  ON trend_snapshots (keyword_id, platform, captured_at DESC);

-- 3. 每日訊號
CREATE TABLE IF NOT EXISTS signals (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  keyword_id        UUID REFERENCES keywords(id) ON DELETE CASCADE,
  velocity_score    FLOAT DEFAULT 0,   -- 互斥基線：近7天 vs 前30天
  info_gap_score    FLOAT DEFAULT 0,
  news_count_30d    INT DEFAULT 0,
  claude_analysis   JSONB,
  potential_tickers TEXT[],
  stage             TEXT CHECK (stage IN ('emerging','growing','near_mainstream')),
  created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_signals_keyword  ON signals (keyword_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_signals_info_gap ON signals (info_gap_score DESC);

-- 4. 個人 Watchlist
CREATE TABLE IF NOT EXISTS watchlist (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticker       TEXT NOT NULL,
  exchange     TEXT CHECK (exchange IN ('NYSE','NASDAQ','ASX','TSE','TWO')),
  company_name TEXT,
  signal_id    UUID REFERENCES signals(id),
  thesis       TEXT,
  status       TEXT DEFAULT 'watching'
                    CHECK (status IN ('watching','positioned','exited')),
  entry_note   TEXT,
  created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- 5. 訊號結果追蹤（v2 新增——沒有這張表，校準期準確率算不出來）
CREATE TABLE IF NOT EXISTS signal_outcomes (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  signal_id       UUID REFERENCES signals(id) ON DELETE CASCADE,
  ticker          TEXT NOT NULL,
  price_at_signal FLOAT,        -- 訊號日股價
  price_1w        FLOAT,
  price_4w        FLOAT,        -- 主要評估點
  price_12w       FLOAT,
  hit             BOOLEAN,      -- 4 週漲幅 > 10% = 命中（門檻可調）
  note            TEXT,         -- 人工標注：真訊號 / 噪音 / 炒作
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 校準期種子關鍵字（30 個）
-- P0：145 個 = 噪音 + pytrends 必被封。先用最高優勢集校準 8 週。
-- 完整 145 個擴充池見 social-signal-engine-mvp.md 第 7 節。
-- ============================================================

INSERT INTO keywords (keyword, category, language, region) VALUES
  -- 供應鏈關鍵材料（Nittobo 邏輯）
  ('Nittobo NVIDIA',              'supply_chain', 'en', 'US'),
  ('PCB substrate shortage',      'supply_chain', 'en', 'US'),
  ('glass fiber cloth AI PCB',    'supply_chain', 'en', 'US'),
  -- 光電 / CPO
  ('CPO co-packaged optics',      'optics',       'en', 'US'),
  ('silicon photonics laser chip','optics',       'en', 'US'),
  ('optical transceiver shortage','optics',       'en', 'US'),
  -- AR 眼鏡供應鏈
  ('AR glasses taiwan supplier',  'ar_optics',    'en', 'US'),
  ('Micro LED AR optics',         'ar_optics',    'en', 'US'),
  ('waveguide lens nano imprint', 'ar_optics',    'en', 'US'),
  -- 台灣半導體
  ('Terafab taiwan',              'tw_semicon',   'en', 'US'),
  -- Local LLM / AI 硬體
  ('local llm setup',             'local_ai',     'en', 'US'),
  ('ollama setup windows',        'local_ai',     'en', 'US'),
  ('run llm on mac mini',         'local_ai',     'en', 'US'),
  ('ai pc upgrade ram',           'ai_hardware',  'en', 'US'),
  -- AI 採用擴散
  ('cursor ai coding',            'ai_adoption',  'en', 'US'),
  ('ai for nurses',               'ai_adoption',  'en', 'US'),
  -- SpaceX / Starlink
  ('Starlink waitlist',           'spacex',       'en', 'US'),
  ('Starship launch cadence',     'spacex',       'en', 'US'),
  ('satellite component lead time','spacex',      'en', 'US'),
  ('SPCX float lockup',           'spacex_event', 'en', 'US'),
  ('SPCX nasdaq 100',             'spacex_event', 'en', 'US'),
  -- 能源
  ('data center power shortage',  'energy',       'en', 'US'),
  ('small modular reactor',       'energy',       'en', 'US'),
  -- 中文（GT geo=TW + 台媒 RSS）
  ('台積電 離職 新創',             'tw_semicon',   'zh', 'TW'),
  ('竹科 AI 新廠',                'tw_semicon',   'zh', 'TW'),
  ('AI 伺服器 液冷',              'tw_semicon',   'zh', 'TW'),
  ('智慧眼鏡 台廠',               'ar_optics',    'zh', 'TW'),
  ('0050 成分股',                 'tw_etf',       'zh', 'TW'),
  ('南電 ABF',                    'tw_semicon',   'zh', 'TW'),
  ('CoWoS 先進封裝',              'tw_semicon',   'zh', 'TW')
ON CONFLICT ON CONSTRAINT uq_keyword_region DO NOTHING;

-- ============================================================
-- 驗證
-- ============================================================
SELECT 'keywords' AS t, COUNT(*) FROM keywords
UNION ALL SELECT 'snapshots', COUNT(*) FROM trend_snapshots
UNION ALL SELECT 'signals',   COUNT(*) FROM signals
UNION ALL SELECT 'outcomes',  COUNT(*) FROM signal_outcomes;
