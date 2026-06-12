"""
启动时数据迁移 — 只做 DB 操作，不调外部 API（避免 Zeabur 健康检查超时）。
每次启动执行，幂等设计（重复运行不产生副作用）。

修复场景：
  1. Zeabur 持久卷已有旧 DB，新代码部署后自动补入 SNDK、WDC 等缺失数据。
  2. Follow 数据因 /data 非持久卷在 redeploy 时丢失，从 FOLLOW_BACKUP env var 恢复。
"""
import json
import base64
import os
import logging

logger = logging.getLogger(__name__)

# 需要确保存在的证券数据（仅 DB 操作，不调外部 API）
TICKERS_TO_ENSURE = {
    "SNDK": {
        "name": "SanDisk",
        "name_cn": "闪迪",
        "sector": "NAND Flash",
        "company_type": "memory",
        "is_listed": True,
        "description": "SanDisk — 2025年从 Western Digital 分拆上市的 NAND Flash 存储公司",
        "chain_link_id": 3,
        "follow_weight": 30.0,
    },
    "WDC": {
        # WDC 已在旧 DB 中, 但 follow 可能因为之前调试被删
        "ensure_follow": True,
        "follow_weight": 30.0,
    },
}


def run_startup_migration(db):
    """启动迁移：确保新公司/关注存在（不调外部 API）"""
    from models import Company, Follow, CompanyChainLink, StockInfoCache

    results = {"companies_added": 0, "follows_added": 0}

    for ticker, cfg in TICKERS_TO_ENSURE.items():
        company = db.query(Company).filter(Company.ticker == ticker).first()

        # 1. 确保公司记录存在
        if not company and cfg.get("name"):
            company = Company(
                ticker=ticker,
                name=cfg["name"],
                name_cn=cfg.get("name_cn"),
                sector=cfg.get("sector"),
                company_type=cfg.get("company_type"),
                is_listed=cfg.get("is_listed", True),
                description=cfg.get("description"),
            )
            db.add(company)
            db.flush()
            results["companies_added"] += 1
            logger.info("StartupMigration: created company %s", ticker)

            # 关联产业链
            chain_link_id = cfg.get("chain_link_id")
            if chain_link_id:
                exists = db.query(CompanyChainLink).filter(
                    CompanyChainLink.company_id == company.id,
                    CompanyChainLink.chain_link_id == chain_link_id,
                ).first()
                if not exists:
                    db.add(CompanyChainLink(company_id=company.id, chain_link_id=chain_link_id))
        elif not company and not cfg.get("name"):
            logger.warning("StartupMigration: %s has no name config, can't create", ticker)
            continue

        if not company:
            continue

        # 2. 确保关注存在
        if cfg.get("ensure_follow") or cfg.get("name"):
            existing_follow = db.query(Follow).filter(Follow.company_id == company.id).first()
            if not existing_follow:
                db.add(Follow(company_id=company.id, weight=cfg.get("follow_weight", 0.0)))
                results["follows_added"] += 1
                logger.info("StartupMigration: added follow for %s", ticker)

        # 3. 为新增公司创建空 StockInfoCache（后续通过定时刷新填充）
        existing_cache = db.query(StockInfoCache).filter(StockInfoCache.ticker == ticker).first()
        if not existing_cache:
            db.add(StockInfoCache(ticker=ticker, data_json={}))

    db.commit()
    if any(v > 0 for v in results.values()):
        logger.info("StartupMigration completed: %s", results)

    # ── 从 FOLLOW_BACKUP env var 恢复用户关注(跨 redeploy 保护) ──
    # 当 /data 不是持久卷时, redeploy 会重置 DB, Follow 数据丢失。
    # 备份存储在 Zeabur env var (跨 redeploy 保留), 启动时自动恢复。
    follow_b64 = os.environ.get("FOLLOW_BACKUP")
    if follow_b64:
        try:
            follow_data = json.loads(base64.b64decode(follow_b64))
            restored = 0
            for item in follow_data:
                cid = item["company_id"]
                existing = db.query(Follow).filter(Follow.company_id == cid).first()
                if not existing:
                    # 确认公司仍存在
                    company_exists = db.query(Company).filter(Company.id == cid).first()
                    if company_exists:
                        db.add(Follow(
                            company_id=cid,
                            weight=item.get("weight", 0.0),
                        ))
                        restored += 1
            if restored:
                db.commit()
                results["follows_restored_from_env"] = restored
                logger.info("StartupMigration: restored %d follows from FOLLOW_BACKUP env var", restored)
        except Exception as e:
            logger.warning("StartupMigration: FOLLOW_BACKUP restore failed: %s", e)

    return results
