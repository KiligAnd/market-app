# -*- coding: utf-8 -*-
"""SQLite 连接、建表与通用审计工具。"""
import csv
import datetime as dt
import os
import sqlite3
from typing import Dict, Iterator, Optional, Tuple

SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(SERVER_DIR)
CODE_DIR = os.path.dirname(APP_DIR)
PROJECT_ROOT = os.path.dirname(CODE_DIR)
APP_DATA_DIR = os.path.join(APP_DIR, 'data')
SOURCE_DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
DB_PATH = os.path.join(APP_DATA_DIR, 'market.db')
SCHEMA_PATH = os.path.join(SERVER_DIR, 'schema.sql')


def now_text() -> str:
    return dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def connect() -> sqlite3.Connection:
    os.makedirs(APP_DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute('PRAGMA journal_mode = WAL')
    conn.execute('PRAGMA busy_timeout = 5000')
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    with open(SCHEMA_PATH, 'r', encoding='utf-8') as fh:
        conn.executescript(fh.read())
    conn.commit()


def snapshot_capture_map() -> Dict[Tuple[str, str], str]:
    """扫描项目 data 目录里的快照 CSV，返回 {(productId, 数据日期): 抓取时间}。

    历史回补 CSV 没有逐行抓取时间，只有快照 CSV 有；因此台账“采集时间”
    只对最新快照行有真实值，其余历史行留空、展示为“历史回补”。
    """
    result: Dict[Tuple[str, str], str] = {}
    if not os.path.isdir(SOURCE_DATA_DIR):
        return result
    for name in sorted(os.listdir(SOURCE_DATA_DIR)):
        if not name.lower().endswith('.csv'):
            continue
        try:
            with open(os.path.join(SOURCE_DATA_DIR, name),
                      encoding='utf-8-sig', newline='') as fh:
                reader = csv.DictReader(fh)
                fields = set(reader.fieldnames or [])
                if '抓取时间' not in fields or '数据日期' not in fields:
                    continue
                for row in reader:
                    # 快照 CSV 的 diid 列存的是搜索接口的 productId
                    product_id = str(row.get('diid') or '').strip()
                    date_text = (row.get('数据日期') or '').strip()
                    stamp = (row.get('抓取时间') or '').strip()
                    if product_id and date_text and stamp:
                        result[(product_id, date_text)] = stamp
        except (OSError, UnicodeDecodeError):
            continue
    return result


# 富宝旧 diid 与搜索 productId 的已知对应关系（同一条行情，两套 ID）
LEGACY_PRODUCT_IDS = {
    '163321': '636',   # 清远机生铝
    '32105': '1591',   # 佛山黄杂铜
}


def migrate_schema(conn: sqlite3.Connection) -> None:
    """兼容旧库：补字段、回填、建索引、补采集配置与计价规则。"""
    columns = {row['name'] for row in conn.execute('PRAGMA table_info(market_quotes)')}
    if 'product_id' not in columns:
        conn.execute('ALTER TABLE market_quotes ADD COLUMN product_id TEXT')

    # 采集时间拆分：captured_at 只存真实抓取时刻，imported_at 存入库批次时间
    if 'imported_at' not in columns:
        conn.execute('ALTER TABLE market_quotes ADD COLUMN imported_at TEXT')
        conn.execute(
            "UPDATE market_quotes SET imported_at = captured_at "
            "WHERE imported_at IS NULL OR imported_at = ''")
        # 旧数据把整批导入时间当成了每行抓取时间，只保留最新快照行，其余按“历史回补”展示
        conn.execute(
            "UPDATE market_quotes SET captured_at = NULL WHERE data_status <> '盘中'")

    for diid, product_id in LEGACY_PRODUCT_IDS.items():
        conn.execute(
            'UPDATE market_quotes SET product_id = ? WHERE diid = ? '
            'AND (product_id IS NULL OR product_id = "")', (product_id, diid))

    conn.execute(
        'CREATE UNIQUE INDEX IF NOT EXISTS idx_quote_source_product_date '
        'ON market_quotes (source_id, COALESCE(product_id, diid), price_type, quote_date)')

    # 物料类型：网站物料 WB / 系统物料 XT
    material_columns = {
        row['name'] for row in conn.execute('PRAGMA table_info(materials)')}
    if 'material_type' not in material_columns:
        conn.execute(
            "ALTER TABLE materials ADD COLUMN material_type TEXT NOT NULL DEFAULT '通用'")
    conn.execute(
        "UPDATE materials SET code = 'WB00001', material_type = '网站' "
        "WHERE code = 'SP005'")
    conn.execute(
        "UPDATE materials SET code = 'WB00002', material_type = '网站' "
        "WHERE code = 'SP006'")
    for code, name in (
            ('XT00001', '铝'), ('XT00002', '轻杂铝'), ('XT00003', '铝质车底盘'),
            ('XT00004', '废电线'), ('XT00005', '混铝铜废电线')):
        conn.execute(
            "INSERT OR IGNORE INTO materials "
            "(code, name, category, unit, material_type) "
            "VALUES (?, ?, '废金属', '元/吨', '系统')", (code, name))

    # 计价结果补行情来源
    result_columns = {
        row['name'] for row in conn.execute('PRAGMA table_info(calc_results)')}
    if 'source_config_id' not in result_columns:
        conn.execute(
            'ALTER TABLE calc_results ADD COLUMN source_config_id INTEGER '
            'REFERENCES source_material_configs(id)')
    if 'period_start' not in result_columns:
        conn.execute('ALTER TABLE calc_results ADD COLUMN period_start TEXT')
    if 'period_end' not in result_columns:
        conn.execute('ALTER TABLE calc_results ADD COLUMN period_end TEXT')
    conn.execute(
        'UPDATE calc_results SET source_config_id = ('
        'SELECT c.id FROM source_material_configs c '
        'WHERE c.material_id = calc_results.material_id ORDER BY c.id LIMIT 1) '
        'WHERE source_config_id IS NULL')

    # 同步状态：逐物料结果与汇总（JSON 文本）
    sync_columns = {
        row['name'] for row in conn.execute('PRAGMA table_info(sync_state)')}
    if 'last_run_materials' not in sync_columns:
        conn.execute('ALTER TABLE sync_state ADD COLUMN last_run_materials TEXT')
    if 'last_run_summary' not in sync_columns:
        conn.execute('ALTER TABLE sync_state ADD COLUMN last_run_summary TEXT')

    conn.execute(
        "INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (2, ?)",
        (now_text(),))
    conn.execute(
        "INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (3, ?)",
        (now_text(),))
    conn.commit()

    # 已有库补齐网站同步设置、采集配置与计价规则
    from seed import (
        ensure_collect_configs,
        ensure_pricing_rules,
        ensure_source_sync_settings,
    )
    ensure_source_sync_settings(conn)
    ensure_collect_configs(conn)
    ensure_pricing_rules(conn)
    migrate_legacy_results(conn)


def migrate_legacy_results(conn: sqlite3.Connection) -> None:
    """旧结果挂在网站物料上：改挂到该公司系统物料，并按新规则重算售价。"""
    rows = conn.execute(
        'SELECT r.id, r.period_avg, r.source_config_id, r.material_id, m.material_type, '
        'b.run_at FROM calc_results r '
        'JOIN calc_runs b ON b.id = r.run_id '
        'JOIN materials m ON m.id = r.material_id '
        "WHERE m.material_type = '网站'").fetchall()
    if not rows:
        return
    migrated = 0
    for row in rows:
        config_id = row['source_config_id']
        rule = None
        if config_id:
            rule = conn.execute(
                'SELECT * FROM material_pricing_rules WHERE source_config_id = ? '
                "ORDER BY status = '生效' DESC, id LIMIT 1", (config_id,)).fetchone()
        if not rule:
            # 没有对应系统物料规则，删除这条过时结果
            conn.execute('DELETE FROM calc_results WHERE id = ?', (row['id'],))
            continue
        period_avg = float(row['period_avg'] or 0)
        offset = rule['offset_value'] or 0
        coefficient = rule['coefficient'] if rule['coefficient'] is not None else 1
        try:
            run_date = dt.date.fromisoformat((row['run_at'] or '')[:10])
        except ValueError:
            run_date = dt.date.today()
        week_end = run_date - dt.timedelta(days=run_date.isoweekday())
        week_start = week_end - dt.timedelta(days=6)
        conn.execute(
            'UPDATE calc_results SET material_id = ?, template_id = ?, period_start = ?, '
            'period_end = ?, offset_value = ?, coefficient = ?, calc_price = ? WHERE id = ?',
            (rule['material_id'], rule['template_id'], week_start.isoformat(),
             week_end.isoformat(), offset, coefficient,
             round((period_avg + offset) * coefficient, 2), row['id']))
        migrated += 1
    conn.execute(
        'DELETE FROM calc_runs WHERE id NOT IN '
        '(SELECT DISTINCT run_id FROM calc_results) AND run_at < ?', (now_text(),))
    if migrated:
        conn.execute(
            'INSERT INTO operation_logs (log_time, action_type, operator, content, ip) '
            'VALUES (?, ?, ?, ?, ?)',
            (now_text(), '参数修改', '系统',
             '旧计价结果已迁移到公司系统物料口径：重算 %d 条，固定调整值与调价系数按新规则取值'
             % migrated, '127.0.0.1'))
    conn.commit()


def ensure_database() -> None:
    """首次启动时自动建库；已有库则执行结构迁移。"""
    if not os.path.exists(DB_PATH):
        from seed import seed_database  # 延迟导入，避免循环依赖
        seed_database(reset=True, quiet=True)
        return
    conn = connect()
    try:
        init_schema(conn)
        migrate_schema(conn)
    finally:
        conn.close()


def get_db() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def log_operation(conn: sqlite3.Connection, action_type: str, content: str,
                  operator: str = '王莉洁', ip: str = '127.0.0.1') -> Dict:
    log_time = now_text()
    cursor = conn.execute(
        'INSERT INTO operation_logs (log_time, action_type, operator, content, ip) '
        'VALUES (?, ?, ?, ?, ?)',
        (log_time, action_type, operator, content, ip)
    )
    conn.commit()
    return {
        'id': cursor.lastrowid,
        'time': log_time,
        'type': action_type,
        'operator': operator,
        'content': content,
        'ip': ip
    }


def row_to_dict(row: Optional[sqlite3.Row]) -> Dict:
    return dict(row) if row else {}
