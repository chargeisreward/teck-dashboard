"""一次性清理脚本：移除 key_indicators 中的僵尸 + 重复 + 宏观脏数据。

执行日期：2026-06-30 (industry_collector rebuild 后)
原因：industry_collector 在 2026-06-30 rebuild 中：
  - 删除了 distributor_data / osat_data / 旧 hyperscaler_capex / gpu_cloud 源
  - 但 key_indicators 表中残留 11 条僵尸 indicator
  - FRED api 23 条宏观经济 indicator 不在 AI 芯片 intelligence 范围内

清理范围：
1. 11 条僵尸 indicator（来源已删除）:
   - distributor_data: 20, 21, 22
   - osat_data: 23, 24, 25
   - 旧 hyperscaler_capex: 13, 14, 15 (已被 sec_edgar_capex 55/56/57 替代)
   - gpu_cloud: 17 (已被 vantage_gpu_price 58-62 替代)
   - typo: 29 (pegasron → pegatron)

2. 23 条 FRED 宏观经济 indicator (非 AI 芯片相关，绝大部分为空):
   32-54 全部

执行：先删除 indicator_observations (无 ON DELETE CASCADE)，再删除 key_indicators。

使用：
    python remove_zombie_indicators.py            # 直接执行（已在脚本中 hardcode DB path）
    docker cp remove_zombie_indicators.py <ctr>:/tmp/
    docker exec <ctr> python /tmp/remove_zombie_indicators.py

⚠️ 执行前必须先备份 DB：
    cp /data/teck_dashboard.db /data/teck_dashboard.db.bak-<timestamp>-pre-clean
"""
import sqlite3

DB_PATH = '/data/teck_dashboard.db'

# 1. 11 僵尸
ZOMBIE_IDS = [13, 14, 15, 17, 20, 21, 22, 23, 24, 25, 29]
# 2. 23 FRED
FRED_IDS = list(range(32, 55))
ALL_TO_DELETE = sorted(ZOMBIE_IDS + FRED_IDS)

print(f'Will delete {len(ALL_TO_DELETE)} indicators: {ALL_TO_DELETE}')

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# 显示待删的 indicator 元信息（用于报告）
print()
print('=== Indicators to be deleted (before) ===')
placeholders = ','.join('?'*len(ALL_TO_DELETE))
c.execute(f'SELECT id, name, source, category FROM key_indicators WHERE id IN ({placeholders}) ORDER BY id', ALL_TO_DELETE)
for r in c.fetchall():
    print(f'  id={r[0]:>3} {r[1]:<40} src={r[2]:<22} cat={r[3]}')

# 数 obs 数量（待删除）
c.execute(f'SELECT COUNT(*) FROM indicator_observations WHERE indicator_id IN ({placeholders})', ALL_TO_DELETE)
obs_count = c.fetchone()[0]
print()
print(f'Total observations to delete: {obs_count}')

# 显式事务
try:
    c.execute('BEGIN')
    c.execute(f'DELETE FROM indicator_observations WHERE indicator_id IN ({placeholders})', ALL_TO_DELETE)
    deleted_obs = c.rowcount
    c.execute(f'DELETE FROM key_indicators WHERE id IN ({placeholders})', ALL_TO_DELETE)
    deleted_ind = c.rowcount
    conn.commit()
    print()
    print(f'✓ Deleted {deleted_obs} observations')
    print(f'✓ Deleted {deleted_ind} indicators')
except Exception as e:
    conn.rollback()
    print(f'✗ ERROR: {e} — rolled back')
    raise

# 校验：剩余 indicators
print()
print('=== Remaining indicators count ===')
c.execute('SELECT COUNT(*) FROM key_indicators')
print(f'  key_indicators: {c.fetchone()[0]}')
c.execute('SELECT COUNT(*) FROM indicator_observations')
print(f'  indicator_observations: {c.fetchone()[0]}')

# 列出剩余 indicators 的 sources
print()
print('=== Remaining sources (post-clean) ===')
c.execute('SELECT source, COUNT(*) FROM key_indicators GROUP BY source ORDER BY source')
for r in c.fetchall():
    print(f'  {r[0]:<28} {r[1]:>3}')

# 数据状态确认
print()
print('=== Remaining indicators with obs count ===')
c.execute('''
SELECT i.id, i.name, i.source, COUNT(o.id) AS obs_count, MAX(o.date) AS latest
FROM key_indicators i
LEFT JOIN indicator_observations o ON o.indicator_id = i.id
GROUP BY i.id
ORDER BY i.id
''')
for r in c.fetchall():
    print(f'  id={r[0]:>3} {r[1]:<40} src={r[2]:<22} obs={r[3]:>3} latest={r[4]}')

conn.close()
print()
print('Done. DB saved.')