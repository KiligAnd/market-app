PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS market_sources (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL UNIQUE,
  enabled INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS materials (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  unit TEXT NOT NULL DEFAULT '元/吨',
  material_type TEXT NOT NULL DEFAULT '通用',
  is_demo INTEGER NOT NULL DEFAULT 0,
  enabled INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS material_aliases (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  material_id INTEGER NOT NULL REFERENCES materials(id),
  source_id INTEGER NOT NULL REFERENCES market_sources(id),
  external_name TEXT NOT NULL,
  external_spec TEXT,
  diid TEXT,
  region TEXT,
  tax TEXT,
  unit TEXT,
  status TEXT NOT NULL DEFAULT '已匹配',
  created_at TEXT NOT NULL,
  UNIQUE (source_id, external_name, external_spec)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_alias_source_diid
  ON material_aliases (source_id, diid)
  WHERE diid IS NOT NULL;

-- 网站省市字典缓存（富宝 /region/provinces）
CREATE TABLE IF NOT EXISTS source_regions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id INTEGER NOT NULL REFERENCES market_sources(id),
  province_id INTEGER NOT NULL,
  province_name TEXT NOT NULL,
  province_short TEXT,
  city_id INTEGER NOT NULL,
  city_name TEXT NOT NULL,
  city_short TEXT,
  updated_at TEXT NOT NULL,
  UNIQUE (source_id, city_id)
);

CREATE INDEX IF NOT EXISTS idx_source_regions_province
  ON source_regions (source_id, province_id);

-- 网站级同步设置：总开关、是否已接入自动解析
CREATE TABLE IF NOT EXISTS source_sync_settings (
  source_id INTEGER PRIMARY KEY REFERENCES market_sources(id),
  enabled INTEGER NOT NULL DEFAULT 1,
  auto_supported INTEGER NOT NULL DEFAULT 0,
  sync_mode TEXT NOT NULL DEFAULT 'daily',
  daily_cap INTEGER NOT NULL DEFAULT 20,
  last_sync_at TEXT,
  last_error TEXT,
  updated_at TEXT NOT NULL
);

-- 网站物料采集配置：一行 = 一个网站产品（productId）
CREATE TABLE IF NOT EXISTS source_material_configs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id INTEGER NOT NULL REFERENCES market_sources(id),
  keyword TEXT NOT NULL,
  province_id INTEGER,
  province_name TEXT,
  city_id INTEGER,
  city_name TEXT,
  product_id TEXT NOT NULL,
  variety_id INTEGER,
  classify_id INTEGER,
  external_name TEXT NOT NULL,
  external_web_name TEXT,
  external_place TEXT,
  external_spec TEXT,
  external_tax TEXT,
  external_unit TEXT,
  external_org TEXT,
  price_type TEXT NOT NULL DEFAULT '市场价格',
  material_id INTEGER REFERENCES materials(id),
  status TEXT NOT NULL DEFAULT '启用',
  history_days INTEGER NOT NULL DEFAULT 30,
  init_next_end TEXT,
  init_done_windows INTEGER NOT NULL DEFAULT 0,
  init_total_windows INTEGER NOT NULL DEFAULT 0,
  initialized INTEGER NOT NULL DEFAULT 0,
  history_rows INTEGER NOT NULL DEFAULT 0,
  last_history_date TEXT,
  last_snapshot_at TEXT,
  last_verified_at TEXT,
  last_error TEXT,
  remark TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (source_id, product_id)
);

CREATE INDEX IF NOT EXISTS idx_collect_config_status
  ON source_material_configs (status, id);

CREATE INDEX IF NOT EXISTS idx_collect_config_material
  ON source_material_configs (material_id);

CREATE TABLE IF NOT EXISTS market_quotes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  material_id INTEGER REFERENCES materials(id),
  source_id INTEGER NOT NULL REFERENCES market_sources(id),
  alias_id INTEGER REFERENCES material_aliases(id),
  diid TEXT,
  product_id TEXT,
  quote_date TEXT NOT NULL,
  price_type TEXT NOT NULL DEFAULT '市场价格',
  source_material_name TEXT,
  raw_text TEXT,
  raw_low REAL,
  raw_high REAL,
  avg_price REAL NOT NULL,
  buy_price REAL,
  sell_price REAL,
  change_text TEXT,
  change_value REAL,
  spec TEXT,
  region TEXT,
  tax TEXT,
  unit TEXT NOT NULL DEFAULT '元/吨',
  data_status TEXT,
  captured_at TEXT,
  imported_at TEXT,
  source_url TEXT,
  match_status TEXT NOT NULL DEFAULT 'matched',
  period_avg_override REAL,
  is_demo INTEGER NOT NULL DEFAULT 0
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_quote_source_diid_date
  ON market_quotes (source_id, COALESCE(diid, source_material_name), price_type, quote_date);

CREATE INDEX IF NOT EXISTS idx_quote_material_date
  ON market_quotes (material_id, quote_date);

CREATE INDEX IF NOT EXISTS idx_quote_date_id
  ON market_quotes (quote_date DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_quote_source_date
  ON market_quotes (source_id, quote_date);

CREATE TABLE IF NOT EXISTS pricing_templates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  formula TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pricing_template_factors (
  template_id INTEGER NOT NULL REFERENCES pricing_templates(id) ON DELETE CASCADE,
  factor TEXT NOT NULL,
  sort_order INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (template_id, factor)
);

CREATE TABLE IF NOT EXISTS pricing_params (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  material_id INTEGER NOT NULL REFERENCES materials(id),
  template_id INTEGER NOT NULL REFERENCES pricing_templates(id),
  period_type TEXT NOT NULL DEFAULT '周',
  offset_value REAL,
  coefficient REAL,
  status TEXT NOT NULL DEFAULT '生效',
  version INTEGER NOT NULL DEFAULT 1,
  effective_from TEXT,
  updated_at TEXT NOT NULL,
  UNIQUE (material_id, version)
);

CREATE TABLE IF NOT EXISTS pricing_param_sources (
  param_id INTEGER NOT NULL REFERENCES pricing_params(id) ON DELETE CASCADE,
  source_id INTEGER NOT NULL REFERENCES market_sources(id),
  PRIMARY KEY (param_id, source_id)
);

-- 物料计价规则：一个网站物料可对应多个公司系统物料
CREATE TABLE IF NOT EXISTS material_pricing_rules (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_config_id INTEGER NOT NULL REFERENCES source_material_configs(id),
  material_id INTEGER NOT NULL REFERENCES materials(id),
  template_id INTEGER NOT NULL REFERENCES pricing_templates(id),
  period_type TEXT NOT NULL DEFAULT '周',
  offset_value REAL,
  coefficient REAL,
  status TEXT NOT NULL DEFAULT '生效',
  version INTEGER NOT NULL DEFAULT 1,
  effective_from TEXT,
  updated_at TEXT NOT NULL,
  UNIQUE (source_config_id, material_id, version)
);

CREATE INDEX IF NOT EXISTS idx_pricing_rules_source
  ON material_pricing_rules (source_config_id, status);

CREATE TABLE IF NOT EXISTS calc_schedules (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  cycle TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT '运行中',
  last_run_at TEXT,
  next_run_at TEXT
);

CREATE TABLE IF NOT EXISTS calc_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  batch_no TEXT NOT NULL UNIQUE,
  run_at TEXT NOT NULL,
  total_count INTEGER NOT NULL DEFAULT 0,
  success_count INTEGER NOT NULL DEFAULT 0,
  fail_count INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT '成功'
);

CREATE TABLE IF NOT EXISTS calc_results (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL REFERENCES calc_runs(id) ON DELETE CASCADE,
  material_id INTEGER NOT NULL REFERENCES materials(id),
  source_config_id INTEGER REFERENCES source_material_configs(id),
  template_id INTEGER NOT NULL REFERENCES pricing_templates(id),
  period_start TEXT,
  period_end TEXT,
  period_avg REAL NOT NULL,
  offset_value REAL,
  coefficient REAL,
  calc_price REAL NOT NULL,
  sync_status TEXT NOT NULL DEFAULT '已同步',
  review_status TEXT NOT NULL DEFAULT '待复核',
  reviewer TEXT,
  reviewed_at TEXT,
  reject_reason TEXT,
  created_at TEXT NOT NULL,
  UNIQUE (run_id, material_id)
);

CREATE TABLE IF NOT EXISTS operation_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  log_time TEXT NOT NULL,
  action_type TEXT NOT NULL,
  operator TEXT NOT NULL,
  content TEXT NOT NULL,
  ip TEXT
);

CREATE INDEX IF NOT EXISTS idx_operation_logs_time ON operation_logs (log_time DESC);

CREATE TABLE IF NOT EXISTS api_call_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  called_at TEXT NOT NULL,
  mode TEXT NOT NULL,
  purpose TEXT NOT NULL,
  endpoint TEXT,
  method TEXT,
  status_code TEXT,
  elapsed_ms INTEGER,
  result TEXT
);

CREATE INDEX IF NOT EXISTS idx_api_call_logs_time ON api_call_logs (called_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_api_call_unique
  ON api_call_logs (called_at, endpoint, purpose, mode);

CREATE TABLE IF NOT EXISTS sync_state (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  initialized INTEGER NOT NULL DEFAULT 0,
  initialized_at TEXT,
  init_target_start TEXT,
  init_total_windows INTEGER NOT NULL DEFAULT 0,
  init_done_windows INTEGER NOT NULL DEFAULT 0,
  init_next_end TEXT,
  last_run_date TEXT,
  last_run_result TEXT,
  last_snapshot_at TEXT,
  last_history_date TEXT,
  last_reconcile_date TEXT,
  history_rows INTEGER NOT NULL DEFAULT 0,
  api_call_date TEXT,
  api_calls_today INTEGER NOT NULL DEFAULT 0,
  last_error TEXT,
  last_run_materials TEXT,
  last_run_summary TEXT,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL
);

CREATE VIEW IF NOT EXISTS v_quote_rolling AS
SELECT
  q.*,
  (
    SELECT ROUND(AVG(q2.avg_price))
    FROM market_quotes q2
    WHERE q2.material_id = q.material_id
      AND q2.source_id = q.source_id
      AND date(q2.quote_date) BETWEEN date(q.quote_date, '-6 days') AND date(q.quote_date)
  ) AS rolling_7d_avg
FROM market_quotes q;

INSERT OR IGNORE INTO schema_migrations (version, applied_at)
VALUES (1, '2026-10-27 00:00:00');
