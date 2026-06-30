"""清理历史 observation 中的 value 重复行。

策略：对每条 indicator 的 observations 按日期升序，**保留每个 value run
的第一行**（值首次出现的那一行），删除同一 value 的后续重复行。

举例：
  Before:  06-11=30, 06-12=30, 06-13=30, 06-14=31, 06-15=31, 06-30=32
  After:   06-11=30, 06-14=31, 06-30=32

效果：Timeline 仅显示"值首次变化的时间点"，与代码层 skip_unchanged
行为对齐。

安全：每条 indicator 处理前 print plan，require --confirm 才执行删除。
"""
import argparse
import sqlite3
import sys


def plan_cleanup(conn) -> tuple[int, int, list[tuple]]:
    """返回 (total_before, total_after, per_indicator_stats)。

    per_indicator_stats: [(indicator_id, name, before, after, to_delete), ...]
    """
    c = conn.cursor()
    c.execute('''
        SELECT i.id, i.name, COUNT(o.id)
        FROM key_indicators i
        LEFT JOIN indicator_observations o ON o.indicator_id = i.id
        GROUP BY i.id
        HAVING COUNT(o.id) > 0
        ORDER BY i.id
    ''')
    indicator_obs_counts = c.fetchall()

    total_before = 0
    total_after = 0
    per_ind = []

    for ind_id, ind_name, before in indicator_obs_counts:
        c.execute('''
            SELECT id, date, value FROM indicator_observations
            WHERE indicator_id = ?
            ORDER BY date ASC, id ASC
        ''', (ind_id,))
        rows = c.fetchall()
        total_before += len(rows)

        keep_ids = []
        prev_value = None
        for row_id, row_date, row_value in rows:
            if prev_value is None or row_value != prev_value:
                keep_ids.append(row_id)
                prev_value = row_value
        after = len(keep_ids)
        total_after += after
        per_ind.append((ind_id, ind_name, before, after, before - after))

    return total_before, total_after, per_ind


def execute_cleanup(conn, per_ind) -> int:
    """实际删除，返回总删除行数。"""
    c = conn.cursor()
    total_deleted = 0
    for ind_id, ind_name, before, after, to_delete in per_ind:
        if to_delete == 0:
            continue
        # 重新获取当前 row ids (考虑 plan 和 execute 之间可能有变化)
        c.execute('''
            SELECT id, date, value FROM indicator_observations
            WHERE indicator_id = ?
            ORDER BY date ASC, id ASC
        ''', (ind_id,))
        rows = c.fetchall()
        keep_ids = []
        prev_value = None
        for row_id, row_date, row_value in rows:
            if prev_value is None or row_value != prev_value:
                keep_ids.append(row_id)
                prev_value = row_value
        delete_ids = [r[0] for r in rows if r[0] not in set(keep_ids)]
        if delete_ids:
            placeholders = ','.join('?' * len(delete_ids))
            c.execute(f'DELETE FROM indicator_observations WHERE id IN ({placeholders})', delete_ids)
            total_deleted += len(delete_ids)
    conn.commit()
    return total_deleted


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--db', required=True, help='SQLite DB path')
    p.add_argument('--confirm', action='store_true', help='actually delete')
    args = p.parse_args()

    conn = sqlite3.connect(args.db)
    total_before, total_after, per_ind = plan_cleanup(conn)

    print(f'=== Plan: keep first occurrence of each value run ===')
    print(f'  Total observations before: {total_before}')
    print(f'  Total observations after:  {total_after}')
    print(f'  Total to delete:          {total_before - total_after}')
    print()
    print(f'{"id":>3} {"name":<40} {"before":>6} {"after":>6} {"delete":>6}')
    print('-' * 70)
    for ind_id, ind_name, before, after, to_delete in per_ind:
        marker = '' if to_delete == 0 else f'  ← -{to_delete}'
        print(f'{ind_id:>3} {ind_name:<40} {before:>6} {after:>6} {to_delete:>6}{marker}')

    if not args.confirm:
        print()
        print('Dry run only. Re-run with --confirm to execute deletion.')
        sys.exit(0)

    print()
    print('=== Executing ===')
    deleted = execute_cleanup(conn, per_ind)
    print(f'Deleted: {deleted} rows')
    print()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM indicator_observations')
    print(f'Final observation count: {c.fetchone()[0]}')
    conn.close()


if __name__ == '__main__':
    main()