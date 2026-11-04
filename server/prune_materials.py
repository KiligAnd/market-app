# -*- coding: utf-8 -*-
"""一次性清理非保留物料及其关联数据。

用法：
    python prune_materials.py --dry-run   # 默认，只打印
    python prune_materials.py --apply     # 备份后执行
"""
import argparse
import datetime as dt
import json
import os
import sqlite3
import sys

import db as database

DEFAULT_KEEP = ('WB00001', 'WB00002')
DEFAULT_DROP_SCHEDULES = ('报废车业务周度计价', '固废业务月度计价')
NEW_SCHEDULE = '废金属周度计价'


def table_counts(conn, removed_ids, keep_unmatched=False) -> dict:
    placeholders = ','.join('?' for _ in removed_ids)
    params = list(removed_ids)
    quote_extra = '' if keep_unmatched else ' OR material_id IS NULL'
    return {
        'materials': conn.execute(
            'SELECT COUNT(*) FROM materials WHERE id IN (%s)' % placeholders,
            params).fetchone()[0],
        'quotes': conn.execute(
            'SELECT COUNT(*) FROM market_quotes WHERE material_id IN (%s)%s' % (
                placeholders, quote_extra), params).fetchone()[0],
        'aliases': conn.execute(
            'SELECT COUNT(*) FROM material_aliases WHERE material_id IN (%s)' % placeholders,
            params).fetchone()[0],
        'params': conn.execute(
            'SELECT COUNT(*) FROM pricing_params WHERE material_id IN (%s)' % placeholders,
            params).fetchone()[0],
        'param_sources': conn.execute(
            'SELECT COUNT(*) FROM pricing_param_sources ps '
            'JOIN pricing_params p ON p.id = ps.param_id '
            'WHERE p.material_id IN (%s)' % placeholders, params).fetchone()[0],
        'results': conn.execute(
            'SELECT COUNT(*) FROM calc_results WHERE material_id IN (%s)' % placeholders,
            params).fetchone()[0],
    }


def list_removed(conn, removed_ids) -> list:
    placeholders = ','.join('?' for _ in removed_ids)
    return [dict(row) for row in conn.execute(
        'SELECT id, code, name FROM materials WHERE id IN (%s) ORDER BY id' % placeholders,
        list(removed_ids))]


def backup_database() -> str:
    backup_dir = os.path.join(database.APP_DATA_DIR, 'backup')
    os.makedirs(backup_dir, exist_ok=True)
    stamp = dt.datetime.now().strftime('%Y%m%d-%H%M%S')
    path = os.path.join(backup_dir, 'market-%s.db' % stamp)
    src = sqlite3.connect(database.DB_PATH)
    dst = sqlite3.connect(path)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return path


def write_manifest(path: str, payload: dict) -> None:
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


def next_monday(today: dt.date) -> dt.date:
    days = (0 - today.weekday()) % 7
    return today + dt.timedelta(days=days or 7)


def apply_cleanup(conn, removed_ids, counts: dict, keep_unmatched: bool,
                  drop_schedules: bool) -> dict:
    placeholders = ','.join('?' for _ in removed_ids)
    params = list(removed_ids)
    now = database.now_text()

    conn.execute('BEGIN IMMEDIATE')
    conn.execute(
        'DELETE FROM market_quotes WHERE material_id IN (%s)' % placeholders, params)
    if not keep_unmatched:
        conn.execute('DELETE FROM market_quotes WHERE material_id IS NULL')
    conn.execute(
        'DELETE FROM calc_results WHERE material_id IN (%s)' % placeholders, params)
    conn.execute(
        'DELETE FROM pricing_params WHERE material_id IN (%s)' % placeholders, params)
    conn.execute(
        'DELETE FROM material_aliases WHERE material_id IN (%s)' % placeholders, params)
    conn.execute(
        'DELETE FROM materials WHERE id IN (%s)' % placeholders, params)

    # 删除已没有任何结果的批次
    empty_batches = conn.execute(
        'DELETE FROM calc_runs WHERE id NOT IN '
        '(SELECT DISTINCT run_id FROM calc_results)').rowcount
    # 剩余批次按真实结果数校正
    conn.execute(
        'UPDATE calc_runs SET '
        'total_count = (SELECT COUNT(*) FROM calc_results c WHERE c.run_id = calc_runs.id), '
        'success_count = (SELECT COUNT(*) FROM calc_results c WHERE c.run_id = calc_runs.id), '
        'fail_count = 0')

    dropped_schedules = 0
    if drop_schedules:
        marks = ','.join('?' for _ in DEFAULT_DROP_SCHEDULES)
        dropped_schedules = conn.execute(
            'DELETE FROM calc_schedules WHERE name IN (%s)' % marks,
            list(DEFAULT_DROP_SCHEDULES)).rowcount
        exists = conn.execute(
            'SELECT id FROM calc_schedules WHERE name = ?', (NEW_SCHEDULE,)).fetchone()
        if not exists:
            monday = next_monday(dt.date.today())
            conn.execute(
                'INSERT INTO calc_schedules '
                '(name, cycle, status, last_run_at, next_run_at) '
                'VALUES (?, ?, ?, ?, ?)',
                (NEW_SCHEDULE, '每周一 08:00', '运行中',
                 (monday - dt.timedelta(days=7)).strftime('%Y-%m-%d 08:00'),
                 monday.strftime('%Y-%m-%d 08:00')))

    content = (
        '清理非保留物料：删除 %d 个物料、%d 条行情、%d 条映射、%d 条参数、%d 条计价结果、%d 个空批次%s' % (
            counts['materials'], counts['quotes'], counts['aliases'],
            counts['params'], counts['results'], empty_batches,
            '，并移除 %d 个旧计价任务' % dropped_schedules if dropped_schedules else ''))
    conn.execute(
        'INSERT INTO operation_logs (log_time, action_type, operator, content, ip) '
        'VALUES (?, ?, ?, ?, ?)',
        (now, '物料清理', '系统', content, '127.0.0.1'))
    conn.commit()
    return {'emptyBatches': empty_batches, 'droppedSchedules': dropped_schedules}


def main() -> int:
    parser = argparse.ArgumentParser(description='清理非保留物料及相关数据')
    parser.add_argument('--apply', action='store_true', help='实际执行；默认只打印')
    parser.add_argument('--dry-run', action='store_true', help='只打印，不修改（默认行为）')
    parser.add_argument('--keep', default=','.join(DEFAULT_KEEP),
                        help='保留的物料编码，逗号分隔')
    parser.add_argument('--keep-unmatched', action='store_true',
                        help='保留 material_id 为空的未匹配演示行情')
    parser.add_argument('--keep-schedules', action='store_true',
                        help='保留原计价任务，不删除/替换')
    args = parser.parse_args()

    keep = tuple(code.strip() for code in args.keep.split(',') if code.strip())
    if not keep:
        print('必须至少保留一个物料')
        return 2

    conn = database.connect()
    try:
        marks = ','.join('?' for _ in keep)
        removed = conn.execute(
            'SELECT id FROM materials WHERE code NOT IN (%s)' % marks, list(keep)).fetchall()
        removed_ids = [row['id'] for row in removed]
        if not removed_ids:
            print('没有需要清理的物料')
            return 0

        removed_rows = list_removed(conn, removed_ids)
        counts = table_counts(conn, removed_ids, keep_unmatched=args.keep_unmatched)
        print('保留物料：%s' % '、'.join(keep))
        print('将删除物料：')
        for row in removed_rows:
            print('  %s %s' % (row['code'], row['name']))
        print('关联数据：行情 %d 条，映射 %d 条，参数 %d 条（来源关联 %d 条），'
              '计价结果 %d 条' % (
                  counts['quotes'], counts['aliases'], counts['params'],
                  counts['param_sources'], counts['results']))
        print('未匹配演示行情：%s' % ('保留' if args.keep_unmatched else '一并删除'))
        print('旧计价任务：%s' % ('保留' if args.keep_schedules else '删除并替换为「%s」' % NEW_SCHEDULE))

        if not args.apply:
            print('\n当前为 dry-run，未修改数据库。加 --apply 执行。')
            return 0

        backup_path = backup_database()
        manifest_path = backup_path.replace('.db', '.json')
        write_manifest(manifest_path, {
            'keep': list(keep),
            'removed': removed_rows,
            'counts': counts,
            'backup': backup_path,
        })
        print('已备份：%s' % backup_path)

        result = apply_cleanup(
            conn, removed_ids, counts, args.keep_unmatched, not args.keep_schedules)
        print('清理完成：空批次 %d 个，旧任务 %d 个' % (
            result['emptyBatches'], result['droppedSchedules']))

        remaining = conn.execute(
            'SELECT code, name FROM materials ORDER BY id').fetchall()
        print('剩余物料：%s' % '、'.join('%s %s' % (row['code'], row['name']) for row in remaining))
        print('剩余行情：%d 条' % conn.execute(
            'SELECT COUNT(*) FROM market_quotes').fetchone()[0])
        conn.execute('VACUUM')
        return 0
    finally:
        conn.close()


if __name__ == '__main__':
    sys.exit(main())
