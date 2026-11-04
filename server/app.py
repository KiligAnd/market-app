# -*- coding: utf-8 -*-
"""FastAPI + SQLite 后端：为 Vue 原型提供数据与写操作。"""
import calendar
import datetime as dt
import json
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import credentials
import db as database
from seed import seed_database

sys.path.insert(0, database.PROJECT_ROOT)
import f139_aluminum_price as f139  # noqa: E402
from f139_sync_guard import CALL_LOG, DailyLimitReached, RequestGate, SyncState  # noqa: E402

app = FastAPI(title='商品行情计价系统 API', version='1.1.0')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://127.0.0.1:5173', 'http://localhost:5173'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.on_event('startup')
def on_startup() -> None:
    database.ensure_database()
    # 已保存过自动续期账号时，把凭据注入当前进程，供 f139 自动登录使用
    credentials.load_into_env()


# ------------------------------------------------------------------ 通用转换
def time_part(value: Optional[str]) -> str:
    value = value or ''
    return value[11:19] if len(value) >= 19 else value


def mapping_item(conn: sqlite3.Connection, rule_id: int) -> dict:
    """映射行 = 计价规则行：BIP系统物料 ↔ 网站爬虫采集物料。"""
    row = conn.execute(
        'SELECT r.id, r.offset_value, r.coefficient, r.status, r.updated_at, '
        'm.code AS material_code, m.name AS material_name, m.material_type, '
        'c.id AS source_config_id, c.keyword, c.external_name, c.external_web_name, '
        'c.external_place, c.external_spec, c.external_tax, c.external_unit, '
        'c.external_org, c.product_id, c.province_name, c.city_name, '
        'c.status AS config_status, s.name AS source_name, s.code AS source_code '
        'FROM material_pricing_rules r '
        'JOIN materials m ON m.id = r.material_id '
        'JOIN source_material_configs c ON c.id = r.source_config_id '
        'JOIN market_sources s ON s.id = c.source_id '
        'WHERE r.id = ?', (rule_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail='映射不存在')
    return {
        'id': row['id'],
        'materialCode': row['material_code'],
        'materialName': row['material_name'],
        'materialType': row['material_type'],
        'source': row['source_name'],
        'sourceCode': row['source_code'],
        'sourceConfigId': row['source_config_id'],
        'configStatus': row['config_status'],
        'keyword': row['keyword'] or '',
        'externalName': row['external_name'] or '',
        'webName': row['external_web_name'] or '',
        'place': row['external_place'] or '',
        'spec': row['external_spec'] or '',
        'tax': row['external_tax'] or '',
        'unit': row['external_unit'] or '元/吨',
        'org': row['external_org'] or '',
        'productId': row['product_id'] or '',
        'provinceName': row['province_name'] or '',
        'cityName': row['city_name'] or '',
        'offset': row['offset_value'],
        'coefficient': row['coefficient'],
        'status': row['status'],
        'updatedAt': row['updated_at'],
    }


def param_item(conn: sqlite3.Connection, param_id: int) -> dict:
    row = conn.execute(
        'SELECT p.id, m.code AS material_code, m.name AS material_name, '
        't.code AS template_code, p.period_type, p.offset_value, p.coefficient, '
        'p.status, p.version '
        'FROM pricing_params p '
        'JOIN materials m ON m.id = p.material_id '
        'JOIN pricing_templates t ON t.id = p.template_id '
        'WHERE p.id = ?', (param_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail='定价参数不存在')
    sources = conn.execute(
        'SELECT s.name FROM pricing_param_sources ps '
        'JOIN market_sources s ON s.id = ps.source_id '
        'WHERE ps.param_id = ? ORDER BY s.id', (param_id,)).fetchall()
    return {
        'id': row['id'],
        'materialCode': row['material_code'],
        'materialName': row['material_name'],
        'templateCode': row['template_code'],
        'sources': [item['name'] for item in sources],
        'period': row['period_type'],
        'offset': row['offset_value'],
        'coefficient': row['coefficient'],
        'status': row['status'],
        'version': row['version'],
    }


def template_item(conn: sqlite3.Connection, template_id: int) -> dict:
    row = conn.execute(
        'SELECT id, code, name, formula, enabled FROM pricing_templates WHERE id = ?',
        (template_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail='模板不存在')
    factors = conn.execute(
        'SELECT factor FROM pricing_template_factors WHERE template_id = ? ORDER BY sort_order',
        (template_id,)).fetchall()
    return {
        'id': row['id'],
        'code': row['code'],
        'name': row['name'],
        'formula': row['formula'],
        'factors': [item['factor'] for item in factors],
        'enabled': bool(row['enabled']),
    }


def result_item(conn: sqlite3.Connection, result_id: int) -> dict:
    row = conn.execute(
        'SELECT r.id, b.batch_no, m.code AS material_code, m.name AS material_name, '
        'm.material_type, t.code AS template_code, r.period_start, r.period_end, '
        'r.period_avg, r.offset_value, r.coefficient, '
        'r.calc_price, r.sync_status, r.review_status, r.reviewer, r.reviewed_at, '
        'r.reject_reason, sm.code AS source_material_code, '
        'sm.name AS source_material_name, s.name AS source_name '
        'FROM calc_results r '
        'JOIN calc_runs b ON b.id = r.run_id '
        'JOIN materials m ON m.id = r.material_id '
        'JOIN pricing_templates t ON t.id = r.template_id '
        'LEFT JOIN source_material_configs c ON c.id = r.source_config_id '
        'LEFT JOIN materials sm ON sm.id = c.material_id '
        'LEFT JOIN market_sources s ON s.id = c.source_id '
        'WHERE r.id = ?', (result_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail='计价结果不存在')
    return {
        'id': row['id'],
        'batchId': row['batch_no'],
        'materialCode': row['material_code'],
        'materialName': row['material_name'],
        'materialType': row['material_type'],
        'sourceMaterialCode': row['source_material_code'] or '',
        'sourceMaterialName': row['source_material_name'] or '',
        'source': row['source_name'] or '',
        'templateCode': row['template_code'],
        'periodStart': row['period_start'] or '',
        'periodEnd': row['period_end'] or '',
        'periodAvg': row['period_avg'],
        'offset': row['offset_value'],
        'coefficient': row['coefficient'],
        'calcPrice': row['calc_price'],
        'syncStatus': row['sync_status'],
        'reviewStatus': row['review_status'],
        'reviewer': row['reviewer'] or '',
        'reviewedAt': row['reviewed_at'] or '',
        'rejectReason': row['reject_reason'] or '',
    }


# ------------------------------------------------------------------ 计价规则
def last_complete_week(day: Optional[dt.date] = None):
    """返回上一个完整周（周一至周日）。"""
    day = day or dt.date.today()
    sunday = day - dt.timedelta(days=day.isoweekday())
    return sunday - dt.timedelta(days=6), sunday


def week_average(conn, config, start: dt.date, end: dt.date) -> dict:
    """统计完整周（周一至周日）均价；只有周一至周五的报价参与计算。"""
    where = ['material_id = ?', 'source_id = ?', 'is_demo = 0',
             'quote_date BETWEEN ? AND ?',
             "CAST(strftime('%w', quote_date) AS INTEGER) BETWEEN 1 AND 5"]
    params = [config['material_id'], config['source_id'],
              start.isoformat(), end.isoformat()]
    if config['product_id']:
        where.append('product_id = ?')
        params.append(str(config['product_id']))
    row = conn.execute(
        'SELECT AVG(avg_price) AS avg_price, COUNT(*) AS days, '
        'MIN(quote_date) AS first_date, MAX(quote_date) AS last_date '
        'FROM market_quotes WHERE ' + ' AND '.join(where), params).fetchone()
    average = row['avg_price']
    return {
        'periodStart': start.isoformat(),
        'periodEnd': end.isoformat(),
        'average': round(float(average), 2) if average is not None else None,
        'days': int(row['days'] or 0),
        'firstDate': row['first_date'] or '',
        'lastDate': row['last_date'] or '',
    }


def calc_price(period_avg, offset, coefficient, template_code: str = 'TPL02'):
    """计算售价：固定调整值 0 表示不增不减，结果保留两位小数。"""
    if period_avg is None:
        return None
    if template_code == 'TPL01':
        return round(float(offset or 0), 2)
    offset = float(offset or 0)
    coefficient = float(coefficient) if coefficient is not None else 1.0
    return round((float(period_avg) + offset) * coefficient, 2)


def pricing_rule_item(conn: sqlite3.Connection, rule_id: int, week: dict = None) -> dict:
    row = conn.execute(
        'SELECT r.id, r.source_config_id, r.period_type, r.offset_value, r.coefficient, '
        'r.status, r.version, r.effective_from, r.updated_at, '
        'm.code AS material_code, m.name AS material_name, '
        'm.material_type, t.code AS template_code, '
        'c.material_id AS source_material_id, c.source_id AS source_id, '
        'c.product_id, c.external_name, c.province_name, c.city_name, '
        's.name AS source_name, sm.code AS source_material_code, '
        'sm.name AS source_material_name '
        'FROM material_pricing_rules r '
        'JOIN materials m ON m.id = r.material_id '
        'JOIN pricing_templates t ON t.id = r.template_id '
        'JOIN source_material_configs c ON c.id = r.source_config_id '
        'JOIN market_sources s ON s.id = c.source_id '
        'LEFT JOIN materials sm ON sm.id = c.material_id '
        'WHERE r.id = ?', (rule_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail='计价规则不存在')
    if week is None:
        start, end = last_complete_week()
        week = week_average(conn, {
            'material_id': row['source_material_id'],
            'source_id': row['source_id'],
            'product_id': row['product_id'],
        }, start, end)
    price = calc_price(week['average'], row['offset_value'], row['coefficient'],
                       row['template_code'])
    return {
        'id': row['id'],
        'sourceConfigId': row['source_config_id'],
        'sourceMaterialCode': row['source_material_code'] or '',
        'sourceMaterialName': row['source_material_name'] or '',
        'source': row['source_name'],
        'productId': row['product_id'] or '',
        'externalName': row['external_name'] or '',
        'region': '%s%s' % (row['province_name'] or '', row['city_name'] or ''),
        'materialCode': row['material_code'],
        'materialName': row['material_name'],
        'materialType': row['material_type'],
        'templateCode': row['template_code'],
        'period': row['period_type'],
        'offset': row['offset_value'],
        'coefficient': row['coefficient'],
        'status': row['status'],
        'version': row['version'],
        'updatedAt': row['updated_at'],
        'periodStart': week['periodStart'],
        'periodEnd': week['periodEnd'],
        'periodAvg': week['average'],
        'quoteDays': week['days'],
        'previewPrice': price,
    }


def query_pricing_rules(conn) -> dict:
    """按网站物料分组返回计价规则，并给出上一完整周均价与预览售价。"""
    start, end = last_complete_week()
    configs = conn.execute(
        'SELECT c.id, c.source_id, c.product_id, c.external_name, c.status, '
        'c.material_id, c.province_name, c.city_name, c.keyword, '
        'c.last_history_date, s.name AS source_name, s.code AS source_code, '
        'm.code AS material_code, m.name AS material_name '
        'FROM source_material_configs c '
        'JOIN market_sources s ON s.id = c.source_id '
        'LEFT JOIN materials m ON m.id = c.material_id '
        "WHERE c.status <> '已删除' ORDER BY c.id").fetchall()

    groups = []
    items = []
    for config in configs:
        week = week_average(conn, config, start, end)
        rules = conn.execute(
            'SELECT id FROM material_pricing_rules WHERE source_config_id = ? '
            'ORDER BY id', (config['id'],)).fetchall()
        rule_items = [pricing_rule_item(conn, row['id'], week) for row in rules]
        items.extend(rule_items)
        groups.append({
            'sourceConfigId': config['id'],
            'sourceCode': config['source_code'],
            'source': config['source_name'],
            'productId': config['product_id'] or '',
            'externalName': config['external_name'] or '',
            'keyword': config['keyword'] or '',
            'region': '%s%s' % (config['province_name'] or '', config['city_name'] or ''),
            'provinceName': config['province_name'] or '',
            'cityName': config['city_name'] or '',
            'status': config['status'],
            'sourceMaterialCode': config['material_code'] or '',
            'sourceMaterialName': config['material_name'] or '',
            'lastHistoryDate': config['last_history_date'] or '',
            'periodStart': week['periodStart'],
            'periodEnd': week['periodEnd'],
            'periodAvg': week['average'],
            'quoteDays': week['days'],
            'rules': rule_items,
        })
    return {'groups': groups, 'items': items}



def schedule_item(conn: sqlite3.Connection, schedule_id: int) -> dict:
    row = conn.execute(
        'SELECT id, name, cycle, status, last_run_at, next_run_at FROM calc_schedules '
        'WHERE id = ?', (schedule_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail='任务不存在')
    return {
        'id': row['id'],
        'name': row['name'],
        'cycle': row['cycle'],
        'status': row['status'],
        'lastRun': row['last_run_at'],
        'nextRun': row['next_run_at'],
    }


# ------------------------------------------------------------------ 查询
def query_sources(conn) -> List[dict]:
    rows = conn.execute('SELECT id, code, name FROM market_sources ORDER BY id').fetchall()
    return [{'id': row['id'], 'code': row['code'], 'name': row['name']} for row in rows]


def query_materials(conn) -> List[dict]:
    rows = conn.execute(
        'SELECT code, name, category, unit, material_type '
        'FROM materials ORDER BY material_type, id').fetchall()
    return [{
        'code': row['code'],
        'name': row['name'],
        'category': row['category'],
        'unit': row['unit'],
        'materialType': row['material_type'],
    } for row in rows]


def query_mappings(conn) -> List[dict]:
    """映射表数据源：material_pricing_rules（系统物料 ↔ 爬虫物料 对照行）。"""
    rows = conn.execute(
        'SELECT r.id FROM material_pricing_rules r '
        'JOIN source_material_configs c ON c.id = r.source_config_id '
        "WHERE c.status <> '已删除' "
        'ORDER BY r.source_config_id, r.id').fetchall()
    return [mapping_item(conn, row['id']) for row in rows]


QUOTE_SELECT = (
    'SELECT q.id, m.code AS material_code, m.name AS material_name, '
    'm.category AS category, s.name AS source, q.source_material_name, '
    'q.quote_date, q.raw_text, q.avg_price, q.change_text, q.captured_at, '
    'q.imported_at, q.match_status, q.period_avg_override, v.rolling_7d_avg, q.is_demo '
    'FROM market_quotes q '
    'JOIN market_sources s ON s.id = q.source_id '
    'LEFT JOIN materials m ON m.id = q.material_id '
    'LEFT JOIN v_quote_rolling v ON v.id = q.id '
)

PAGE_SIZES = (10, 20, 50, 100)


def quote_item(row) -> dict:
    matched = row['match_status'] == 'matched'
    period_avg = None
    if matched:
        period_avg = row['period_avg_override']
        if period_avg is None:
            period_avg = row['rolling_7d_avg']
    return {
        'id': row['id'],
        'materialCode': row['material_code'] or '',
        'materialName': row['material_name'] or '',
        'category': row['category'] or '废金属',
        'source': row['source'],
        'externalName': row['source_material_name'] or '',
        'systemName': (
            '%s（%s）' % (row['material_name'], row['material_code'])
            if row['material_code'] else '—'
        ),
        'date': row['quote_date'],
        'avg': row['avg_price'],
        'range': row['raw_text'] or '',
        'change': row['change_text'] or '—',
        'periodAvg': period_avg,
        'capturedAt': time_part(row['captured_at']),
        'importedAt': time_part(row['imported_at']),
        'status': '成功' if matched else '未匹配',
        'matchStatus': row['match_status'],
        'isDemo': bool(row['is_demo']),
    }


def query_quotes(conn) -> List[dict]:
    rows = conn.execute(
        QUOTE_SELECT + 'ORDER BY q.quote_date DESC, q.id ASC').fetchall()
    return [quote_item(row) for row in rows]


def quote_filters(source: str, category: str, start_date: str,
                  end_date: str, keyword: str):
    """构造分页查询的 WHERE 子句和参数。"""
    clauses = []
    params: List = []
    if source:
        clauses.append('(s.code = ? OR s.name = ?)')
        params.extend([source, source])
    if category:
        clauses.append('m.category = ?')
        params.append(category)
    if start_date:
        clauses.append('q.quote_date >= ?')
        params.append(start_date)
    if end_date:
        clauses.append('q.quote_date <= ?')
        params.append(end_date)
    if keyword:
        like = '%%%s%%' % keyword
        clauses.append(
            '(m.code LIKE ? OR m.name LIKE ? OR q.source_material_name LIKE ? '
            'OR q.raw_text LIKE ? OR q.product_id LIKE ?)')
        params.extend([like, like, like, like, like])
    where = (' WHERE ' + ' AND '.join(clauses)) if clauses else ''
    return where, params


def query_quotes_page(conn, page: int, page_size: int, source: str = '',
                      category: str = '', start_date: str = '',
                      end_date: str = '', keyword: str = '') -> dict:
    page_size = page_size if page_size in PAGE_SIZES else 10
    where, params = quote_filters(
        source, category, start_date, end_date, keyword)

    total = conn.execute(
        'SELECT COUNT(*) AS n FROM market_quotes q '
        'JOIN market_sources s ON s.id = q.source_id '
        'LEFT JOIN materials m ON m.id = q.material_id' + where,
        params).fetchone()['n']
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(max(int(page or 1), 1), total_pages)
    offset = (page - 1) * page_size

    rows = conn.execute(
        QUOTE_SELECT + where + ' ORDER BY q.quote_date DESC, q.id DESC'
        ' LIMIT ? OFFSET ?', params + [page_size, offset]).fetchall()
    return {
        'items': [quote_item(row) for row in rows],
        'page': page,
        'pageSize': page_size,
        'total': total,
        'totalPages': total_pages,
        'source': source,
        'category': category,
        'startDate': start_date,
        'endDate': end_date,
        'keyword': keyword,
    }


def query_market_stats(conn, quotes: List[dict]) -> dict:
    total = len(quotes)
    matched = len([q for q in quotes if q['matchStatus'] == 'matched'])
    unmatched = total - matched
    today = dt.date.today().isoformat()
    # “今日采集行情条数”按行情日期统计，避免历史回补行被算进今天
    today_quotes = conn.execute(
        'SELECT COUNT(*) AS n FROM market_quotes WHERE quote_date = ?',
        (today,)).fetchone()['n']
    matched_materials = len({q['materialCode'] for q in quotes if q['materialCode']})
    source_count = conn.execute('SELECT COUNT(*) AS n FROM market_sources').fetchone()['n']
    return {
        'todayQuotes': today_quotes,
        'sourceCount': source_count,
        'matchedMaterials': matched_materials,
        'matchRate': round(matched / total * 100) if total else 0,
        'unmatched': unmatched,
        'totalQuotes': total,
    }


def build_ledger_rows(quotes: List[dict]) -> List[dict]:
    """台账展示每个物料最近 3 个真实行情日 + 演示行，避免一次返回全部历史。"""
    dates_by_material = {}
    for quote in quotes:
        if quote['isDemo'] or not quote['materialCode']:
            continue
        dates_by_material.setdefault(quote['materialCode'], set()).add(quote['date'])
    latest_dates = set()
    for dates in dates_by_material.values():
        latest_dates.update(sorted(dates, reverse=True)[:3])
    return [
        q for q in quotes
        if q['isDemo'] or q['date'] in latest_dates
    ]


def daily_quota(conn, configs: List[dict] = None) -> dict:
    """今日行情接口配额：与爬虫 RequestGate 的上限保持一致。"""
    row = conn.execute(
        'SELECT MAX(ss.daily_cap) AS cap FROM source_sync_settings ss '
        'JOIN market_sources ms ON ms.id = ss.source_id '
        "WHERE ss.enabled = 1 AND ms.code = 'fubao'").fetchone()
    cap = int(row['cap'] or 0) if row else 0
    if cap <= 0:
        cap = 20
    enabled = len([item for item in (configs or []) if item.get('status') == '启用'])
    cap = max(cap, 4 + enabled)
    state = conn.execute(
        'SELECT api_call_date, api_calls_today FROM sync_state WHERE id = 1').fetchone()
    calls = 0
    if state and state['api_call_date'] == dt.date.today().isoformat():
        calls = int(state['api_calls_today'] or 0)
    return {
        'dailyCap': cap,
        'callsToday': calls,
        'callsRemaining': max(0, cap - calls),
    }


def query_sync_status(conn, quotes: List[dict]) -> dict:
    state = conn.execute('SELECT * FROM sync_state WHERE id = 1').fetchone()
    state = dict(state) if state else {}
    configs = query_collect_configs(conn)
    primary = next((item for item in configs if item['materialCode'] == 'WB00001'), None)
    if not primary and configs:
        primary = configs[0]
    primary_code = primary['materialCode'] if primary else 'WB00001'
    real_quotes = [q for q in quotes if q['materialCode'] == primary_code and not q['isDemo']]
    real_quotes.sort(key=lambda q: q['date'])
    coverage = {
        'start': real_quotes[0]['date'] if real_quotes else '',
        'end': real_quotes[-1]['date'] if real_quotes else '',
        'days': len({q['date'] for q in real_quotes}),
    }
    latest = real_quotes[-1] if real_quotes else None
    initialized = bool(state.get('initialized'))
    result = state.get('last_run_result') or ''
    if not initialized:
        mode = 'init'
    elif result in ('error', 'failed'):
        mode = 'error'
    elif result in ('partial', 'init_partial'):
        mode = 'partial'
    elif result == 'skipped':
        mode = 'skipped'
    elif result in ('init_success',):
        mode = 'daily'
    else:
        mode = 'daily'

    quota = daily_quota(conn, configs)
    calls_today = quota['callsToday']

    run_materials = state.get('last_run_materials')
    if isinstance(run_materials, str):
        try:
            run_materials = json.loads(run_materials) if run_materials.strip() else {}
        except ValueError:
            run_materials = {}
    if not isinstance(run_materials, dict):
        run_materials = {}
    run_summary = state.get('last_run_summary')
    if isinstance(run_summary, str):
        try:
            run_summary = json.loads(run_summary) if run_summary.strip() else {}
        except ValueError:
            run_summary = {}
    if not isinstance(run_summary, dict):
        run_summary = {}
    material_detail = []
    for item in configs:
        if item['status'] == '已删除':
            continue
        info = run_materials.get('C%s' % item['id']) or {}
        material_detail.append({
            'configId': item['id'],
            'materialCode': item['materialCode'],
            'materialName': item['materialName'],
            'keyword': item['keyword'],
            'productId': item['productId'],
            'status': info.get('status') or '',
            'error': info.get('error') or '',
            'rows': info.get('rows') or item['historyRows'],
            'lastDate': info.get('lastDate') or item['lastHistoryDate'],
        })

    source = {
        'name': primary['source'] if primary else '富宝资讯',
        'material': primary['externalName'] if primary else '清远机械生铝',
        'diid': primary['productId'] if primary else '163321',
        'spec': primary['spec'] if primary and primary['spec'] else '机生铝 Fe6%-8%',
        'tax': primary['tax'] if primary and primary['tax'] else '不含税',
        'unit': primary['unit'] if primary else '元/吨',
    }
    return {
        'mode': mode,
        'initialized': initialized,
        'initDone': int(state.get('init_done_windows') or 0),
        'initTotal': int(state.get('init_total_windows') or 0),
        'callsToday': calls_today,
        'dailyCap': quota['dailyCap'],
        'callsRemaining': quota['callsRemaining'],
        'lastSync': state.get('last_snapshot_at') or '',
        'lastResult': result,
        'lastError': state.get('last_error') or '',
        'collectRunning': COLLECT_RUNNING,
        'runSummary': {
            'total': int(run_summary.get('total') or len(material_detail)),
            'success': int(run_summary.get('success') or 0),
            'partial': int(run_summary.get('partial') or 0),
            'failed': int(run_summary.get('failed') or 0),
            'skipped': int(run_summary.get('skipped') or 0),
        },
        'materials': material_detail,
        'coverage': coverage,
        'latest': {
            'date': latest['date'] if latest else '',
            'range': latest['range'] if latest else '—',
            'avg': latest['avg'] if latest else 0,
            'change': latest['change'] if latest else '—',
        },
        'source': source,
        'configs': [{
            'id': item['id'],
            'materialCode': item['materialCode'],
            'materialName': item['materialName'],
            'externalName': item['externalName'],
            'productId': item['productId'],
            'status': item['status'],
            'initialized': item['initialized'],
            'historyRows': item['historyRows'],
            'lastHistoryDate': item['lastHistoryDate'],
            'lastError': item['lastError'],
        } for item in configs],
    }


def query_templates(conn) -> List[dict]:
    rows = conn.execute(
        'SELECT id, code, name, formula, enabled FROM pricing_templates ORDER BY id').fetchall()
    result = []
    for row in rows:
        factors = conn.execute(
            'SELECT factor FROM pricing_template_factors WHERE template_id = ? '
            'ORDER BY sort_order', (row['id'],)).fetchall()
        result.append({
            'id': row['id'],
            'code': row['code'],
            'name': row['name'],
            'formula': row['formula'],
            'factors': [item['factor'] for item in factors],
            'enabled': bool(row['enabled']),
        })
    return result


def query_params(conn) -> List[dict]:
    rows = conn.execute(
        'SELECT p.id, m.code AS material_code, m.name AS material_name, '
        't.code AS template_code, p.period_type, p.offset_value, p.coefficient, p.status '
        'FROM pricing_params p '
        'JOIN materials m ON m.id = p.material_id '
        'JOIN pricing_templates t ON t.id = p.template_id '
        'ORDER BY p.id').fetchall()
    result = []
    for row in rows:
        result.append(param_item(conn, row['id']))
    return result


def query_schedules(conn) -> List[dict]:
    rows = conn.execute(
        'SELECT id, name, cycle, status, last_run_at, next_run_at '
        'FROM calc_schedules ORDER BY id').fetchall()
    return [{
        'id': row['id'],
        'name': row['name'],
        'cycle': row['cycle'],
        'status': row['status'],
        'lastRun': row['last_run_at'],
        'nextRun': row['next_run_at'],
    } for row in rows]


def query_batches(conn) -> List[dict]:
    rows = conn.execute(
        'SELECT batch_no, run_at, total_count, success_count, fail_count, status '
        'FROM calc_runs ORDER BY run_at DESC').fetchall()
    return [{
        'id': row['batch_no'],
        'runAt': row['run_at'],
        'total': row['total_count'],
        'success': row['success_count'],
        'failed': row['fail_count'],
        'status': row['status'],
    } for row in rows]


def batch_item(conn, batch_no: str) -> dict:
    row = conn.execute(
        'SELECT batch_no, run_at, total_count, success_count, fail_count, status '
        'FROM calc_runs WHERE batch_no = ?', (batch_no,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail='批次不存在')
    return {
        'id': row['batch_no'],
        'runAt': row['run_at'],
        'total': row['total_count'],
        'success': row['success_count'],
        'failed': row['fail_count'],
        'status': row['status'],
    }


def query_results(conn) -> List[dict]:
    rows = conn.execute('SELECT id FROM calc_results ORDER BY id').fetchall()
    return [result_item(conn, row['id']) for row in rows]


def add_months(value: dt.datetime, months: int) -> dt.datetime:
    year = value.year + (value.month - 1 + months) // 12
    month = (value.month - 1 + months) % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def next_run_text(cycle: str, now: dt.datetime) -> Optional[str]:
    text = cycle or ''
    if '月' in text:
        return add_months(now, 1).strftime('%Y-%m-%d %H:%M')
    if '周' in text:
        return (now + dt.timedelta(days=7)).strftime('%Y-%m-%d %H:%M')
    if '日' in text:
        return (now + dt.timedelta(days=1)).strftime('%Y-%m-%d %H:%M')
    return None


def execute_pricing(conn, schedule_row, schedule_id: int) -> dict:
    """按「网站物料 → 公司系统物料」规则，用上一完整周均价生成计价结果。"""
    now = dt.datetime.now()
    week_start, week_end = last_complete_week(now.date())
    rules = conn.execute(
        'SELECT r.id, r.source_config_id, r.material_id, r.template_id, r.period_type, '
        'r.offset_value, r.coefficient, t.code AS template_code, '
        'm.code AS material_code, m.name AS material_name, '
        'sm.code AS source_material_code, sm.name AS source_material_name, '
        'c.material_id AS source_material_id, c.source_id AS source_id, '
        'c.product_id AS product_id '
        'FROM material_pricing_rules r '
        'JOIN pricing_templates t ON t.id = r.template_id '
        'JOIN materials m ON m.id = r.material_id '
        'JOIN source_material_configs c ON c.id = r.source_config_id '
        'LEFT JOIN materials sm ON sm.id = c.material_id '
        "WHERE r.status = '生效' AND c.status = '启用' "
        'ORDER BY r.source_config_id, r.id').fetchall()

    planned = []
    skipped = []
    weeks = {}
    for rule in rules:
        config_id = rule['source_config_id']
        if config_id not in weeks:
            weeks[config_id] = week_average(conn, {
                'material_id': rule['source_material_id'],
                'source_id': rule['source_id'],
                'product_id': rule['product_id'],
            }, week_start, week_end)
        week = weeks[config_id]
        label = '%s → %s %s' % (
            rule['source_material_code'] or '网站物料',
            rule['material_code'], rule['material_name'])
        if week['average'] is None:
            skipped.append('%s（%s ~ %s 无有效报价）' % (
                label, week_start.isoformat(), week_end.isoformat()))
            continue
        if rule['template_code'] not in ('TPL01', 'TPL02'):
            skipped.append('%s（模板 %s 暂不支持自动计算）' % (
                label, rule['template_code']))
            continue

        planned.append({
            'source_config_id': config_id,
            'material_id': rule['material_id'],
            'template_id': rule['template_id'],
            'material_code': rule['material_code'],
            'period_start': week['periodStart'],
            'period_end': week['periodEnd'],
            'period_avg': week['average'],
            'offset_value': rule['offset_value'],
            'coefficient': rule['coefficient'],
            'calc_price': calc_price(week['average'], rule['offset_value'],
                                     rule['coefficient'], rule['template_code']),
        })

    configured_ids = {rule['source_config_id'] for rule in rules}
    unconfigured = conn.execute(
        'SELECT c.id, sm.code AS code, sm.name AS name, c.external_name '
        'FROM source_material_configs c '
        'LEFT JOIN materials sm ON sm.id = c.material_id '
        "WHERE c.status = '启用' ORDER BY c.id").fetchall()
    for config in unconfigured:
        if config['id'] in configured_ids:
            continue
        skipped.append('%s %s（尚未配置公司系统物料规则）' % (
            config['code'] or '网站物料', config['name'] or config['external_name'] or ''))

    if not planned:
        raise HTTPException(
            status_code=400,
            detail='上一完整周（%s ~ %s）没有可计价的规则行情：%s' % (
                week_start.isoformat(), week_end.isoformat(),
                '；'.join(skipped) if skipped else '尚未配置生效的计价规则'))

    batch_no = 'BAT' + now.strftime('%Y%m%d%H%M%S%f')
    run_at = now.strftime('%Y-%m-%d %H:%M:%S')
    cursor = conn.execute(
        'INSERT INTO calc_runs '
        '(batch_no, run_at, total_count, success_count, fail_count, status) '
        "VALUES (?, ?, ?, ?, 0, '成功')",
        (batch_no, run_at, len(planned), len(planned)))
    run_id = cursor.lastrowid

    result_ids = []
    for item in planned:
        result_cursor = conn.execute(
            'INSERT INTO calc_results '
            '(run_id, material_id, source_config_id, template_id, period_start, '
            'period_end, period_avg, offset_value, coefficient, calc_price, '
            'sync_status, review_status, created_at) '
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '已同步', '待复核', ?)",
            (run_id, item['material_id'], item['source_config_id'],
             item['template_id'], item['period_start'], item['period_end'],
             item['period_avg'], item['offset_value'], item['coefficient'],
             item['calc_price'], run_at))
        result_ids.append(result_cursor.lastrowid)

    next_run = next_run_text(schedule_row['cycle'], now)
    conn.execute(
        'UPDATE calc_schedules SET last_run_at = ?, next_run_at = ? WHERE id = ?',
        (run_at, next_run, schedule_id))
    results = [result_item(conn, result_id) for result_id in result_ids]
    log = database.log_operation(
        conn, '计价执行',
        '%s 执行完成：批次 %s，成功 %d 条，跳过 %d 个物料%s' % (
            schedule_row['name'], batch_no, len(results), len(skipped),
            ('；' + '、'.join(skipped)) if skipped else ''))
    conn.commit()
    return {
        'item': schedule_item(conn, schedule_id),
        'run': batch_item(conn, batch_no),
        'results': results,
        'skipped': skipped,
        'log': log,
    }


def query_logs(conn) -> List[dict]:
    rows = conn.execute(
        'SELECT id, log_time, action_type, operator, content, ip '
        'FROM operation_logs ORDER BY log_time DESC, id DESC').fetchall()
    return [{
        'id': row['id'],
        'time': row['log_time'],
        'type': row['action_type'],
        'operator': row['operator'],
        'content': row['content'],
        'ip': row['ip'],
    } for row in rows]


def query_api_calls(conn) -> List[dict]:
    rows = conn.execute(
        'SELECT called_at, mode, purpose, endpoint, method, status_code, elapsed_ms, result '
        'FROM api_call_logs ORDER BY called_at DESC, id DESC').fetchall()
    return [{
        'time': row['called_at'],
        'mode': row['mode'],
        'purpose': row['purpose'],
        'endpoint': row['endpoint'],
        'method': row['method'],
        'status': row['status_code'],
        'elapsed': row['elapsed_ms'],
        'result': row['result'],
    } for row in rows]


# ------------------------------------------------------------------ 采集配置
CONFIG_STATE_FILE = os.path.join(database.SOURCE_DATA_DIR, 'config_state.json')
CONFIG_GATE_LOCK = threading.Lock()
REGION_TTL_DAYS = 30
COLLECT_LOCK = threading.Lock()
COLLECT_RUNNING = False
# 正在回补的采集配置 id（进程内标记，用于前端展示进度）
BACKFILL_RUNNING = set()

# token 自动续期：同一时间只允许一次登录，失败后冷却一段时间，避免触发风控
TOKEN_REFRESH_LOCK = threading.Lock()
TOKEN_REFRESH_COOLDOWN = 300
TOKEN_REFRESH_AT = 0.0
TOKEN_REFRESH_ERROR = ''


def ensure_token_auto(force: bool = False):
    """确保有可用 token：过期且已配置账号时自动登录，返回 (token, error)。"""
    global TOKEN_REFRESH_AT, TOKEN_REFRESH_ERROR
    token = f139.load_token()
    if token and f139.token_valid(token) and not force:
        return token, ''

    creds = credentials.read_credentials()
    if not creds:
        valid_token = token if token and f139.token_valid(token) else ''
        return valid_token, '未配置自动续期账号，请在「网站物料采集配置」设置账号密码'

    with TOKEN_REFRESH_LOCK:
        token = f139.load_token()
        if token and f139.token_valid(token) and not force:
            return token, ''
        now = time.monotonic()
        if not force and TOKEN_REFRESH_AT and now - TOKEN_REFRESH_AT < TOKEN_REFRESH_COOLDOWN:
            return '', TOKEN_REFRESH_ERROR or '自动续期稍后重试'
        TOKEN_REFRESH_AT = now
        try:
            new_token = f139.login(creds[0], creds[1], verbose=False)
            if os.environ.get('F139_TOKEN', '').strip():
                os.environ['F139_TOKEN'] = new_token
            TOKEN_REFRESH_ERROR = ''
            return new_token, ''
        except Exception as exc:
            TOKEN_REFRESH_ERROR = '自动登录失败：%s' % exc
            return '', TOKEN_REFRESH_ERROR


def config_gate(daily_cap: int = 20) -> RequestGate:
    """配置解析使用独立配额，不占用每日行情同步的调用次数。"""
    state = SyncState(CONFIG_STATE_FILE)
    return RequestGate(state, mode='config', min_delay=3.0, max_delay=8.0,
                       daily_cap=daily_cap, log_path=CALL_LOG, enabled=True)


def source_row(conn, code: str):
    row = conn.execute(
        'SELECT id, code, name FROM market_sources WHERE code = ?', (code,)).fetchone()
    if not row:
        raise HTTPException(status_code=400, detail='网站不存在：%s' % code)
    return row


def build_f139_client(gate: RequestGate) -> f139.F139Client:
    token, error = ensure_token_auto()
    if not token:
        raise HTTPException(
            status_code=503,
            detail='富宝 token 不可用：%s' % (
                error or '请先设置自动续期账号，或在「富宝 Token」卡片录入 AUTH_COOKIE'))
    return f139.F139Client(token=token, gate=gate)


def strip_region_suffix(name: str) -> str:
    name = (name or '').strip()
    for suffix in ('壮族自治区', '回族自治区', '维吾尔自治区', '自治区',
                   '特别行政区', '省', '市'):
        if name.endswith(suffix):
            return name[:-len(suffix)]
    return name


def place_matches(place: str, province_name: str = '', city_name: str = '',
                  province_short: str = '', city_short: str = '') -> bool:
    place = (place or '').strip()
    if not place:
        return False
    candidates = {
        (city_short or '').strip(), strip_region_suffix(city_name),
        (province_short or '').strip(), strip_region_suffix(province_name),
    }
    for candidate in candidates:
        if candidate and (candidate == place or candidate in place or place in candidate):
            return True
    return False


def region_tree(conn, source_id: int) -> dict:
    rows = conn.execute(
        'SELECT province_id, province_name, province_short, city_id, city_name, '
        'city_short, updated_at FROM source_regions WHERE source_id = ? '
        'ORDER BY province_id, city_id', (source_id,)).fetchall()
    provinces = {}
    updated = ''
    for row in rows:
        entry = provinces.setdefault(row['province_id'], {
            'id': row['province_id'],
            'name': row['province_name'],
            'shortName': row['province_short'] or '',
            'cities': [],
        })
        entry['cities'].append({
            'id': row['city_id'],
            'name': row['city_name'],
            'shortName': row['city_short'] or '',
        })
        updated = max(updated, row['updated_at'] or '')
    return {'provinces': list(provinces.values()), 'updatedAt': updated}


def refresh_regions(conn, source) -> dict:
    gate = config_gate()
    with CONFIG_GATE_LOCK:
        client = build_f139_client(gate)
        payload = client.regions()
    now = database.now_text()
    with conn:
        conn.execute('DELETE FROM source_regions WHERE source_id = ?', (source['id'],))
        for province in payload:
            if not province.get('id'):
                continue
            for city in province.get('cities') or []:
                if not city.get('id'):
                    continue
                conn.execute(
                    'INSERT OR REPLACE INTO source_regions '
                    '(source_id, province_id, province_name, province_short, city_id, '
                    'city_name, city_short, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                    (source['id'], province.get('id'), province.get('name') or '',
                     province.get('shortName') or '', city.get('id'),
                     city.get('name') or '', city.get('shortName') or '', now))
    return region_tree(conn, source['id'])


def regions_payload(conn, source_code: str = 'fubao', refresh: bool = False) -> dict:
    source = source_row(conn, source_code)
    tree = region_tree(conn, source['id'])
    stale = False
    if tree['updatedAt']:
        try:
            updated = dt.datetime.strptime(tree['updatedAt'], '%Y-%m-%d %H:%M:%S')
            stale = updated < dt.datetime.now() - dt.timedelta(days=REGION_TTL_DAYS)
        except ValueError:
            stale = True
    warning = ''
    if refresh or not tree['provinces'] or stale:
        try:
            tree = refresh_regions(conn, source)
        except HTTPException:
            raise
        except Exception as exc:
            warning = '省市字典刷新失败：%s' % exc
            if not tree['provinces']:
                tree = {'provinces': [], 'updatedAt': ''}
    return {**tree, 'warning': warning}


def region_names(conn, source_id: int, province_id: Optional[int],
                 city_id: Optional[int]) -> dict:
    """省市名称；市非必填，缺省时只按省取一条记录。"""
    empty = {'provinceName': '', 'provinceShort': '', 'cityName': '', 'cityShort': ''}
    if not province_id:
        return empty
    if city_id:
        row = conn.execute(
            'SELECT province_name, province_short, city_name, city_short '
            'FROM source_regions WHERE source_id = ? AND province_id = ? AND city_id = ?',
            (source_id, province_id, city_id)).fetchone()
        if not row:
            return empty
        return {
            'provinceName': row['province_name'] or '',
            'provinceShort': row['province_short'] or '',
            'cityName': row['city_name'] or '',
            'cityShort': row['city_short'] or '',
        }
    row = conn.execute(
        'SELECT province_name, province_short FROM source_regions '
        'WHERE source_id = ? AND province_id = ? ORDER BY city_id LIMIT 1',
        (source_id, province_id)).fetchone()
    if not row:
        return empty
    return {
        'provinceName': row['province_name'] or '',
        'provinceShort': row['province_short'] or '',
        'cityName': '',
        'cityShort': '',
    }


def config_item(conn, config_id: int) -> dict:
    row = conn.execute(
        'SELECT c.*, s.code AS source_code, s.name AS source_name, '
        'm.code AS material_code, m.name AS material_name, '
        'COALESCE(ss.enabled, 1) AS source_enabled, '
        'COALESCE(ss.auto_supported, 0) AS auto_supported '
        'FROM source_material_configs c '
        'JOIN market_sources s ON s.id = c.source_id '
        'LEFT JOIN materials m ON m.id = c.material_id '
        'LEFT JOIN source_sync_settings ss ON ss.source_id = c.source_id '
        'WHERE c.id = ?', (config_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail='采集配置不存在')
    latest = conn.execute(
        'SELECT quote_date, raw_text, avg_price, change_text FROM market_quotes '
        'WHERE source_id = ? AND product_id = ? AND is_demo = 0 '
        'ORDER BY quote_date DESC LIMIT 1',
        (row['source_id'], row['product_id'])).fetchone()
    return {
        'id': row['id'],
        'sourceCode': row['source_code'],
        'source': row['source_name'],
        'sourceEnabled': bool(row['source_enabled']),
        'autoSupported': bool(row['auto_supported']),
        'keyword': row['keyword'],
        'provinceId': row['province_id'],
        'provinceName': row['province_name'] or '',
        'cityId': row['city_id'],
        'cityName': row['city_name'] or '',
        'productId': row['product_id'],
        'externalName': row['external_name'],
        'webName': row['external_web_name'] or '',
        'place': row['external_place'] or '',
        'spec': row['external_spec'] or '',
        'tax': row['external_tax'] or '',
        'unit': row['external_unit'] or '元/吨',
        'org': row['external_org'] or '',
        'varietyId': row['variety_id'],
        'classifyId': row['classify_id'],
        'materialCode': row['material_code'] or '',
        'materialName': row['material_name'] or '',
        'status': row['status'],
        'historyDays': row['history_days'],
        'initialized': bool(row['initialized']),
        'historyRows': row['history_rows'],
        'initDone': row['init_done_windows'],
        'initTotal': row['init_total_windows'],
        'backfillRunning': row['id'] in BACKFILL_RUNNING,
        'lastHistoryDate': row['last_history_date'] or '',
        'lastSnapshotAt': row['last_snapshot_at'] or '',
        'lastVerifiedAt': row['last_verified_at'] or '',
        'lastError': row['last_error'] or '',
        'remark': row['remark'] or '',
        'createdAt': row['created_at'],
        'updatedAt': row['updated_at'],
        'today': {
            'date': latest['quote_date'],
            'range': latest['raw_text'] or '',
            'avg': latest['avg_price'],
            'change': latest['change_text'] or '',
        } if latest else None,
    }


def query_collect_configs(conn, include_deleted: bool = False) -> List[dict]:
    sql = 'SELECT id FROM source_material_configs'
    if not include_deleted:
        sql += " WHERE status <> '已删除'"
    sql += ' ORDER BY id'
    return [config_item(conn, row['id']) for row in conn.execute(sql).fetchall()]


def query_source_sync(conn) -> List[dict]:
    """按网站汇总同步开关、物料数量、今日同步与错误情况。"""
    rows = conn.execute(
        'SELECT s.id, s.code, s.name, '
        'COALESCE(ss.enabled, 0) AS enabled, '
        'COALESCE(ss.auto_supported, 0) AS auto_supported, '
        "COALESCE(ss.sync_mode, 'manual') AS sync_mode, "
        'COALESCE(ss.daily_cap, 0) AS daily_cap, '
        'ss.last_sync_at, ss.last_error '
        'FROM market_sources s '
        'LEFT JOIN source_sync_settings ss ON ss.source_id = s.id '
        'ORDER BY s.id').fetchall()
    today = dt.date.today().isoformat()
    result = []
    for row in rows:
        configs = conn.execute(
            'SELECT status, initialized, last_snapshot_at, last_error '
            "FROM source_material_configs WHERE source_id = ? AND status <> '已删除'",
            (row['id'],)).fetchall()
        total = len(configs)
        enabled_count = sum(1 for item in configs if item['status'] == '启用')
        disabled_count = sum(1 for item in configs if item['status'] == '停用')
        initialized_count = sum(1 for item in configs if item['initialized'])
        error_count = sum(1 for item in configs if item['last_error'])
        synced_today = sum(
            1 for item in configs
            if (item['last_snapshot_at'] or '')[:10] == today)
        last_sync = max(
            (item['last_snapshot_at'] or '' for item in configs), default='')
        config_error = next(
            (item['last_error'] for item in configs if item['last_error']), '')
        if row['code'] == 'fubao':
            quota = daily_quota(conn, [{'status': item['status']} for item in configs])
        else:
            quota = {
                'dailyCap': int(row['daily_cap'] or 0),
                'callsToday': 0,
                'callsRemaining': 0,
            }
        result.append({
            'id': row['id'],
            'code': row['code'],
            'name': row['name'],
            'enabled': bool(row['enabled']),
            'autoSupported': bool(row['auto_supported']),
            'syncMode': row['sync_mode'],
            'dailyCap': quota['dailyCap'],
            'callsToday': quota['callsToday'],
            'callsRemaining': quota['callsRemaining'],
            'lastSyncAt': row['last_sync_at'] or last_sync,
            'lastError': row['last_error'] or config_error,
            'materialCount': total,
            'enabledCount': enabled_count,
            'disabledCount': disabled_count,
            'initializedCount': initialized_count,
            'errorCount': error_count,
            'syncedToday': synced_today,
        })
    return result


def next_material_code(conn) -> str:
    """网站物料编码：WB00001 起；系统物料使用 XT00001 起。"""
    row = conn.execute(
        "SELECT MAX(CAST(SUBSTR(code, 3) AS INTEGER)) AS n FROM materials "
        "WHERE code LIKE 'WB%'").fetchone()
    number = int(row['n'] or 0) + 1
    while True:
        code = 'WB%05d' % number
        if not conn.execute('SELECT 1 FROM materials WHERE code = ?', (code,)).fetchone():
            return code
        number += 1


def next_system_material_code(conn) -> str:
    row = conn.execute(
        "SELECT MAX(CAST(SUBSTR(code, 3) AS INTEGER)) AS n FROM materials "
        "WHERE code LIKE 'XT%'").fetchone()
    number = int(row['n'] or 0) + 1
    while True:
        code = 'XT%05d' % number
        if not conn.execute('SELECT 1 FROM materials WHERE code = ?', (code,)).fetchone():
            return code
        number += 1


def upsert_alias(conn, material_id: int, source_id: int, data: dict) -> None:
    """同一系统物料+网站只保留一条别名，避免映射表出现重复行。"""
    external_name = data.get('externalName') or data.get('keyword') or ''
    spec = data.get('spec') or ''
    row = conn.execute(
        'SELECT id FROM material_aliases WHERE material_id = ? AND source_id = ? '
        'ORDER BY id LIMIT 1', (material_id, source_id)).fetchone()
    if row:
        conn.execute(
            'UPDATE material_aliases SET external_name = ?, external_spec = ?, diid = ?, '
            'region = ?, tax = ?, unit = ?, status = ? WHERE id = ?',
            (external_name, spec, data.get('productId'), data.get('place') or '',
             data.get('tax') or '', data.get('unit') or '元/吨', '已匹配', row['id']))
    else:
        conn.execute(
            'INSERT INTO material_aliases '
            '(material_id, source_id, external_name, external_spec, diid, region, tax, '
            'unit, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (material_id, source_id, external_name, spec, data.get('productId'),
             data.get('place') or '', data.get('tax') or '',
             data.get('unit') or '元/吨', '已匹配', dt.date.today().isoformat()))


def payload_to_candidate(item: dict, fallback: Optional[dict] = None) -> dict:
    fallback = fallback or {}
    avg = item.get('avgPrice')
    try:
        avg = float(avg) if avg is not None and avg != '' else None
    except (TypeError, ValueError):
        avg = None
    return {
        'productId': str(item.get('productId') or fallback.get('productId') or ''),
        'externalName': (
            item.get('combinationName')
            or fallback.get('externalName')
            or '%s-%s' % (item.get('place') or '', item.get('webName') or '')
        ),
        'webName': item.get('webName') or item.get('name') or fallback.get('webName') or '',
        'place': item.get('place') or fallback.get('place') or '',
        'spec': item.get('specification') or fallback.get('spec') or '',
        'tax': item.get('tax') or fallback.get('tax') or '',
        'unit': item.get('unit') or fallback.get('unit') or '元/吨',
        'org': item.get('organization') or fallback.get('org') or '',
        'varietyId': item.get('varietyId') or fallback.get('varietyId'),
        'classifyId': item.get('classifyId') or fallback.get('classifyId'),
        'price': item.get('priceStr') or fallback.get('price') or '',
        'avg': avg,
        'change': item.get('uad') or fallback.get('change') or '',
        'date': item.get('dateDate') or fallback.get('date') or '',
    }


class CollectSearchPayload(BaseModel):
    source: str = 'fubao'
    keyword: str
    provinceId: Optional[int] = None
    cityId: Optional[int] = None
    pageSize: int = 50


class CollectConfigPayload(BaseModel):
    source: str = 'fubao'
    keyword: str
    provinceId: int
    provinceName: str = ''
    cityId: Optional[int] = None
    cityName: str = ''
    productId: str
    externalName: str
    externalWebName: str = ''
    externalPlace: str = ''
    externalSpec: str = ''
    externalTax: str = ''
    externalUnit: str = '元/吨'
    externalOrg: str = ''
    varietyId: Optional[int] = None
    classifyId: Optional[int] = None
    # 兼容旧字段：网站物料固定自动创建，这两个字段不再生效
    materialCode: Optional[str] = None
    createMaterial: bool = True
    historyDays: int = 30
    remark: str = ''
    enabled: bool = True
    # 保存后是否立即回补历史（新增配置时为 true）
    syncHistory: bool = False


class BackfillPayload(BaseModel):
    days: int = 30
    reinit: bool = False


class BatchTogglePayload(BaseModel):
    sourceId: int
    enabled: bool


def _backfill_worker(config_id: int, days: int, reinit: bool) -> None:
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    command = [sys.executable, os.path.join(database.CODE_DIR, 'f139_auto.py'),
               'init', '--config', str(config_id), '--init-days', str(days)]
    if reinit:
        command.append('--reinit')
    BACKFILL_RUNNING.add(config_id)
    try:
        subprocess.run(command, cwd=database.CODE_DIR, creationflags=flags,
                       timeout=7200, check=False, env=credentials.subprocess_env())
        subprocess.run(
            [sys.executable, os.path.join(database.SERVER_DIR, 'sync_db.py')],
            cwd=database.SERVER_DIR, creationflags=flags, timeout=600, check=False,
            env=credentials.subprocess_env())
    except Exception as exc:
        try:
            conn = database.connect()
            conn.execute(
                'UPDATE source_material_configs SET last_error = ?, updated_at = ? WHERE id = ?',
                ('回补任务异常：%s' % exc, database.now_text(), config_id))
            conn.commit()
            conn.close()
        except Exception:
            pass
    finally:
        BACKFILL_RUNNING.discard(config_id)


def planned_windows(days: int, chunk_days: int = 60) -> int:
    """回补窗口数：与 f139_auto.expected_total_windows 保持一致（起始日含当天）。"""
    span = max(1, int(days)) + 1
    return max(1, (span + chunk_days - 1) // chunk_days)


def start_backfill(conn, config_id: int, days: int, reinit: bool = False) -> dict:
    """启动历史回补；条件不满足时返回原因，不影响配置保存。"""
    days = max(1, min(int(days or 30), MAX_HISTORY_DAYS))
    info = {'started': False, 'days': days, 'windows': planned_windows(days),
            'quota': daily_quota(conn, query_collect_configs(conn)), 'reason': ''}
    row = conn.execute(
        'SELECT id, status, source_id, initialized, init_done_windows, '
        'init_total_windows FROM source_material_configs WHERE id = ?',
        (config_id,)).fetchone()
    if not row or row['status'] == '已删除':
        info['reason'] = '采集配置不存在'
        return info
    if row['status'] != '启用':
        info['reason'] = '采集配置已停用'
        return info
    settings = conn.execute(
        'SELECT COALESCE(enabled, 0) AS enabled FROM source_sync_settings '
        'WHERE source_id = ?', (row['source_id'],)).fetchone()
    if settings is not None and not settings['enabled']:
        info['reason'] = '网站总开关已关闭'
        return info
    if config_id in BACKFILL_RUNNING:
        info['reason'] = '该配置正在回补中'
        return info
    if info['quota']['callsRemaining'] <= 0:
        info['reason'] = '今日接口配额已用完，将在明日续跑'
        return info

    conn.execute(
        'UPDATE source_material_configs SET last_error = ?, updated_at = ? WHERE id = ?',
        ('', database.now_text(), config_id))
    conn.commit()
    threading.Thread(
        target=_backfill_worker, args=(config_id, days, reinit), daemon=True).start()
    info['started'] = True
    return info


def _collect_worker() -> None:
    """后台执行一次完整的抓取 + SQLite 导入。"""
    global COLLECT_RUNNING
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    try:
        result = subprocess.run(
            [sys.executable, os.path.join(database.CODE_DIR, 'f139_auto.py'),
             'auto', '--force'],
            cwd=database.CODE_DIR, creationflags=flags, timeout=7200, check=False,
            env=credentials.subprocess_env())
        if result.returncode in (0, 3):
            subprocess.run(
                [sys.executable, os.path.join(database.SERVER_DIR, 'sync_db.py')],
                cwd=database.SERVER_DIR, creationflags=flags, timeout=600, check=False,
                env=credentials.subprocess_env())
    except Exception as exc:
        try:
            conn = database.connect()
            conn.execute(
                'UPDATE sync_state SET last_error = ?, updated_at = ? WHERE id = 1',
                ('手动采集异常：%s' % exc, database.now_text()))
            conn.commit()
            conn.close()
        except Exception:
            pass
    finally:
        with COLLECT_LOCK:
            COLLECT_RUNNING = False


def _save_config(conn, payload: CollectConfigPayload,
                 config_id: Optional[int] = None) -> dict:
    keyword = (payload.keyword or '').strip()
    product_id = (payload.productId or '').strip()
    if not keyword or not product_id:
        raise HTTPException(status_code=400, detail='网站物料名称和 productId 不能为空')
    if not payload.provinceId:
        raise HTTPException(status_code=400, detail='请选择省/直辖市')

    source = source_row(conn, payload.source)
    settings = conn.execute(
        'SELECT auto_supported FROM source_sync_settings WHERE source_id = ?',
        (source['id'],)).fetchone()
    if settings is not None and not settings['auto_supported']:
        raise HTTPException(status_code=400, detail='该网站尚未接入自动解析')
    city_id = payload.cityId or None
    names = region_names(conn, source['id'], payload.provinceId, city_id)
    province_name = payload.provinceName or names['provinceName']
    city_name = payload.cityName or names['cityName']
    if not province_name:
        raise HTTPException(status_code=400, detail='省市字典未加载，请先刷新省市')

    row = None
    if config_id is not None:
        row = conn.execute(
            'SELECT * FROM source_material_configs WHERE id = ?', (config_id,)).fetchone()
        if not row or row['status'] == '已删除':
            raise HTTPException(status_code=404, detail='采集配置不存在')
    else:
        row = conn.execute(
            'SELECT * FROM source_material_configs WHERE source_id = ? AND product_id = ?',
            (source['id'], product_id)).fetchone()
        if row:
            config_id = row['id']

    # 网站物料固定自动创建：已有配置沿用原物料，新建时按名称去重后创建
    material_id = row['material_id'] if row else None
    if not material_id:
        region_label = (names['cityShort'] or strip_region_suffix(city_name)
                        or names['provinceShort'] or strip_region_suffix(province_name))
        material_name = '%s%s' % (region_label, keyword)
        existing_material = conn.execute(
            'SELECT id FROM materials WHERE name = ? '
            "AND material_type = '网站' ORDER BY id LIMIT 1", (material_name,)).fetchone()
        if existing_material:
            material_id = existing_material['id']
        else:
            code = next_material_code(conn)
            cursor = conn.execute(
                'INSERT INTO materials (code, name, category, unit, material_type) '
                "VALUES (?, ?, ?, ?, '网站')",
                (code, material_name, '废金属', payload.externalUnit or '元/吨'))
            material_id = cursor.lastrowid

    place_label = (payload.externalPlace or names['cityShort']
                   or strip_region_suffix(city_name) or names['provinceShort']
                   or strip_region_suffix(province_name))
    external_name = (payload.externalName or '').strip()
    if not external_name:
        external_name = '%s-%s' % (place_label, keyword)

    now = database.now_text()
    values = (
        keyword, payload.provinceId, province_name, city_id, city_name,
        payload.varietyId, payload.classifyId, external_name,
        payload.externalWebName or keyword, payload.externalPlace or place_label,
        payload.externalSpec or '', payload.externalTax or '', payload.externalUnit or '元/吨',
        payload.externalOrg or '', material_id,
        '启用' if payload.enabled else '停用',
        max(1, min(int(payload.historyDays or 30), MAX_HISTORY_DAYS)),
        payload.remark or '', now,
    )
    if config_id:
        conn.execute(
            'UPDATE source_material_configs SET keyword = ?, province_id = ?, '
            'province_name = ?, city_id = ?, city_name = ?, variety_id = ?, '
            'classify_id = ?, external_name = ?, external_web_name = ?, '
            'external_place = ?, external_spec = ?, external_tax = ?, external_unit = ?, '
            'external_org = ?, material_id = ?, status = ?, history_days = ?, '
            'remark = ?, updated_at = ? WHERE id = ?', values + (config_id,))
    else:
        cursor = conn.execute(
            'INSERT INTO source_material_configs '
            '(keyword, province_id, province_name, city_id, city_name, variety_id, '
            'classify_id, external_name, external_web_name, external_place, '
            'external_spec, external_tax, external_unit, external_org, material_id, '
            'status, history_days, remark, created_at, updated_at, source_id, product_id, '
            'price_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            values + (now, source['id'], product_id, '市场价格'))
        config_id = cursor.lastrowid

    upsert_alias(conn, material_id, source['id'], {
        'externalName': external_name, 'productId': product_id,
        'keyword': keyword, 'place': payload.externalPlace or place_label,
        'tax': payload.externalTax or '', 'unit': payload.externalUnit or '元/吨',
        'spec': payload.externalSpec or '',
    })
    alias = conn.execute(
        'SELECT id FROM material_aliases WHERE material_id = ? AND source_id = ? '
        'ORDER BY id LIMIT 1', (material_id, source['id'])).fetchone()
    conn.execute(
        'UPDATE material_aliases SET status = ? WHERE material_id = ? AND source_id = ?',
        ('已匹配' if payload.enabled else '停用', material_id, source['id']))
    conn.execute(
        'UPDATE market_quotes SET material_id = ?, alias_id = ? '
        'WHERE source_id = ? AND product_id = ? AND material_id IS NULL',
        (material_id, alias['id'] if alias else None, source['id'], product_id))

    item = config_item(conn, config_id)
    log = database.log_operation(
        conn, '采集配置',
        '%s采集配置：%s / %s / %s%s / %s（productId=%s）→ %s' % (
            '更新' if row else '新增', item['source'], item['keyword'],
            item['provinceName'], item['cityName'], item['externalName'],
            item['productId'], item['materialCode'] or '未绑定'))
    conn.commit()
    return {'item': item, 'log': log, 'created': not bool(row)}


# ------------------------------------------------------------------ 路由
API_VERSION = '1.8.0'
API_FEATURES = ('collect_run', 'pricing_execute', 'mapping_crud',
                'source_sync', 'quotes_page', 'pricing_rules', 'sync_quota',
                'save_and_sync', 'token_manage', 'quote_capture_split')
MAX_HISTORY_DAYS = 365


@app.get('/api/health')
def health():
    return {
        'ok': True,
        'version': API_VERSION,
        'features': list(API_FEATURES),
        'time': database.now_text(),
    }


def valid_date(value: str) -> str:
    text = (value or '').strip()
    if not text:
        return ''
    try:
        dt.date.fromisoformat(text)
        return text
    except ValueError:
        return ''


@app.get('/api/quotes')
def quotes_page(page: int = 1, pageSize: int = 10, source: str = '',
                category: str = '', startDate: str = '', endDate: str = '',
                keyword: str = '',
                conn: sqlite3.Connection = Depends(database.get_db)):
    start_date = valid_date(startDate)
    end_date = valid_date(endDate)
    if start_date and end_date and start_date > end_date:
        start_date, end_date = end_date, start_date
    return query_quotes_page(
        conn, page, pageSize, source, category, start_date, end_date,
        keyword.strip())


@app.get('/api/bootstrap')
def bootstrap(conn: sqlite3.Connection = Depends(database.get_db)):
    quotes = query_quotes(conn)
    return {
        'sources': query_sources(conn),
        'materials': query_materials(conn),
        'mappings': query_mappings(conn),
        'quotes': quotes,
        'ledgerRows': build_ledger_rows(quotes),
        'templates': query_templates(conn),
        'params': query_params(conn),
        'pricingRules': query_pricing_rules(conn),
        'schedules': query_schedules(conn),
        'batches': query_batches(conn),
        'results': query_results(conn),
        'logs': query_logs(conn),
        'apiCallLogs': query_api_calls(conn),
        'syncStatus': query_sync_status(conn, quotes),
        'marketStats': query_market_stats(conn, quotes),
        'collectConfigs': query_collect_configs(conn),
        'sourceSync': query_source_sync(conn),
    }


# ------------------------------------------------------------------ 采集配置接口
@app.get('/api/collect/regions')
def collect_regions(source: str = 'fubao', refresh: bool = False,
                    conn: sqlite3.Connection = Depends(database.get_db)):
    return regions_payload(conn, source, refresh=refresh)


@app.post('/api/collect/regions/refresh')
def collect_regions_refresh(source: str = 'fubao',
                            conn: sqlite3.Connection = Depends(database.get_db)):
    return regions_payload(conn, source, refresh=True)


@app.get('/api/collect/configs')
def collect_configs(includeDeleted: bool = False,
                    conn: sqlite3.Connection = Depends(database.get_db)):
    return {'items': query_collect_configs(conn, include_deleted=includeDeleted)}


@app.get('/api/collect/overview')
def collect_overview(conn: sqlite3.Connection = Depends(database.get_db)):
    state = conn.execute('SELECT * FROM sync_state WHERE id = 1').fetchone()
    calls_today = 0
    if state and state['api_call_date'] == dt.date.today().isoformat():
        calls_today = int(state['api_calls_today'] or 0)
    return {
        'sources': query_source_sync(conn),
        'callsToday': calls_today,
        'lastSyncAt': state['last_snapshot_at'] if state else '',
        'lastResult': state['last_run_result'] if state else '',
    }


@app.get('/api/collect/token')
def collect_token_status(auto_refresh: bool = True):
    """富宝 token 状态（只返回掩码，不返回完整 token）。

    token 过期且已保存自动续期账号时，这里会顺带尝试一次自动登录；
    失败不会抛出 500，而是通过 refreshError 返回原因。
    """
    refresh_error = ''
    token = f139.load_token()
    if auto_refresh and (not token or not f139.token_valid(token)):
        refreshed, refresh_error = ensure_token_auto()
        if refreshed:
            token = refreshed
    env_set = bool(os.environ.get('F139_TOKEN', '').strip())
    expiry = f139.token_expiry(token) if token else None
    remaining = None
    if expiry:
        remaining = int((expiry - dt.datetime.now()).total_seconds() // 3600)
    masked = ''
    if token:
        core = token.split('|')[0]
        masked = (core[:10] + '****' + core[-6:]) if len(core) > 18 else '****'
    cred = credentials.status()
    return {
        'present': bool(token),
        'valid': f139.token_valid(token) if token else False,
        'source': 'env' if env_set else ('file' if token else 'missing'),
        'masked': masked,
        'expiry': expiry.strftime('%Y-%m-%d %H:%M:%S') if expiry else '',
        'remainingHours': remaining,
        'filePath': os.path.basename(f139.TOKEN_FILE),
        'autoRenew': cred['configured'],
        'autoRenewAccount': cred['username'],
        'refreshError': refresh_error,
    }


class TokenPayload(BaseModel):
    token: str


class CredentialsPayload(BaseModel):
    username: str
    password: str


@app.post('/api/collect/token')
def save_collect_token(payload: TokenPayload,
                       conn: sqlite3.Connection = Depends(database.get_db)):
    """前台录入富宝 AUTH_COOKIE，写入 auth_token.txt（无 BOM）。"""
    token = (payload.token or '').strip().strip('"').strip("'")
    if not token:
        raise HTTPException(status_code=400, detail='token 不能为空')
    if len(token) < 16:
        raise HTTPException(status_code=400, detail='token 长度异常，请粘贴完整的 AUTH_COOKIE')
    f139.save_token(token)
    expiry = f139.token_expiry(token)
    warning = ''
    if not expiry:
        warning = 'token 未包含过期时间，无法自动判断有效期'
    elif not f139.token_valid(token):
        warning = '该 token 已过期，请粘贴新的 AUTH_COOKIE'
    if os.environ.get('F139_TOKEN', '').strip():
        warning = (warning + '；' if warning else '') + \
            '当前环境变量 F139_TOKEN 优先级更高，录入的 token 不会生效'
    log = database.log_operation(
        conn, '采集配置',
        '录入富宝 token（有效期至 %s）' % (
            expiry.strftime('%Y-%m-%d %H:%M:%S') if expiry else '未知'))
    status = collect_token_status(auto_refresh=False)
    status['warning'] = warning
    status['message'] = 'token 已保存'
    status['log'] = log
    return status


@app.get('/api/collect/credentials')
def collect_credentials_status():
    """自动续期账号状态（只返回掩码用户名，不返回密码）。"""
    return credentials.status()


@app.post('/api/collect/credentials')
def save_collect_credentials(payload: CredentialsPayload,
                             conn: sqlite3.Connection = Depends(database.get_db)):
    """保存自动续期账号：先验证登录，再用 Windows DPAPI 加密写入 cred.dat。"""
    global TOKEN_REFRESH_AT, TOKEN_REFRESH_ERROR
    username = (payload.username or '').strip()
    password = payload.password or ''
    if not username or not password:
        raise HTTPException(status_code=400, detail='用户名和密码不能为空')
    try:
        token = f139.login(username, password, verbose=False)
    except Exception as exc:
        raise HTTPException(status_code=400, detail='登录验证失败：%s' % exc)
    try:
        credentials.save_credentials(username, password)
    except Exception as exc:
        raise HTTPException(status_code=500, detail='凭据加密保存失败：%s' % exc)
    credentials.load_into_env()
    if os.environ.get('F139_TOKEN', '').strip():
        os.environ['F139_TOKEN'] = token
    TOKEN_REFRESH_AT = time.monotonic()
    TOKEN_REFRESH_ERROR = ''
    log = database.log_operation(
        conn, '采集配置',
        '富宝账号登录（账号 %s，自动续期已启用，token 有效期至 %s）' % (
            credentials.mask_username(username),
            f139.token_expiry(token).strftime('%Y-%m-%d %H:%M:%S')
            if f139.token_expiry(token) else '未知'))
    status = collect_token_status(auto_refresh=False)
    return {
        'credentials': credentials.status(),
        'token': status,
        'log': log,
        'message': '账号登录成功，自动续期已启用，后续 token 过期会自动获取',
    }


@app.post('/api/collect/login')
def login_collect_account(payload: CredentialsPayload,
                          conn: sqlite3.Connection = Depends(database.get_db)):
    """用户账号登录（与 /collect/credentials 等价，语义更明确）。"""
    return save_collect_credentials(payload, conn)


@app.delete('/api/collect/credentials')
def delete_collect_credentials(conn: sqlite3.Connection = Depends(database.get_db)):
    """移除自动续期账号；已获取的 token 保留到自然过期。"""
    credentials.clear_credentials()
    log = database.log_operation(conn, '采集配置', '退出富宝账号登录（关闭自动续期）')
    return {
        'credentials': credentials.status(),
        'log': log,
        'message': '账号已退出，自动续期已关闭；当前 token 保留到过期为止',
    }


@app.post('/api/collect/token/refresh')
def refresh_collect_token(conn: sqlite3.Connection = Depends(database.get_db)):
    """立即用已保存账号重新登录，刷新 token。"""
    if not credentials.status()['configured']:
        raise HTTPException(status_code=400, detail='尚未配置自动续期账号')
    token, error = ensure_token_auto(force=True)
    if not token:
        raise HTTPException(status_code=502, detail=error or '自动登录失败')
    log = database.log_operation(
        conn, '采集配置',
        '富宝 token 自动续期成功（有效期至 %s）' % (
            f139.token_expiry(token).strftime('%Y-%m-%d %H:%M:%S')
            if f139.token_expiry(token) else '未知'))
    return {
        'token': collect_token_status(auto_refresh=False),
        'log': log,
        'message': 'token 已自动续期',
    }


@app.get('/api/sync/status')
def sync_status(conn: sqlite3.Connection = Depends(database.get_db)):
    """轻量同步状态：配额、上次结果、逐物料明细；手动采集后前端轮询用。"""
    data = query_sync_status(conn, query_quotes(conn))
    data['collectRunning'] = COLLECT_RUNNING
    return data


@app.post('/api/collect/run')
def run_collect_now(conn: sqlite3.Connection = Depends(database.get_db)):
    global COLLECT_RUNNING
    configs = query_collect_configs(conn)
    quota = daily_quota(conn, configs)
    if quota['callsRemaining'] <= 0:
        raise HTTPException(
            status_code=409,
            detail='今日接口调用已达上限（%d 次），请明天再试' % quota['dailyCap'])
    with COLLECT_LOCK:
        if COLLECT_RUNNING:
            raise HTTPException(status_code=409, detail='采集任务正在运行，请稍后再试')
        COLLECT_RUNNING = True
    try:
        log = database.log_operation(
            conn, '行情采集',
            '手动触发行情采集（今日配额 %d/%d）' % (
                quota['callsToday'], quota['dailyCap']))
        threading.Thread(target=_collect_worker, daemon=True).start()
    except Exception:
        with COLLECT_LOCK:
            COLLECT_RUNNING = False
        raise
    return {
        'started': True,
        'log': log,
        'quota': quota,
        'message': '采集任务已启动（后台低频抓取，完成后自动导入 SQLite）',
    }


@app.post('/api/sources/{source_id}/toggle')
def toggle_source_sync(source_id: int,
                       conn: sqlite3.Connection = Depends(database.get_db)):
    row = conn.execute(
        'SELECT s.name, COALESCE(ss.enabled, 0) AS enabled, '
        'COALESCE(ss.auto_supported, 0) AS auto_supported '
        'FROM market_sources s LEFT JOIN source_sync_settings ss ON ss.source_id = s.id '
        'WHERE s.id = ?', (source_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail='网站不存在')
    if not row['auto_supported']:
        raise HTTPException(status_code=400, detail='该网站尚未接入自动解析')
    enabled = 0 if row['enabled'] else 1
    conn.execute(
        'INSERT INTO source_sync_settings '
        '(source_id, enabled, auto_supported, sync_mode, daily_cap, updated_at) '
        "VALUES (?, ?, 1, 'daily', 20, ?) "
        'ON CONFLICT(source_id) DO UPDATE SET enabled = excluded.enabled, '
        'updated_at = excluded.updated_at',
        (source_id, enabled, database.now_text()))
    active = conn.execute(
        "SELECT COUNT(*) AS n FROM source_material_configs "
        "WHERE source_id = ? AND status = '启用'", (source_id,)).fetchone()['n']
    log = database.log_operation(
        conn, '网站同步',
        '%s网站同步：%s（影响 %d 个启用物料）' % (
            '启用' if enabled else '停用', row['name'], active))
    conn.commit()
    item = next(
        (entry for entry in query_source_sync(conn) if entry['id'] == source_id), None)
    return {'item': item, 'log': log}


@app.post('/api/collect/configs/batch-toggle')
def batch_toggle_collect_configs(payload: BatchTogglePayload,
                                 conn: sqlite3.Connection = Depends(database.get_db)):
    source = conn.execute(
        'SELECT s.name, COALESCE(ss.enabled, 0) AS enabled, '
        'COALESCE(ss.auto_supported, 0) AS auto_supported '
        'FROM market_sources s LEFT JOIN source_sync_settings ss ON ss.source_id = s.id '
        'WHERE s.id = ?', (payload.sourceId,)).fetchone()
    if not source:
        raise HTTPException(status_code=404, detail='网站不存在')
    if not source['auto_supported']:
        raise HTTPException(status_code=400, detail='该网站尚未接入自动解析')
    if payload.enabled and not source['enabled']:
        raise HTTPException(status_code=400, detail='网站总开关已关闭，请先启用网站同步')

    status = '启用' if payload.enabled else '停用'
    rows = conn.execute(
        "SELECT id, material_id FROM source_material_configs "
        "WHERE source_id = ? AND status <> '已删除'", (payload.sourceId,)).fetchall()
    for row in rows:
        conn.execute(
            'UPDATE source_material_configs SET status = ?, updated_at = ? WHERE id = ?',
            (status, database.now_text(), row['id']))
        if row['material_id']:
            conn.execute(
                'UPDATE material_aliases SET status = ? '
                'WHERE material_id = ? AND source_id = ?',
                ('已匹配' if payload.enabled else '停用',
                 row['material_id'], payload.sourceId))
    log = database.log_operation(
        conn, '采集配置',
        '%s「%s」下全部物料：%s（共 %d 条）' % (
            status, source['name'], status, len(rows)))
    conn.commit()
    item = next(
        (entry for entry in query_source_sync(conn)
         if entry['id'] == payload.sourceId), None)
    return {'updated': len(rows), 'status': status, 'item': item, 'log': log}


@app.post('/api/collect/search')
def collect_search(payload: CollectSearchPayload,
                   conn: sqlite3.Connection = Depends(database.get_db)):
    keyword = (payload.keyword or '').strip()
    if not keyword:
        raise HTTPException(status_code=400, detail='请输入网站物料名称')
    source = source_row(conn, payload.source)
    settings = conn.execute(
        'SELECT auto_supported FROM source_sync_settings WHERE source_id = ?',
        (source['id'],)).fetchone()
    if settings is not None and not settings['auto_supported']:
        raise HTTPException(status_code=400, detail='该网站尚未接入自动解析')
    names = region_names(conn, source['id'], payload.provinceId, payload.cityId)

    gate = config_gate()
    try:
        with CONFIG_GATE_LOCK:
            client = build_f139_client(gate)
            search_items, total = client.search_quotes(
                keyword, page_size=min(max(int(payload.pageSize), 1), 50))
            ids = []
            seen = set()
            for item in search_items:
                product_id = str(item.get('productId') or '')
                if product_id and product_id not in seen:
                    seen.add(product_id)
                    ids.append(product_id)
            today = dt.date.today()
            start = today - dt.timedelta(days=6)
            raw_items = client.quote_history(
                ids, start.isoformat(), today.isoformat()) if ids else []
    except DailyLimitReached as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail='富宝接口调用失败：%s' % exc)

    search_map = {str(item.get('productId')): item for item in search_items}
    candidates = {}
    for item in raw_items:
        product_id = str(item.get('productId') or '')
        if product_id:
            candidates[product_id] = payload_to_candidate(item, search_map.get(product_id))
    for product_id, item in search_map.items():
        candidates.setdefault(product_id, payload_to_candidate(item))

    bound = {}
    for row in conn.execute(
            'SELECT c.product_id, m.code, m.name FROM source_material_configs c '
            'LEFT JOIN materials m ON m.id = c.material_id '
            "WHERE c.status <> '已删除'").fetchall():
        bound[row['product_id']] = {
            'code': row['code'] or '',
            'name': row['name'] or '',
        }

    results = []
    for product_id, item in candidates.items():
        if payload.provinceId or payload.cityId:
            item['matched'] = place_matches(
                item['place'], names['provinceName'], names['cityName'],
                names['provinceShort'], names['cityShort'])
        else:
            item['matched'] = True
        item['boundMaterial'] = bound.get(product_id)
        results.append(item)
    results.sort(key=lambda row: (row['matched'], row['date'] or ''), reverse=True)

    return {
        'items': results,
        'total': total,
        'keyword': keyword,
        'province': {
            'id': payload.provinceId, 'name': names['provinceName'],
            'shortName': names['provinceShort'],
        },
        'city': {
            'id': payload.cityId, 'name': names['cityName'],
            'shortName': names['cityShort'],
        },
        'note': '富宝搜索接口不按省市过滤，已由本地按报价地区匹配。',
    }


@app.post('/api/collect/configs')
def create_collect_config(payload: CollectConfigPayload,
                          conn: sqlite3.Connection = Depends(database.get_db)):
    result = _save_config(conn, payload)
    if payload.syncHistory:
        result['backfill'] = start_backfill(
            conn, result['item']['id'], payload.historyDays)
    return result


@app.put('/api/collect/configs/{config_id}')
def update_collect_config(config_id: int, payload: CollectConfigPayload,
                          conn: sqlite3.Connection = Depends(database.get_db)):
    result = _save_config(conn, payload, config_id=config_id)
    if payload.syncHistory:
        result['backfill'] = start_backfill(
            conn, result['item']['id'], payload.historyDays)
    return result


@app.post('/api/collect/configs/{config_id}/toggle')
def toggle_collect_config(config_id: int,
                          conn: sqlite3.Connection = Depends(database.get_db)):
    row = conn.execute(
        'SELECT status, material_id, source_id FROM source_material_configs WHERE id = ?',
        (config_id,)).fetchone()
    if not row or row['status'] == '已删除':
        raise HTTPException(status_code=404, detail='采集配置不存在')
    status = '停用' if row['status'] == '启用' else '启用'
    if status == '启用':
        source_state = conn.execute(
            'SELECT COALESCE(enabled, 1) AS enabled FROM source_sync_settings '
            'WHERE source_id = ?', (row['source_id'],)).fetchone()
        if source_state and not source_state['enabled']:
            raise HTTPException(status_code=400, detail='网站总开关已关闭，请先启用网站同步')
    conn.execute(
        'UPDATE source_material_configs SET status = ?, updated_at = ? WHERE id = ?',
        (status, database.now_text(), config_id))
    if row['material_id']:
        conn.execute(
            'UPDATE material_aliases SET status = ? WHERE material_id = ? AND source_id = ?',
            ('已匹配' if status == '启用' else '停用',
             row['material_id'], row['source_id']))
    item = config_item(conn, config_id)
    log = database.log_operation(
        conn, '采集配置',
        '%s采集配置：%s / %s' % (status, item['externalName'], item['materialCode']))
    conn.commit()
    return {'item': item, 'log': log}


@app.post('/api/collect/configs/{config_id}/verify')
def verify_collect_config(config_id: int,
                          conn: sqlite3.Connection = Depends(database.get_db)):
    row = conn.execute(
        'SELECT product_id, source_id, external_name, external_web_name, external_place, '
        'external_spec, external_tax, external_unit, external_org, variety_id, classify_id '
        'FROM source_material_configs WHERE id = ?',
        (config_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail='采集配置不存在')
    source_state = conn.execute(
        'SELECT COALESCE(enabled, 1) AS enabled FROM source_sync_settings '
        'WHERE source_id = ?', (row['source_id'],)).fetchone()
    if source_state and not source_state['enabled']:
        raise HTTPException(status_code=400, detail='网站总开关已关闭，请先启用网站同步')
    gate = config_gate()
    try:
        with CONFIG_GATE_LOCK:
            client = build_f139_client(gate)
            detail = client.quote_detail(row['product_id'])
    except DailyLimitReached as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail='校验失败：%s' % exc)

    def keep(*values):
        """保留第一个非空值；富宝详情缺字段时不能把已有配置覆盖成空。"""
        for value in values:
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            return value
        return ''

    external_name = keep(detail.get('combinationName'), row['external_name'])
    if not external_name:
        parts = [
            keep(detail.get('place'), row['external_place']),
            keep(detail.get('webName'), detail.get('name'), row['external_web_name']),
            keep(detail.get('specification'), row['external_spec']),
            keep(detail.get('tax'), row['external_tax']),
        ]
        external_name = '-'.join(str(part).strip() for part in parts if str(part or '').strip())

    conn.execute(
        'UPDATE source_material_configs SET external_name = ?, external_web_name = ?, '
        'external_place = ?, external_spec = ?, external_tax = ?, external_unit = ?, '
        'external_org = ?, variety_id = ?, classify_id = ?, last_verified_at = ?, '
        'last_error = ?, updated_at = ? WHERE id = ?',
        (external_name,
         keep(detail.get('webName'), detail.get('name'), row['external_web_name']),
         keep(detail.get('place'), row['external_place']),
         keep(detail.get('specification'), row['external_spec']),
         keep(detail.get('tax'), row['external_tax']),
         keep(detail.get('unit'), row['external_unit'], '元/吨'),
         keep(detail.get('organization'), row['external_org']),
         keep(detail.get('varietyId'), row['variety_id']) or None,
         keep(detail.get('classifyId'), row['classify_id']) or None,
         database.now_text(), '', database.now_text(), config_id))
    item = config_item(conn, config_id)
    log = database.log_operation(
        conn, '采集配置', '校验采集配置：%s（productId=%s）' % (
            item['externalName'], item['productId']))
    conn.commit()
    return {'item': item, 'log': log}


@app.post('/api/collect/configs/{config_id}/backfill')
def backfill_collect_config(config_id: int, payload: BackfillPayload,
                            conn: sqlite3.Connection = Depends(database.get_db)):
    row = conn.execute(
        'SELECT product_id, external_name FROM source_material_configs WHERE id = ?',
        (config_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail='采集配置不存在')
    info = start_backfill(conn, config_id, payload.days, payload.reinit)
    if not info['started']:
        raise HTTPException(status_code=409, detail=info['reason'])
    item = config_item(conn, config_id)
    log = database.log_operation(
        conn, '采集配置',
        '启动历史回补：%s，%d 天（%d 个窗口）' % (
            item['externalName'], info['days'], info['windows']))
    return {'started': True, 'item': item, 'log': log, 'quota': info['quota'],
            'backfill': info,
            'message': '回补任务已启动（后台低频执行，可在列表查看进度）'}


@app.delete('/api/collect/configs/{config_id}')
def delete_collect_config(config_id: int,
                          conn: sqlite3.Connection = Depends(database.get_db)):
    row = conn.execute(
        'SELECT external_name, material_id, source_id FROM source_material_configs '
        'WHERE id = ?', (config_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail='采集配置不存在')
    conn.execute(
        "UPDATE source_material_configs SET status = '已删除', updated_at = ? WHERE id = ?",
        (database.now_text(), config_id))
    alias_note = ''
    if row['material_id']:
        active = conn.execute(
            "SELECT COUNT(*) AS n FROM source_material_configs "
            "WHERE source_id = ? AND material_id = ? AND status = '启用' AND id <> ?",
            (row['source_id'], row['material_id'], config_id)).fetchone()['n']
        if active == 0:
            conn.execute(
                "UPDATE material_aliases SET status = '停用' "
                'WHERE material_id = ? AND source_id = ?',
                (row['material_id'], row['source_id']))
            alias_note = '；映射已同步停用'
    log = database.log_operation(
        conn, '采集配置',
        '删除采集配置：%s%s' % (row['external_name'], alias_note))
    conn.commit()
    return {'id': config_id, 'log': log}


# ------------------------------------------------------------------ 写操作
class PricingParamUpdate(BaseModel):
    period: str = '周'
    offset: Optional[float] = None
    coefficient: Optional[float] = None
    sources: List[str] = []
    templateCode: Optional[str] = None


class PricingParamCreate(BaseModel):
    materialCode: str
    templateCode: str = 'TPL02'
    period: str = '周'
    offset: Optional[float] = 0
    coefficient: Optional[float] = 1
    sources: List[str] = []


class PricingRuleUpdate(BaseModel):
    templateCode: Optional[str] = None
    period: str = '周'
    offset: Optional[float] = None
    coefficient: Optional[float] = None
    status: Optional[str] = None


class PricingRuleCreate(BaseModel):
    sourceConfigId: int
    materialCode: str
    templateCode: str = 'TPL02'
    period: str = '周'
    offset: Optional[float] = 0
    coefficient: Optional[float] = 1


class GroupCoefficientPayload(BaseModel):
    coefficient: float


class MaterialCreate(BaseModel):
    name: str
    materialType: str = '系统'
    category: str = '废金属'
    unit: str = '元/吨'


class MappingPayload(BaseModel):
    """新增映射 = 系统物料 + 爬虫采集配置 + 计价参数。"""
    sourceConfigId: int
    materialCode: str
    templateCode: str = 'TPL02'
    period: str = '周'
    offset: Optional[float] = 0
    coefficient: Optional[float] = 1


class MappingUpdatePayload(BaseModel):
    templateCode: Optional[str] = None
    period: str = '周'
    offset: Optional[float] = None
    coefficient: Optional[float] = None
    status: Optional[str] = None


class MappingImportPayload(BaseModel):
    text: str


class TemplateUpdate(BaseModel):
    name: str
    factors: List[str] = []


class ReviewUpdate(BaseModel):
    status: str


@app.post('/api/mappings/{mapping_id}/toggle')
def toggle_mapping(mapping_id: int, conn: sqlite3.Connection = Depends(database.get_db)):
    """启停映射（计价规则）：仅停止该系统物料计价，不影响行情采集。"""
    row = conn.execute(
        'SELECT id, status FROM material_pricing_rules WHERE id = ?',
        (mapping_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail='映射不存在')
    status = '停用' if row['status'] == '生效' else '生效'
    conn.execute(
        'UPDATE material_pricing_rules SET status = ?, updated_at = ? WHERE id = ?',
        (status, database.now_text(), mapping_id))
    item = mapping_item(conn, mapping_id)
    log = database.log_operation(
        conn, '物料映射变更',
        '%s：%s %s ↔ %s「%s」（%s计价，不影响行情采集）' % (
            status, item['materialCode'], item['materialName'],
            item['source'], item['keyword'], '停止' if status == '停用' else '恢复'))
    return {'item': item, 'log': log}


@app.post('/api/mappings')
def create_mapping(payload: MappingPayload,
                   conn: sqlite3.Connection = Depends(database.get_db)):
    config = conn.execute(
        'SELECT id FROM source_material_configs WHERE id = ? AND status <> ?',
        (payload.sourceConfigId, '已删除')).fetchone()
    if not config:
        raise HTTPException(status_code=400, detail='爬虫采集配置不存在')
    material = conn.execute(
        'SELECT id, material_type FROM materials WHERE code = ?',
        (payload.materialCode,)).fetchone()
    if not material:
        raise HTTPException(status_code=400, detail='系统物料不存在：%s' % payload.materialCode)
    if material['material_type'] != '系统':
        raise HTTPException(status_code=400, detail='映射只能绑定公司系统物料（XT 开头）')
    template = conn.execute(
        'SELECT id FROM pricing_templates WHERE code = ?',
        (payload.templateCode,)).fetchone()
    if not template:
        raise HTTPException(status_code=400, detail='模板不存在：%s' % payload.templateCode)
    exists = conn.execute(
        'SELECT id FROM material_pricing_rules WHERE source_config_id = ? '
        'AND material_id = ? AND version = 1',
        (payload.sourceConfigId, material['id'])).fetchone()
    if exists:
        raise HTTPException(status_code=400, detail='该爬虫物料已映射此系统物料，请直接编辑')
    cursor = conn.execute(
        'INSERT INTO material_pricing_rules '
        '(source_config_id, material_id, template_id, period_type, offset_value, '
        'coefficient, status, version, effective_from, updated_at) '
        "VALUES (?, ?, ?, ?, ?, ?, '生效', 1, ?, ?)",
        (payload.sourceConfigId, material['id'], template['id'], payload.period or '周',
         payload.offset, payload.coefficient, dt.date.today().isoformat(),
         database.now_text()))
    item = mapping_item(conn, cursor.lastrowid)
    log = database.log_operation(
        conn, '物料映射变更',
        '新增映射：%s %s ↔ %s「%s」（调整值 %s / 系数 %s）' % (
            item['materialCode'], item['materialName'], item['source'],
            item['keyword'], item['offset'], item['coefficient']))
    conn.commit()
    return {'item': item, 'log': log}


@app.put('/api/mappings/{mapping_id}')
def update_mapping(mapping_id: int, payload: MappingUpdatePayload,
                   conn: sqlite3.Connection = Depends(database.get_db)):
    row = conn.execute(
        'SELECT id FROM material_pricing_rules WHERE id = ?', (mapping_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail='映射不存在')
    status = payload.status or '生效'
    if status not in ('生效', '停用'):
        raise HTTPException(status_code=400, detail='非法映射状态')
    template_id = None
    if payload.templateCode:
        template = conn.execute(
            'SELECT id FROM pricing_templates WHERE code = ?',
            (payload.templateCode,)).fetchone()
        if not template:
            raise HTTPException(status_code=400, detail='模板不存在：%s' % payload.templateCode)
        template_id = template['id']
    if template_id:
        conn.execute(
            'UPDATE material_pricing_rules SET template_id = ?, period_type = ?, '
            'offset_value = ?, coefficient = ?, status = ?, updated_at = ? WHERE id = ?',
            (template_id, payload.period or '周', payload.offset, payload.coefficient,
             status, database.now_text(), mapping_id))
    else:
        conn.execute(
            'UPDATE material_pricing_rules SET period_type = ?, offset_value = ?, '
            'coefficient = ?, status = ?, updated_at = ? WHERE id = ?',
            (payload.period or '周', payload.offset, payload.coefficient,
             status, database.now_text(), mapping_id))
    item = mapping_item(conn, mapping_id)
    log = database.log_operation(
        conn, '物料映射变更',
        '编辑映射：%s %s ↔ %s「%s」：调整值 %s / 系数 %s / %s' % (
            item['materialCode'], item['materialName'], item['source'],
            item['keyword'], item['offset'], item['coefficient'], item['status']))
    conn.commit()
    return {'item': item, 'log': log}


@app.post('/api/mappings/batch-import')
def batch_import_mappings(payload: MappingImportPayload,
                          conn: sqlite3.Connection = Depends(database.get_db)):
    """批量导入映射：每行 系统物料编码, productId, 固定调整值, 调价系数。"""
    created = 0
    updated = 0
    errors = []
    template = conn.execute(
        "SELECT id FROM pricing_templates WHERE code = 'TPL02'").fetchone()
    for index, raw_line in enumerate((payload.text or '').splitlines(), 1):
        line = raw_line.strip().lstrip('\ufeff')
        if not line or line.startswith('#'):
            continue
        if '系统物料编码' in line or 'material_code' in line.lower():
            continue
        parts = [part.strip().strip('"') for part in re.split(r'[,\t]', line)]
        if len(parts) < 2:
            errors.append('第 %d 行：至少需要 系统物料编码,productId' % index)
            continue
        material_code, product_id = parts[0], parts[1]
        try:
            offset = float(parts[2]) if len(parts) > 2 and parts[2] else 0
            coefficient = float(parts[3]) if len(parts) > 3 and parts[3] else 1.0
        except ValueError:
            errors.append('第 %d 行：调整值/系数必须是数字' % index)
            continue

        material = conn.execute(
            'SELECT id FROM materials WHERE code = ?', (material_code,)).fetchone()
        config = conn.execute(
            'SELECT id FROM source_material_configs WHERE product_id = ? '
            "AND status <> '已删除' ORDER BY id LIMIT 1", (product_id,)).fetchone()
        if not material or not config:
            errors.append('第 %d 行：系统物料或采集配置不存在（%s / productId=%s）' % (
                index, material_code, product_id))
            continue
        existing = conn.execute(
            'SELECT id FROM material_pricing_rules WHERE source_config_id = ? '
            'AND material_id = ? AND version = 1',
            (config['id'], material['id'])).fetchone()
        if existing:
            conn.execute(
                'UPDATE material_pricing_rules SET offset_value = ?, coefficient = ?, '
                "status = '生效', updated_at = ? WHERE id = ?",
                (offset, coefficient, database.now_text(), existing['id']))
            updated += 1
        else:
            conn.execute(
                'INSERT INTO material_pricing_rules '
                '(source_config_id, material_id, template_id, period_type, offset_value, '
                'coefficient, status, version, effective_from, updated_at) '
                "VALUES (?, ?, ?, '周', ?, ?, '生效', 1, ?, ?)",
                (config['id'], material['id'], template['id'] if template else None,
                 offset, coefficient, dt.date.today().isoformat(),
                 database.now_text()))
            created += 1

    log = database.log_operation(
        conn, '物料映射变更',
        '批量导入映射：新增 %d 条，更新 %d 条，失败 %d 条' % (
            created, updated, len(errors)))
    conn.commit()
    return {
        'created': created,
        'updated': updated,
        'errors': errors,
        'log': log,
    }


@app.post('/api/pricing-params')
def create_param(payload: PricingParamCreate,
                 conn: sqlite3.Connection = Depends(database.get_db)):
    material = conn.execute(
        'SELECT id, code, name FROM materials WHERE code = ?',
        (payload.materialCode,)).fetchone()
    if not material:
        raise HTTPException(status_code=400, detail='系统物料不存在：%s' % payload.materialCode)
    existing = conn.execute(
        'SELECT version FROM pricing_params WHERE material_id = ? '
        'ORDER BY version DESC LIMIT 1', (material['id'],)).fetchone()
    version = (existing['version'] + 1) if existing else 1
    if existing:
        conn.execute(
            "UPDATE pricing_params SET status = '停用', updated_at = ? "
            'WHERE material_id = ?', (database.now_text(), material['id']))
    template = conn.execute(
        'SELECT id FROM pricing_templates WHERE code = ?',
        (payload.templateCode,)).fetchone()
    if not template:
        raise HTTPException(status_code=400, detail='模板不存在：%s' % payload.templateCode)

    cursor = conn.execute(
        'INSERT INTO pricing_params '
        '(material_id, template_id, period_type, offset_value, coefficient, status, '
        'version, effective_from, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (material['id'], template['id'], payload.period, payload.offset,
         payload.coefficient, '生效', version, dt.date.today().isoformat(),
         database.now_text()))
    param_id = cursor.lastrowid
    for source_name in payload.sources:
        source = conn.execute(
            'SELECT id FROM market_sources WHERE name = ?', (source_name,)).fetchone()
        if source:
            conn.execute(
                'INSERT OR IGNORE INTO pricing_param_sources (param_id, source_id) '
                'VALUES (?, ?)', (param_id, source['id']))
    item = param_item(conn, param_id)
    log = database.log_operation(
        conn, '参数修改',
        '新增 %s %s 定价参数 v%s：%s / %s / 偏移 %s / 系数 %s' % (
            item['materialCode'], item['materialName'], item['version'],
            item['templateCode'], item['period'], item['offset'], item['coefficient']))
    conn.commit()
    return {'item': item, 'log': log}


@app.put('/api/pricing-params/{param_id}')
def update_param(param_id: int, payload: PricingParamUpdate,
                 conn: sqlite3.Connection = Depends(database.get_db)):
    row = conn.execute(
        'SELECT id FROM pricing_params WHERE id = ?', (param_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail='定价参数不存在')
    template_id = None
    if payload.templateCode:
        template = conn.execute(
            'SELECT id FROM pricing_templates WHERE code = ?',
            (payload.templateCode,)).fetchone()
        if not template:
            raise HTTPException(status_code=400, detail='模板不存在：%s' % payload.templateCode)
        template_id = template['id']
    if template_id:
        conn.execute(
            'UPDATE pricing_params SET template_id = ?, period_type = ?, '
            'offset_value = ?, coefficient = ?, updated_at = ? WHERE id = ?',
            (template_id, payload.period, payload.offset, payload.coefficient,
             database.now_text(), param_id))
    else:
        conn.execute(
            'UPDATE pricing_params SET period_type = ?, offset_value = ?, coefficient = ?, '
            'updated_at = ? WHERE id = ?',
            (payload.period, payload.offset, payload.coefficient,
             database.now_text(), param_id))
    conn.execute('DELETE FROM pricing_param_sources WHERE param_id = ?', (param_id,))
    for source_name in payload.sources:
        source = conn.execute(
            'SELECT id FROM market_sources WHERE name = ?', (source_name,)).fetchone()
        if source:
            conn.execute(
                'INSERT OR IGNORE INTO pricing_param_sources (param_id, source_id) '
                'VALUES (?, ?)', (param_id, source['id']))
    item = param_item(conn, param_id)
    log = database.log_operation(
        conn, '参数修改',
        '%s 定价参数已保存：偏移 %s / 系数 %s' % (
            item['materialCode'],
            ('+' if (item['offset'] or 0) >= 0 else '') + str(item['offset']),
            ('%.2f' % item['coefficient']) if item['coefficient'] is not None else '—'))
    return {'item': item, 'log': log}


# ------------------------------------------------------------------ 计价规则接口
@app.post('/api/materials')
def create_material(payload: MaterialCreate,
                    conn: sqlite3.Connection = Depends(database.get_db)):
    """新增物料：默认公司系统物料（XT 编码），也可指定网站物料。"""
    name = (payload.name or '').strip()
    if not name:
        raise HTTPException(status_code=400, detail='物料名称不能为空')
    material_type = payload.materialType if payload.materialType in ('系统', '网站') else '系统'
    exists = conn.execute(
        'SELECT code, name, category, unit, material_type FROM materials '
        'WHERE name = ? AND material_type = ?', (name, material_type)).fetchone()
    if exists:
        return {
            'item': {
                'code': exists['code'],
                'name': exists['name'],
                'category': exists['category'],
                'unit': exists['unit'],
                'materialType': exists['material_type'],
            },
            'created': False,
        }
    code = next_system_material_code(conn) if material_type == '系统' else next_material_code(conn)
    conn.execute(
        'INSERT INTO materials (code, name, category, unit, material_type) '
        'VALUES (?, ?, ?, ?, ?)',
        (code, name, payload.category or '废金属', payload.unit or '元/吨', material_type))
    log = database.log_operation(
        conn, '参数修改', '新增%s物料：%s %s' % (material_type, code, name))
    conn.commit()
    return {
        'item': {
            'code': code,
            'name': name,
            'category': payload.category or '废金属',
            'unit': payload.unit or '元/吨',
            'materialType': material_type,
        },
        'created': True,
        'log': log,
    }


def rule_log_text(item: dict) -> str:
    return '%s（%s）→ %s %s：固定调整值 %s / 调价系数 %s' % (
        item['sourceMaterialCode'] or '网站物料', item['source'],
        item['materialCode'], item['materialName'],
        ('+' if (item['offset'] or 0) > 0 else '') + str(item['offset'] or 0),
        '%.2f' % (item['coefficient'] if item['coefficient'] is not None else 1))


@app.get('/api/pricing-rules')
def list_pricing_rules(conn: sqlite3.Connection = Depends(database.get_db)):
    return query_pricing_rules(conn)


@app.post('/api/pricing-rules')
def create_pricing_rule(payload: PricingRuleCreate,
                        conn: sqlite3.Connection = Depends(database.get_db)):
    config = conn.execute(
        'SELECT id, material_id FROM source_material_configs WHERE id = ? '
        "AND status <> '已删除'", (payload.sourceConfigId,)).fetchone()
    if not config:
        raise HTTPException(status_code=400, detail='网站物料采集配置不存在')
    material = conn.execute(
        'SELECT id, material_type FROM materials WHERE code = ?',
        (payload.materialCode,)).fetchone()
    if not material:
        raise HTTPException(status_code=400, detail='系统物料不存在：%s' % payload.materialCode)
    if material['material_type'] != '系统':
        raise HTTPException(status_code=400, detail='计价规则只能绑定公司系统物料（XT 开头）')
    template = conn.execute(
        'SELECT id FROM pricing_templates WHERE code = ?',
        (payload.templateCode,)).fetchone()
    if not template:
        raise HTTPException(status_code=400, detail='模板不存在：%s' % payload.templateCode)
    exists = conn.execute(
        'SELECT id FROM material_pricing_rules WHERE source_config_id = ? '
        'AND material_id = ? AND version = 1',
        (payload.sourceConfigId, material['id'])).fetchone()
    if exists:
        raise HTTPException(status_code=400, detail='该网站物料已配置此系统物料')
    cursor = conn.execute(
        'INSERT INTO material_pricing_rules '
        '(source_config_id, material_id, template_id, period_type, offset_value, '
        'coefficient, status, version, effective_from, updated_at) '
        "VALUES (?, ?, ?, ?, ?, ?, '生效', 1, ?, ?)",
        (payload.sourceConfigId, material['id'], template['id'], payload.period or '周',
         payload.offset, payload.coefficient, dt.date.today().isoformat(),
         database.now_text()))
    item = pricing_rule_item(conn, cursor.lastrowid)
    log = database.log_operation(
        conn, '参数修改', '新增计价规则：%s' % rule_log_text(item))
    conn.commit()
    return {'item': item, 'log': log}


@app.put('/api/pricing-rules/{rule_id}')
def update_pricing_rule(rule_id: int, payload: PricingRuleUpdate,
                        conn: sqlite3.Connection = Depends(database.get_db)):
    row = conn.execute(
        'SELECT id FROM material_pricing_rules WHERE id = ?', (rule_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail='计价规则不存在')
    status = payload.status or '生效'
    if status not in ('生效', '停用'):
        raise HTTPException(status_code=400, detail='非法规则状态')
    template_id = None
    if payload.templateCode:
        template = conn.execute(
            'SELECT id FROM pricing_templates WHERE code = ?',
            (payload.templateCode,)).fetchone()
        if not template:
            raise HTTPException(status_code=400, detail='模板不存在：%s' % payload.templateCode)
        template_id = template['id']
    if template_id:
        conn.execute(
            'UPDATE material_pricing_rules SET template_id = ?, period_type = ?, '
            'offset_value = ?, coefficient = ?, status = ?, updated_at = ? WHERE id = ?',
            (template_id, payload.period or '周', payload.offset, payload.coefficient,
             status, database.now_text(), rule_id))
    else:
        conn.execute(
            'UPDATE material_pricing_rules SET period_type = ?, offset_value = ?, '
            'coefficient = ?, status = ?, updated_at = ? WHERE id = ?',
            (payload.period or '周', payload.offset, payload.coefficient,
             status, database.now_text(), rule_id))
    item = pricing_rule_item(conn, rule_id)
    log = database.log_operation(
        conn, '参数修改',
        '保存计价规则：%s（%s）' % (rule_log_text(item), item['status']))
    conn.commit()
    return {'item': item, 'log': log}


@app.post('/api/pricing-rules/group/{source_config_id}/coefficient')
def apply_group_coefficient(source_config_id: int, payload: GroupCoefficientPayload,
                            conn: sqlite3.Connection = Depends(database.get_db)):
    """把统一调价系数应用到该网站物料下的全部系统物料规则。"""
    rows = conn.execute(
        'SELECT id FROM material_pricing_rules WHERE source_config_id = ?',
        (source_config_id,)).fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail='该网站物料尚未配置计价规则')
    conn.execute(
        'UPDATE material_pricing_rules SET coefficient = ?, updated_at = ? '
        'WHERE source_config_id = ?',
        (payload.coefficient, database.now_text(), source_config_id))
    ids = [row['id'] for row in rows]
    items = [pricing_rule_item(conn, rule_id) for rule_id in ids]
    log = database.log_operation(
        conn, '参数修改',
        '统一调价系数：%d 条规则统一设为 %.2f' % (len(items), payload.coefficient))
    conn.commit()
    return {'items': items, 'log': log}


@app.put('/api/templates/{template_id}')
def update_template(template_id: int, payload: TemplateUpdate,
                    conn: sqlite3.Connection = Depends(database.get_db)):
    row = conn.execute(
        'SELECT id FROM pricing_templates WHERE id = ?', (template_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail='模板不存在')
    conn.execute(
        'UPDATE pricing_templates SET name = ?, updated_at = ? WHERE id = ?',
        (payload.name, database.now_text(), template_id))
    conn.execute(
        'DELETE FROM pricing_template_factors WHERE template_id = ?', (template_id,))
    for order, factor in enumerate(payload.factors):
        conn.execute(
            'INSERT INTO pricing_template_factors (template_id, factor, sort_order) '
            'VALUES (?, ?, ?)', (template_id, factor, order))
    item = template_item(conn, template_id)
    log = database.log_operation(
        conn, '模板修改',
        '%s 模板已保存：%s' % (item['code'], '、'.join(item['factors'])))
    return {'item': item, 'log': log}


@app.post('/api/results/{result_id}/review')
def review_result(result_id: int, payload: ReviewUpdate,
                  conn: sqlite3.Connection = Depends(database.get_db)):
    if payload.status not in ('已复核', '已驳回', '待复核'):
        raise HTTPException(status_code=400, detail='非法复核状态')
    row = conn.execute(
        'SELECT id FROM calc_results WHERE id = ?', (result_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail='计价结果不存在')
    conn.execute(
        'UPDATE calc_results SET review_status = ?, reviewer = ?, reviewed_at = ?, '
        'reject_reason = ? WHERE id = ?',
        (payload.status, '王莉洁', database.now_text(),
         '演示驳回' if payload.status == '已驳回' else None, result_id))
    item = result_item(conn, result_id)
    log = database.log_operation(
        conn, '复核',
        '%s %s 计价结果：%s' % (item['materialCode'], item['materialName'], payload.status))
    return {'item': item, 'log': log}


@app.post('/api/results/batch-approve')
def batch_approve(conn: sqlite3.Connection = Depends(database.get_db)):
    rows = conn.execute(
        "SELECT id FROM calc_results WHERE review_status = '待复核'").fetchall()
    ids = [row['id'] for row in rows]
    for result_id in ids:
        conn.execute(
            'UPDATE calc_results SET review_status = ?, reviewer = ?, reviewed_at = ? '
            'WHERE id = ?',
            ('已复核', '王莉洁', database.now_text(), result_id))
    items = [result_item(conn, result_id) for result_id in ids]
    log = None
    if ids:
        log = database.log_operation(
            conn, '复核', '批量复核通过 %d 条计价结果' % len(ids))
    return {'count': len(ids), 'items': items, 'log': log}


@app.post('/api/schedules/{schedule_id}/run')
def run_schedule(schedule_id: int, conn: sqlite3.Connection = Depends(database.get_db)):
    row = conn.execute(
        'SELECT id, name, cycle FROM calc_schedules WHERE id = ?',
        (schedule_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail='任务不存在')
    return execute_pricing(conn, row, schedule_id)


# ------------------------------------------------------------------ 生产静态页面
DIST_DIR = os.path.join(database.APP_DIR, 'dist')
if os.path.isdir(DIST_DIR):
    app.mount('/', StaticFiles(directory=DIST_DIR, html=True), name='static')
