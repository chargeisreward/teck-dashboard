"""
启动时数据迁移 — 只做 DB 操作，不调外部 API（避免 Zeabur 健康检查超时）。
每次启动执行，幂等设计（重复运行不产生副作用）。

修复场景：Zeabur 持久卷已有旧 DB，新代码部署后自动补入 SNDK、WDC 等缺失数据。
"""
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

    return results
