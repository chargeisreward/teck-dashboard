"""清理 timeline_events 表中的重复 collection 事件。

问题：trigger_industry_collect 每次 cron 都会为每个成功 collector 创建
TimelineEvent，即使 observation 值没变。导致 timeline 里同一指标
（china_customs、nvidia_ir）每天重复刷屏。

策略：
- 只处理 event_type='collection' 的事件
- 对同一 indicator_name_cn + 同一 value_display，只保留时间最早的一条
- 删除后续重复
"""
import argparse
import sqlite3


def plan_timeline_cleanup(conn):
    c = conn.cursor()
    c.execute('''
        SELECT id, event_time, event_type, title, value_display, source_name
        FROM timeline_events
        WHERE event_type = 'collection'
        ORDER BY title, event_time ASC
    ''')
    rows = c.fetchall()

    keep = []
    delete = []
    seen = set()  # title -> first id
    for r in rows:
        row_id, event_time, event_type, title, value_display, source_name = r
        if title not in seen:
            seen.add(title)
            keep.append(row_id)
        else:
            delete.append(row_id)

    return keep, delete


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--db', required=True)
    p.add_argument('--confirm', action='store_true')
    args = p.parse_args()

    conn = sqlite3.connect(args.db)
    keep, delete = plan_timeline_cleanup(conn)

    print(f'Collection timeline events: keep={len(keep)}, delete={len(delete)}')

    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM timeline_events WHERE event_type='collection'")
    total = c.fetchone()[0]
    print(f'Total collection events: {total}')

    if not args.confirm:
        print()
        print('Dry run. Use --confirm to delete.')
        return

    if delete:
        placeholders = ','.join('?' * len(delete))
        c.execute(f'DELETE FROM timeline_events WHERE id IN ({placeholders})', delete)
        conn.commit()
        print(f'Deleted {len(delete)} duplicate timeline events.')
    else:
        print('No duplicates to delete.')

    c.execute("SELECT COUNT(*) FROM timeline_events")
    print(f'Final timeline_events count: {c.fetchone()[0]}')
    conn.close()


if __name__ == '__main__':
    main()