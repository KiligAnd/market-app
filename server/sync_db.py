# -*- coding: utf-8 -*-
"""把爬虫最新 CSV / 同步状态增量导入 SQLite。"""
import csv
import os
import sys

import db as database
import seed


def config_rows(conn):
    return conn.execute(
        'SELECT c.*, s.code AS source_code FROM source_material_configs c '
        'JOIN market_sources s ON s.id = c.source_id '
        "WHERE c.status <> '已删除' ORDER BY c.id").fetchall()


def csv_name(config) -> str:
    for item in seed.REAL_QUOTE_FILES:
        if str(item['product_id']) == str(config['product_id']):
            return item['history']
    return 'f139_历史_product_%s.csv' % config['product_id']


def legacy_diid(config) -> str:
    for item in seed.REAL_QUOTE_FILES:
        if str(item['product_id']) == str(config['product_id']):
            return item['diid']
    return str(config['product_id'])


def snap_times() -> dict:
    """快照 CSV 的真实抓取时间，见 db.snapshot_capture_map。"""
    return database.snapshot_capture_map()


def upsert_quotes(conn) -> int:
    state = seed.load_sync_state()
    imported = database.now_text()
    batch_snapshot = state.get('last_snapshot_at') or imported
    captures = snap_times()
    changed = 0

    for config in config_rows(conn):
        csv_path = os.path.join(database.SOURCE_DATA_DIR, csv_name(config))
        if not os.path.exists(csv_path):
            continue

        material_id = config['material_id']
        source_id = config['source_id']
        product_id = str(config['product_id'])
        diid = legacy_diid(config)
        alias = conn.execute(
            'SELECT id, external_name FROM material_aliases WHERE source_id = ? AND material_id = ? '
            'ORDER BY id LIMIT 1', (source_id, material_id)).fetchone()

        rows = list(csv.DictReader(open(csv_path, encoding='utf-8-sig', newline='')))
        if not rows:
            continue
        rows.sort(key=lambda row: row['数据日期'])
        latest_date = rows[-1]['数据日期']
        dates = set()

        for row in rows:
            date_text = (row.get('数据日期') or '').strip()
            if not date_text:
                continue
            dates.add(date_text)
            avg = float(row.get('均价') or 0)
            low, high = seed.parse_range(row.get('价格区间'))
            # 采集配置的 external_name 为空时（例如校验接口曾写回空值），
            # 依次回退到别名名称、CSV 地区/品种/规格/含税，避免台账名称变空。
            display_name = (config['external_name'] or '').strip()
            if not display_name and alias:
                display_name = (alias['external_name'] or '').strip()
            if not display_name:
                parts = [
                    row.get('地区') or config['external_place'],
                    row.get('品种') or config['external_web_name'],
                    row.get('规格型号') or config['external_spec'],
                    row.get('含税') or config['external_tax'],
                ]
                display_name = '-'.join(str(part).strip() for part in parts if str(part or '').strip())
            values = {
                'material_id': material_id,
                'source_id': source_id,
                'alias_id': alias['id'] if alias else None,
                'diid': diid,
                'product_id': product_id,
                'quote_date': date_text,
                'price_type': '市场价格',
                'source_material_name': display_name,
                'raw_text': seed.fmt_range(row.get('价格区间')),
                'raw_low': low,
                'raw_high': high,
                'avg_price': avg,
                'buy_price': float(row.get('买价') or avg),
                'sell_price': float(row.get('卖价') or avg),
                'change_text': row.get('涨跌'),
                'change_value': seed.parse_change(row.get('涨跌')),
                'spec': row.get('规格型号') or config['external_spec'] or '',
                'region': row.get('地区') or config['external_place'] or '',
                'tax': row.get('含税') or config['external_tax'] or '',
                'unit': row.get('单位') or config['external_unit'] or '元/吨',
                'data_status': '盘中' if date_text == latest_date else '已发布',
                'imported_at': imported,
                'source_url': 'https://price.f139.com/history?productId=%s' % product_id,
                'match_status': 'matched',
                'period_avg_override': None,
                'is_demo': 0,
            }
            # 只有快照行有真实抓取时间；历史回补行留空，也不覆盖库里已有的值
            captured = captures.get((product_id, date_text))
            if captured:
                values['captured_at'] = captured
            existing = conn.execute(
                'SELECT id FROM market_quotes WHERE source_id = ? '
                'AND COALESCE(product_id, diid) = ? AND price_type = ? AND quote_date = ?',
                (source_id, product_id, '市场价格', date_text)).fetchone()
            if existing:
                assignments = ', '.join('%s = ?' % key for key in values)
                conn.execute(
                    'UPDATE market_quotes SET %s WHERE id = ?' % assignments,
                    list(values.values()) + [existing['id']])
            else:
                columns = ', '.join(values.keys())
                placeholders = ', '.join('?' for _ in values)
                conn.execute(
                    'INSERT INTO market_quotes (%s) VALUES (%s)' % (columns, placeholders),
                    list(values.values()))
            changed += 1

        conn.execute(
            'UPDATE source_material_configs SET history_rows = ?, last_history_date = ?, '
            'last_snapshot_at = ?, updated_at = ? WHERE id = ?',
            (len(dates), max(dates) if dates else '', batch_snapshot,
             database.now_text(), config['id']))
    return changed


def upsert_sync_state(conn) -> None:
    state = seed.load_sync_state()
    exists = conn.execute('SELECT id FROM sync_state WHERE id = 1').fetchone()
    summary = seed.load_sync_state_extra('last_run_summary')
    materials = seed.load_sync_state_extra('last_run_materials')
    values = (
        state['initialized'], state['initialized_at'], state['init_target_start'],
        state['init_total_windows'], state['init_done_windows'], state['init_next_end'],
        state['last_run_date'], state['last_run_result'], state['last_snapshot_at'],
        state['last_history_date'], state['last_reconcile_date'], state['history_rows'],
        state['api_call_date'], state['api_calls_today'], state['last_error'],
        summary, materials, database.now_text(),
    )
    if exists:
        conn.execute(
            'UPDATE sync_state SET initialized = ?, initialized_at = ?, '
            'init_target_start = ?, init_total_windows = ?, init_done_windows = ?, '
            'init_next_end = ?, last_run_date = ?, last_run_result = ?, '
            'last_snapshot_at = ?, last_history_date = ?, last_reconcile_date = ?, '
            'history_rows = ?, api_call_date = ?, api_calls_today = ?, '
            'last_error = ?, last_run_summary = ?, last_run_materials = ?, '
            'updated_at = ? WHERE id = 1', values)
    else:
        conn.execute(
            'INSERT INTO sync_state (initialized, initialized_at, init_target_start, '
            'init_total_windows, init_done_windows, init_next_end, last_run_date, '
            'last_run_result, last_snapshot_at, last_history_date, last_reconcile_date, '
            'history_rows, api_call_date, api_calls_today, last_error, '
            'last_run_summary, last_run_materials, updated_at) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', values)


def import_api_calls(conn) -> None:
    calls_path = os.path.join(database.SOURCE_DATA_DIR, 'sync_calls.csv')
    if not os.path.exists(calls_path):
        return
    with open(calls_path, 'r', encoding='utf-8-sig', newline='') as fh:
        for row in csv.DictReader(fh):
            conn.execute(
                'INSERT OR IGNORE INTO api_call_logs '
                '(called_at, mode, purpose, endpoint, method, status_code, '
                'elapsed_ms, result) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                (row.get('时间'), row.get('模式'), row.get('用途'), row.get('接口'),
                 row.get('方法'), row.get('状态码'),
                 int(float(row.get('耗时ms') or 0)), row.get('结果')))


def add_sync_log(conn) -> None:
    state = seed.load_sync_state()
    sync_time = state.get('last_snapshot_at')
    if not sync_time:
        return
    exists = conn.execute(
        "SELECT id FROM operation_logs WHERE log_time = ? AND action_type = '行情采集'",
        (sync_time,)).fetchone()
    if exists:
        return
    result = state.get('last_run_result') or 'success'
    summary = state.get('last_run_summary') or {}
    if not state.get('initialized'):
        label = '初始化回补完成'
    elif result in ('failed', 'error'):
        label = '同步失败'
    elif result in ('partial', 'init_partial'):
        label = '同步部分完成'
    elif result == 'skipped':
        label = '同步跳过'
    else:
        label = '每日增量同步完成'
    detail = '历史 %s 个交易日；今日接口调用 %s 次' % (
        state.get('history_rows') or 0, state.get('api_calls_today') or 0)
    if summary:
        detail += '；成功 %s / 部分 %s / 失败 %s / 跳过 %s' % (
            summary.get('success', 0), summary.get('partial', 0),
            summary.get('failed', 0), summary.get('skipped', 0))
    error = state.get('last_error')
    if error and result in ('failed', 'error', 'partial', 'init_partial'):
        detail += '；原因：%s' % error
    conn.execute(
        'INSERT INTO operation_logs (log_time, action_type, operator, content, ip) '
        'VALUES (?, ?, ?, ?, ?)',
        (sync_time, '行情采集', '系统', '%s：%s' % (label, detail), '10.0.1.xx'))


def main() -> int:
    database.ensure_database()
    conn = database.connect()
    database.init_schema(conn)
    with conn:
        changed = upsert_quotes(conn)
        upsert_sync_state(conn)
        import_api_calls(conn)
        add_sync_log(conn)
    total = conn.execute('SELECT COUNT(*) AS n FROM market_quotes').fetchone()['n']
    state = conn.execute('SELECT * FROM sync_state WHERE id = 1').fetchone()
    print('SQLite 增量同步完成：本次处理 %d 条历史行情，库内共 %d 条；状态 %s' % (
        changed, total, state['last_run_result'] if state else 'unknown'))
    conn.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
