# -*- coding: utf-8 -*-
"""建库并导入现有原型数据。"""
import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
from typing import Dict, List, Optional

import db as database

SOURCES = [
    ('fubao', '富宝资讯'),
    ('lingtong', '灵通平台'),
    ('zhongfei', '中废网'),
]

MATERIALS = [
    ('WB00001', '清远机生铝', '废金属', '元/吨', '网站'),
    ('WB00002', '佛山黄杂铜', '废金属', '元/吨', '网站'),
    ('XT00001', '铝', '废金属', '元/吨', '系统'),
    ('XT00002', '轻杂铝', '废金属', '元/吨', '系统'),
    ('XT00003', '铝质车底盘', '废金属', '元/吨', '系统'),
    ('XT00004', '废电线', '废金属', '元/吨', '系统'),
    ('XT00005', '混铝铜废电线', '废金属', '元/吨', '系统'),
]

MAPPINGS = [
    ('WB00001', 'fubao', '机械生铝（机生铝 · Fe6%-8%）', '机生铝 Fe6%-8%',
     '163321', '清远', '不含税', '2026-10-27'),
    ('WB00002', 'fubao', '黄杂铜', '黄杂铜',
     '32105', '佛山', '不含税', '2026-10-27'),
]

# 真实行情 CSV 与数据库物料/别名的对应关系
REAL_QUOTE_FILES = [
    {
        'material': 'WB00001',
        'diid': '163321',
        'product_id': '636',
        'history': 'f139_历史_diid163321.csv',
        'alias': ('fubao', '机械生铝（机生铝 · Fe6%-8%）'),
        'source_name': '清远机械生铝',
        'external_name': '清远-机生铝-Fe6%-8%-不含税',
        'region': '清远',
        'tax': '不含税',
        'spec': 'Fe6%-8%',
    },
    {
        'material': 'WB00002',
        'diid': '32105',
        'product_id': '1591',
        'history': 'f139_历史_diid32105.csv',
        'alias': ('fubao', '黄杂铜'),
        'source_name': '黄杂铜',
        'external_name': '佛山-黄杂铜-不含税',
        'region': '佛山',
        'tax': '不含税',
        'spec': '黄杂铜',
    },
]

# 网站物料采集配置种子（与上面的真实行情一一对应）
COLLECT_CONFIGS = [
    {
        'material': 'WB00001',
        'keyword': '机生铝',
        'province_id': 27,
        'province_name': '广东省',
        'city_id': 57,
        'city_name': '清远市',
        'product_id': '636',
        'variety_id': 168,
        'classify_id': 22,
        'external_name': '清远-机生铝-Fe6%-8%-不含税',
        'external_web_name': '机生铝',
        'external_place': '清远',
        'external_spec': 'Fe6%-8%',
        'external_tax': '不含税',
        'external_unit': '元/吨',
        'external_org': '富宝废旧',
        'history_days': 365,
        'initialized': 1,
        'history_rows': 288,
        'last_history_date': '2026-10-27',
        'status': '启用',
    },
    {
        'material': 'WB00002',
        'keyword': '黄杂铜',
        'province_id': 27,
        'province_name': '广东省',
        'city_id': 51,
        'city_name': '佛山市',
        'product_id': '1591',
        'variety_id': 482,
        'classify_id': 22,
        'external_name': '佛山-黄杂铜-不含税',
        'external_web_name': '黄杂铜',
        'external_place': '佛山',
        'external_spec': '',
        'external_tax': '不含税',
        'external_unit': '元/吨',
        'external_org': '富宝废旧',
        'history_days': 30,
        'initialized': 0,
        'history_rows': 1,
        'last_history_date': '2026-10-27',
        'status': '启用',
    },
]


# 网站级同步设置：仅富宝已接入自动解析，其余网站默认关闭
SOURCE_SYNC_SETTINGS = [
    ('fubao', 1, 1, 'daily', 20),
    ('lingtong', 0, 0, 'manual', 0),
    ('zhongfei', 0, 0, 'manual', 0),
]


def ensure_source_sync_settings(conn) -> None:
    """幂等补齐网站级同步设置；已有设置不覆盖。"""
    now = database.now_text()
    for code, enabled, supported, mode, cap in SOURCE_SYNC_SETTINGS:
        source = conn.execute(
            'SELECT id FROM market_sources WHERE code = ?', (code,)).fetchone()
        if not source:
            continue
        conn.execute(
            'INSERT OR IGNORE INTO source_sync_settings '
            '(source_id, enabled, auto_supported, sync_mode, daily_cap, updated_at) '
            'VALUES (?, ?, ?, ?, ?, ?)',
            (source['id'], enabled, supported, mode, cap, now))
    conn.commit()


def ensure_collect_configs(conn) -> None:
    """幂等补齐两条内置采集配置；已有库升级时也会调用。"""
    now = database.now_text()
    source = conn.execute(
        "SELECT id FROM market_sources WHERE code = 'fubao'").fetchone()
    if not source:
        return
    for item in COLLECT_CONFIGS:
        material = conn.execute(
            'SELECT id FROM materials WHERE code = ?', (item['material'],)).fetchone()
        if not material:
            continue
        existing = conn.execute(
            'SELECT id FROM source_material_configs WHERE source_id = ? AND product_id = ?',
            (source['id'], item['product_id'])).fetchone()
        if existing:
            conn.execute(
                'UPDATE source_material_configs SET '
                'material_id = COALESCE(material_id, ?), '
                'province_id = COALESCE(province_id, ?), '
                'province_name = COALESCE(province_name, ?), '
                'city_id = COALESCE(city_id, ?), '
                'city_name = COALESCE(city_name, ?), '
                'updated_at = ? WHERE id = ?',
                (material['id'], item['province_id'], item['province_name'],
                 item['city_id'], item['city_name'], now, existing['id']))
            continue
        conn.execute(
            'INSERT INTO source_material_configs '
            '(source_id, keyword, province_id, province_name, city_id, city_name, '
            'product_id, variety_id, classify_id, external_name, external_web_name, '
            'external_place, external_spec, external_tax, external_unit, external_org, '
            'price_type, material_id, status, history_days, initialized, history_rows, '
            'last_history_date, created_at, updated_at) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (source['id'], item['keyword'], item['province_id'], item['province_name'],
             item['city_id'], item['city_name'], item['product_id'], item['variety_id'],
             item['classify_id'], item['external_name'], item['external_web_name'],
             item['external_place'], item['external_spec'], item['external_tax'],
             item['external_unit'], item['external_org'], '市场价格', material['id'],
             item['status'], item['history_days'], item['initialized'],
             item['history_rows'], item['last_history_date'], now, now))
    conn.commit()

TEMPLATES = [
    ('TPL01', '固定价模板', '直接使用人工录入售价', ['固定售价']),
    ('TPL02', '周期均价+偏移系数模板', '执行价 =（周期均价 ± 偏移）× 系数',
     ['多源均价', '统计周期', '固定偏移', '调价系数']),
    ('TPL03', '跨期价差联动模板', '本期价 = 本期均价 - 上期均价 + 上期售价',
     ['多源均价', '统计周期', '上期价差', '上期售价联动']),
]

# 旧模型（单物料定价参数）已停用；新模型见 PRICING_RULES
PARAMS = []

# 网站物料 → 公司系统物料计价规则
# (网站物料编码, productId, 系统物料编码, 模板, 固定调整值, 调价系数)
PRICING_RULES = [
    ('WB00001', '636', 'XT00001', 'TPL02', 0, 1.03),
    ('WB00001', '636', 'XT00002', 'TPL02', -842, 1.03),
    ('WB00001', '636', 'XT00003', 'TPL02', -4500, 1.03),
    ('WB00002', '1591', 'XT00004', 'TPL02', -5800, 1.18),
    ('WB00002', '1591', 'XT00005', 'TPL02', -11802, 1.18),
]

SCHEDULES = [
    ('废金属周度计价', '每周一 08:00', '运行中', '2026-10-27 08:00', '2026-11-02 08:00'),
]

BATCHES = []

RESULTS = []

LOGS = [
    ('2026-10-29 10:20:08', '参数修改', '王莉洁',
     '物料计价规则切换：网站物料 WB00001 清远机生铝 → 系统物料 XT00001 铝（调整值0）、'
     'XT00002 轻杂铝（-842）、XT00003 铝质车底盘（-4500），统一调价系数1.03'),
    ('2026-10-27 10:16:31', '行情采集', '系统',
     '富宝资讯「清远机械生铝」同步完成：快照1条、历史288个交易日（2025-10-27 ~ 2026-10-27）'),
    ('2026-10-27 10:15:40', '物料映射变更', '王莉洁',
     '新增WB00001清远机生铝 ↔ 富宝资讯「机械生铝」映射关系'),
]


def ensure_pricing_rules(conn) -> None:
    """幂等补齐「网站物料 → 公司系统物料」计价规则，并停用旧参数。"""
    now = database.now_text()
    template = conn.execute(
        "SELECT id FROM pricing_templates WHERE code = 'TPL02'").fetchone()
    if not template:
        return
    for material_code, product_id, target_code, template_code, offset, coeff in PRICING_RULES:
        config = conn.execute(
            'SELECT id FROM source_material_configs WHERE product_id = ? '
            "AND status <> '已删除' ORDER BY id LIMIT 1", (product_id,)).fetchone()
        target = conn.execute(
            'SELECT id FROM materials WHERE code = ?', (material_code,)).fetchone()
        rule_material = conn.execute(
            'SELECT id FROM materials WHERE code = ?', (target_code,)).fetchone()
        if not config or not target or not rule_material:
            continue
        exists = conn.execute(
            'SELECT id FROM material_pricing_rules WHERE source_config_id = ? '
            'AND material_id = ? AND version = 1',
            (config['id'], rule_material['id'])).fetchone()
        if exists:
            continue
        conn.execute(
            'INSERT INTO material_pricing_rules '
            '(source_config_id, material_id, template_id, period_type, offset_value, '
            'coefficient, status, version, effective_from, updated_at) '
            "VALUES (?, ?, ?, '周', ?, ?, '生效', 1, ?, ?)",
            (config['id'], rule_material['id'], template['id'], offset, coeff,
             dt.date.today().isoformat(), now))
    # 旧模型参数统一停用，避免与新规则并存
    conn.execute(
        "UPDATE pricing_params SET status = '停用', updated_at = ? WHERE status = '生效'",
        (now,))
    conn.commit()


DEMO_QUOTES = []

DEFAULT_SYNC_STATE = {
    'initialized': 1,
    'initialized_at': '2026-10-27 15:43:00',
    'init_target_start': '2025-10-27',
    'init_total_windows': 7,
    'init_done_windows': 7,
    'init_next_end': '2025-10-26',
    'last_run_date': '2026-10-27',
    'last_run_result': 'skipped',
    'last_snapshot_at': '2026-10-27 15:43:25',
    'last_history_date': '2026-10-27',
    'last_reconcile_date': None,
    'history_rows': 288,
    'api_call_date': '2026-10-27',
    'api_calls_today': 2,
    'last_error': None,
}


def fmt_range(text: str) -> str:
    return re.sub(r'\d+(?:\.\d+)?', lambda m: format(int(round(float(m.group()))), ','), text or '')


def parse_range(text: str):
    nums = [float(n) for n in re.findall(r'\d+(?:\.\d+)?', text or '')]
    if len(nums) >= 2:
        return nums[0], nums[1]
    if len(nums) == 1:
        return nums[0], nums[0]
    return None, None


def parse_change(text: str) -> Optional[float]:
    text = (text or '').strip()
    if not text or text == '平':
        return 0
    match = re.search(r'([+-]?\d+(?:\.\d+)?)', text)
    if not match:
        return None
    value = float(match.group(1))
    if text.startswith('跌'):
        return -value
    return value


def load_sync_state() -> Dict:
    path = os.path.join(database.SOURCE_DATA_DIR, 'sync_state.json')
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
            return {
                'initialized': 1 if data.get('initialized') else 0,
                'initialized_at': data.get('initialized_at'),
                'init_target_start': data.get('init_target_start'),
                'init_total_windows': int(data.get('init_total_windows') or 0),
                'init_done_windows': int(data.get('init_done_windows') or 0),
                'init_next_end': data.get('init_next_end'),
                'last_run_date': data.get('last_run_date'),
                'last_run_result': data.get('last_run_result'),
                'last_snapshot_at': data.get('last_snapshot_at'),
                'last_history_date': data.get('last_history_date'),
                'last_reconcile_date': data.get('last_reconcile_date'),
                'history_rows': int(data.get('history_rows') or 0),
                'api_call_date': data.get('api_call_date'),
                'api_calls_today': int(data.get('api_calls_today') or 0),
                'last_error': data.get('last_error'),
            }
        except (OSError, ValueError):
            pass
    return dict(DEFAULT_SYNC_STATE)


def load_sync_state_extra(key: str) -> str:
    """读取同步状态 JSON 的扩展字段（逐物料结果/汇总），返回 JSON 文本。"""
    path = os.path.join(database.SOURCE_DATA_DIR, 'sync_state.json')
    if not os.path.exists(path):
        return ''
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return ''
    value = data.get(key)
    if value is None:
        return ''
    return json.dumps(value, ensure_ascii=False)


def seed_database(reset: bool = False, quiet: bool = False) -> None:
    if reset and os.path.exists(database.DB_PATH):
        for suffix in ('', '-wal', '-shm'):
            try:
                os.remove(database.DB_PATH + suffix)
            except FileNotFoundError:
                pass
    conn = database.connect()
    database.init_schema(conn)
    database.migrate_schema(conn)
    existing = conn.execute('SELECT COUNT(*) AS n FROM materials').fetchone()['n']
    if existing and not reset:
        if not quiet:
            print('数据库已有数据；如需重建请执行 python seed.py --reset')
        conn.close()
        return

    with conn:
        source_ids = {}
        for code, name in SOURCES:
            cursor = conn.execute(
                'INSERT INTO market_sources (code, name) VALUES (?, ?)', (code, name))
            source_ids[code] = cursor.lastrowid

        material_ids = {}
        for code, name, category, unit, material_type in MATERIALS:
            conn.execute(
                'INSERT OR IGNORE INTO materials (code, name, category, unit, material_type) '
                'VALUES (?, ?, ?, ?, ?)',
                (code, name, category, unit, material_type))
            row = conn.execute(
                'SELECT id FROM materials WHERE code = ?', (code,)).fetchone()
            material_ids[code] = row['id']

        alias_ids = {}
        for material_code, source_code, external, spec, diid, region, tax, created in MAPPINGS:
            cursor = conn.execute(
                'INSERT INTO material_aliases '
                '(material_id, source_id, external_name, external_spec, diid, region, tax, '
                'unit, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (material_ids[material_code], source_ids[source_code], external, spec, diid,
                 region, tax, '元/吨', '已匹配', created))
            alias_ids[(source_code, external)] = cursor.lastrowid

        template_ids = {}
        for code, name, formula, factors in TEMPLATES:
            now = database.now_text()
            cursor = conn.execute(
                'INSERT INTO pricing_templates (code, name, formula, created_at, updated_at) '
                'VALUES (?, ?, ?, ?, ?)', (code, name, formula, now, now))
            template_ids[code] = cursor.lastrowid
            for order, factor in enumerate(factors):
                conn.execute(
                    'INSERT INTO pricing_template_factors (template_id, factor, sort_order) '
                    'VALUES (?, ?, ?)', (cursor.lastrowid, factor, order))

        for material_code, template_code, period, offset, coeff, status, version, srcs in PARAMS:
            cursor = conn.execute(
                'INSERT INTO pricing_params '
                '(material_id, template_id, period_type, offset_value, coefficient, status, '
                'version, effective_from, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (material_ids[material_code], template_ids[template_code], period, offset,
                 coeff, status, version, '2026-10-01', database.now_text()))
            for source_code in srcs:
                conn.execute(
                    'INSERT INTO pricing_param_sources (param_id, source_id) VALUES (?, ?)',
                    (cursor.lastrowid, source_ids[source_code]))

        for name, cycle, status, last_run, next_run in SCHEDULES:
            conn.execute(
                'INSERT INTO calc_schedules (name, cycle, status, last_run_at, next_run_at) '
                'VALUES (?, ?, ?, ?, ?)', (name, cycle, status, last_run, next_run))

        run_ids = {}
        for batch_no, run_at, total, success, failed, status in BATCHES:
            cursor = conn.execute(
                'INSERT INTO calc_runs '
                '(batch_no, run_at, total_count, success_count, fail_count, status) '
                'VALUES (?, ?, ?, ?, ?, ?)',
                (batch_no, run_at, total, success, failed, status))
            run_ids[batch_no] = cursor.lastrowid

        for batch_no, material_code, template_code, period_avg, offset, coeff, calc_price, sync_status, review_status, reviewer, reviewed_at in RESULTS:
            conn.execute(
                'INSERT INTO calc_results '
                '(run_id, material_id, template_id, period_avg, offset_value, coefficient, '
                'calc_price, sync_status, review_status, reviewer, reviewed_at, created_at) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (run_ids[batch_no], material_ids[material_code], template_ids[template_code],
                 period_avg, offset, coeff, calc_price, sync_status, review_status,
                 reviewer, reviewed_at, '2026-10-27 10:20:08'))

        for log_time, action_type, operator, content in LOGS:
            conn.execute(
                'INSERT INTO operation_logs (log_time, action_type, operator, content, ip) '
                'VALUES (?, ?, ?, ?, ?)', (log_time, action_type, operator, content, '10.0.1.xx'))

        state = load_sync_state()
        conn.execute(
            'INSERT INTO sync_state '
            '(id, initialized, initialized_at, init_target_start, init_total_windows, '
            'init_done_windows, init_next_end, last_run_date, last_run_result, '
            'last_snapshot_at, last_history_date, last_reconcile_date, history_rows, '
            'api_call_date, api_calls_today, last_error, updated_at) '
            'VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (state['initialized'], state['initialized_at'], state['init_target_start'],
             state['init_total_windows'], state['init_done_windows'], state['init_next_end'],
             state['last_run_date'], state['last_run_result'], state['last_snapshot_at'],
             state['last_history_date'], state['last_reconcile_date'], state['history_rows'],
             state['api_call_date'], state['api_calls_today'], state['last_error'],
             database.now_text()))

        calls_path = os.path.join(database.SOURCE_DATA_DIR, 'sync_calls.csv')
        if os.path.exists(calls_path):
            with open(calls_path, 'r', encoding='utf-8-sig', newline='') as fh:
                for row in csv.DictReader(fh):
                    conn.execute(
                        'INSERT INTO api_call_logs '
                        '(called_at, mode, purpose, endpoint, method, status_code, '
                        'elapsed_ms, result) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                        (row.get('时间'), row.get('模式'), row.get('用途'), row.get('接口'),
                         row.get('方法'), row.get('状态码'),
                         int(float(row.get('耗时ms') or 0)), row.get('结果')))

        insert_real_quotes(conn, source_ids, material_ids, alias_ids)
        insert_demo_quotes(conn, source_ids, material_ids, alias_ids)
        insert_market_log(conn)
        ensure_source_sync_settings(conn)
        ensure_collect_configs(conn)
        ensure_pricing_rules(conn)

    count = conn.execute('SELECT COUNT(*) AS n FROM market_quotes').fetchone()['n']
    if not quiet:
        print('数据库已初始化：%s' % database.DB_PATH)
        print('行情条数：%d（真实 + 演示）' % count)
    conn.close()


def insert_real_quotes(conn, source_ids, material_ids, alias_ids) -> None:
    imported = database.now_text()
    captures = database.snapshot_capture_map()
    for config in REAL_QUOTE_FILES:
        csv_path = os.path.join(database.SOURCE_DATA_DIR, config['history'])
        if not os.path.exists(csv_path):
            continue
        rows = list(csv.DictReader(open(csv_path, encoding='utf-8-sig', newline='')))
        if not rows:
            continue
        rows.sort(key=lambda r: r['数据日期'])
        latest_date = rows[-1]['数据日期']
        alias_id = alias_ids.get(config['alias'])
        for row in rows:
            date_text = (row.get('数据日期') or '').strip()
            avg = float(row.get('均价') or 0)
            low, high = parse_range(row.get('价格区间'))
            alias_key = config['alias']
            # 只有快照行有真实抓取时间，历史回补行留空
            snap_time = captures.get((str(config['product_id']), date_text))
            conn.execute(
                'INSERT INTO market_quotes '
                '(material_id, source_id, alias_id, diid, product_id, quote_date, price_type, '
                'source_material_name, raw_text, raw_low, raw_high, avg_price, buy_price, '
                'sell_price, change_text, change_value, spec, region, tax, unit, data_status, '
                'captured_at, imported_at, source_url, match_status, period_avg_override, is_demo) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (material_ids[config['material']], source_ids[alias_key[0]],
                 alias_id, config['diid'], config['product_id'], date_text, '市场价格',
                 config.get('external_name') or config['source_name'],
                 fmt_range(row.get('价格区间')), low, high, avg,
                 float(row.get('买价') or avg), float(row.get('卖价') or avg),
                 row.get('涨跌'), parse_change(row.get('涨跌')),
                 row.get('规格型号') or config['spec'],
                 row.get('地区') or config['region'],
                 row.get('含税') or config['tax'],
                 row.get('单位') or '元/吨',
                 '盘中' if date_text == latest_date else '已发布',
                 snap_time, imported,
                 'https://price.f139.com/history?productId=%s' % config['product_id'],
                 'matched', None, 0))


def insert_demo_quotes(conn, source_ids, material_ids, alias_ids) -> None:
    for item in DEMO_QUOTES:
        material_id = material_ids.get(item['material']) if item['material'] else None
        alias_id = alias_ids.get(item['alias_key']) if item['alias_key'] else None
        conn.execute(
            'INSERT INTO market_quotes '
            '(material_id, source_id, alias_id, diid, quote_date, price_type, '
            'source_material_name, raw_text, raw_low, raw_high, avg_price, buy_price, '
            'sell_price, change_text, change_value, spec, region, tax, unit, data_status, '
             'captured_at, imported_at, source_url, match_status, period_avg_override, is_demo) '
             'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
             (material_id, source_ids[item['source']], alias_id, None, item['date'],
              '市场价格', item['name'], item['raw'], None, None, item['avg'], None, None,
              '平', 0, None, None, None, '元/吨', '已发布', item['captured'], item['captured'],
              None, item['status'], item['period'], 1))


def insert_market_log(conn) -> None:
    conn.execute(
        'INSERT INTO operation_logs (log_time, action_type, operator, content, ip) '
        'VALUES (?, ?, ?, ?, ?)',
        ('2026-10-27 15:43:25', '行情采集', '系统',
         '每日增量同步完成：快照1条，历史288个交易日；今日接口调用2次', '10.0.1.xx'))


def main() -> int:
    parser = argparse.ArgumentParser(description='初始化 market.db')
    parser.add_argument('--reset', action='store_true', help='删除并重建数据库')
    args = parser.parse_args()
    seed_database(reset=args.reset)
    return 0


if __name__ == '__main__':
    sys.exit(main())
