import asyncio
import logging
import os
from bisect import bisect_right
from collections import defaultdict
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from datetime import date, datetime, timedelta
from database import engine, Base, get_db
from models import (
    Company, Product, ProductMetric, MarketData, StorageProduct,
    IndustryChainLink, CompanyChainLink, Financial, SupplyDemand,
    KeyIndicator, IndicatorObservation, Forecast, JudgmentLog,
    ScoringDimension, CompanyScore, Portfolio, PortfolioHolding,
    PortfolioPerformance, PortfolioEvaluation, TimelineEvent, Follow,
)
from schemas import (
    CompanyOut, CompanyDetail, ProductOut, MarketDataOut,
    StorageProductOut, DashboardSummary,
    IndustryChainLinkOut, ChainLinkDetail, CompanyChainLinkOut,
    FinancialOut, SupplyDemandOut,
    KeyIndicatorOut, IndicatorDetail, IndicatorObservationOut,
    ForecastOut, JudgmentLogOut, JudgmentLogCreate,
    ScoringDimensionOut, CompanyScoreOut, CompanyScoreSummary,
    PortfolioOut, PortfolioDetail, PortfolioHoldingOut,
    PortfolioPerformanceOut, PortfolioEvaluationOut,
    HoldingTrackingData, PortfolioTrackingData, WeightUpdateRequest,
    ValuationParams, PeerGroupDef, ValuationCompanyData,
    PeerComparisonResultOut, ValuationResultOut, PriceDataPoint,
    ChainSupplyDemandScoreOut, CompanyAdjustmentOut,
    FuturePEValuationParams, FuturePEValuationResultOut,
    FuturePEComparisonResultOut, TimelineEventOut,
    FollowOut, IndustryChainCard, DashboardOverview, FollowActionResponse,
)
import ai_analysis
from price_performance import compute_relative_performance

# 供应链位置中文名称映射（与 IndustryData.jsx CATEGORY_CN 保持一致）
CATEGORY_CN_MAP = {
    "raw_materials": "原材料",
    "equipment": "设备",
    "eda": "EDA/设计工具",
    "chip_design": "芯片设计",
    "foundry": "晶圆制造",
    "memory": "存储芯片",
    "packaging": "先进封装/OSAT",
    "distribution": "分销",
    "end_market": "终端市场",
    "gpu_cloud": "GPU云",
    # 旧版分类
    "price_supply": "价格与供需",
    "industry": "行业景气度",
    "lead_time": "产业链交期",
    "financial": "公司财务追踪",
    "technology": "技术前沿",
    "sentiment": "市场情绪",
}
from valuation import GordonGrowthModel, CompanyValuationInput
from valuation_v2 import (
    SupplyDemandAnalyzer, FuturePEModel, CompanyInput,
)
from price_data import fetch_price_history, get_current_price, get_stock_info, get_top_gainers_losers, get_price_history_cached, get_stock_info_cached
from models import StockInfoCache
from price_performance import update_timeline_returns, refresh_pending_post_events, compute_relative_performance
from industry_collector import collect_all as run_industry_collectors
from scheduler import init_scheduler
from refresh_company_data import refresh_all_company_data, verify_data_integrity
from portfolio_tracking import compute_holding_returns, derive_eps_metrics, compute_portfolio_aggregates

Base.metadata.create_all(bind=engine)

# ── 自动初始化数据库（仅在首次启动时） ──
try:
    from seed_data import seed as _seed_db
    _seed_db()
    # 也运行产业链数据采集（市场数据/来源标注）
    from data_pipeline.market_size_collector import collect_chain_data
    collect_chain_data()
except Exception as _e:
    print(f"[init] DB seed skipped: {_e}")

app = FastAPI(title="AI芯片与半导体存储产业链分析仪表盘")
logger = logging.getLogger(__name__)


@app.on_event("startup")
async def on_startup():
    """应用启动时初始化定时调度器 + 数据迁移"""
    try:
        init_scheduler()
        logger.info("Scheduler initialized on startup")
    except Exception as e:
        logger.warning(f"Scheduler init skipped (might be dev mode): {e}")

    # 启动数据迁移：确保新证券/关注/价格数据在持久化 DB 中也存在
    try:
        from database import SessionLocal
        from startup_migration import run_startup_migration
        db = SessionLocal()
        try:
            result = run_startup_migration(db)
            if any(v > 0 for v in result.values()):
                logger.info(f"Startup migration applied: {result}")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Startup migration skipped: {e}")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Zeabur 部署允许多域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================================
# 1. 概览
# =========================================================================

@app.get("/api/dashboard/summary", response_model=DashboardSummary)
def get_dashboard_summary(db: Session = Depends(get_db)):
    total_companies = db.query(Company).count()
    total_products = db.query(Product).count()
    total_storage = db.query(StorageProduct).count()

    subq = (db.query(MarketData.company_id, func.max(MarketData.date).label("max_date"))
            .group_by(MarketData.company_id).subquery())
    latest_caps = (db.query(Company.name, Company.ticker, MarketData.market_cap)
                   .join(subq, (MarketData.company_id == subq.c.company_id) & (MarketData.date == subq.c.max_date))
                   .join(Company, Company.id == MarketData.company_id).all())

    categories = (db.query(Product.category, func.count(Product.id).label("count"))
                  .group_by(Product.category).all())

    return DashboardSummary(
        total_companies=total_companies, total_products=total_products,
        total_storage_products=total_storage,
        latest_market_caps=[{"name": n, "ticker": t, "market_cap": c} for n, t, c in latest_caps],
        product_categories=[{"category": cat, "count": cnt} for cat, cnt in categories],
    )


# ── 新版市场概览聚合端点 ───────────────────────────────────

TYPE_LABELS_OVERVIEW = {
    "chip_design": "AI芯片设计", "manufacturing": "晶圆制造",
    "memory": "存储/HBM", "packaging": "先进封装",
    "equipment": "半导体设备", "eda": "EDA/IP",
    "llm": "大模型/AI", "cloud": "云厂商",
    "application": "应用厂商", "networking": "网络互联",
}


@app.get("/api/dashboard/overview", response_model=DashboardOverview)
def get_dashboard_overview(db: Session = Depends(get_db)):
    """市场概览聚合数据：产业链卡片 + 核心公司（单次查询）"""
    total_companies = db.query(Company).count()
    total_products = db.query(Product).count()
    total_storage = db.query(StorageProduct).count()

    # StockInfoCache 批量加载
    cache_records = db.query(StockInfoCache).all()
    cache_map = {}
    for r in cache_records:
        if r.ticker and isinstance(r.data_json, dict):
            cache_map[r.ticker.upper()] = r.data_json

    # 每公司最新财务记录
    latest_year_subq = (
        db.query(Financial.company_id, func.max(Financial.fiscal_year).label("max_year"))
        .group_by(Financial.company_id).subquery()
    )
    latest_fins = (
        db.query(Financial)
        .join(latest_year_subq,
              (Financial.company_id == latest_year_subq.c.company_id) &
              (Financial.fiscal_year == latest_year_subq.c.max_year))
        .all()
    )
    fin_map = {f.company_id: f for f in latest_fins}

    # 按 company_type 分组聚合
    companies = db.query(Company).all()
    type_agg = {}
    for c in companies:
        ct = c.company_type or "other"
        if ct not in type_agg:
            type_agg[ct] = {"count": 0, "cp_sum": 0.0, "cp_n": 0,
                           "rev_sum": 0.0, "ni_sum": 0.0, "mcap_sum": 0.0}
        agg = type_agg[ct]
        agg["count"] += 1
        if c.ticker and c.ticker.upper() in cache_map:
            d = cache_map[c.ticker.upper()]
            try:
                cp = d.get("change_pct")
                if cp is not None:
                    agg["cp_sum"] += float(cp)
                    agg["cp_n"] += 1
            except (TypeError, ValueError):
                pass
            try:
                mcap = d.get("market_cap_b")
                if mcap is not None:
                    agg["mcap_sum"] += float(mcap)
            except (TypeError, ValueError):
                pass
        fin = fin_map.get(c.id)
        if fin:
            if fin.revenue is not None:
                agg["rev_sum"] += fin.revenue
            if fin.net_income is not None:
                agg["ni_sum"] += fin.net_income

    chains = []
    for ct, agg in type_agg.items():
        if ct == "other":
            continue
        chains.append(IndustryChainCard(
            company_type=ct,
            name_cn=TYPE_LABELS_OVERVIEW.get(ct, ct),
            company_count=agg["count"],
            avg_change_pct=round(agg["cp_sum"] / agg["cp_n"], 2) if agg["cp_n"] > 0 else None,
            total_revenue_ttm=round(agg["rev_sum"], 1) if agg["rev_sum"] > 0 else None,
            total_net_income_ttm=round(agg["ni_sum"], 1) if agg["ni_sum"] > 0 else None,
            total_market_cap=round(agg["mcap_sum"], 1) if agg["mcap_sum"] > 0 else None,
        ))

    # 核心公司（已关注）
    follows = db.query(Follow).order_by(Follow.created_at).all()
    f_company_ids = [f.company_id for f in follows]
    f_companies = {c.id: c for c in db.query(Company).filter(Company.id.in_(f_company_ids)).all()} if f_company_ids else {}
    core = []
    for f in follows:
        co = f_companies.get(f.company_id)
        if not co:
            continue
        info = {"current_price": None, "change_pct": None, "pe_ttm": None,
                "market_cap_b": None, "revenue_b": None}
        if co.ticker and co.ticker.upper() in cache_map:
            d = cache_map[co.ticker.upper()]
            info["current_price"] = d.get("current_price") or d.get("current_price_usd")
            info["change_pct"] = d.get("change_pct")
            info["pe_ttm"] = d.get("pe_ttm")
            mcap = d.get("market_cap_b")
            info["market_cap_b"] = round(float(mcap), 1) if mcap else None
            rev = d.get("revenue_b")
            info["revenue_b"] = round(float(rev), 1) if rev else None
        core.append({
            "id": co.id, "ticker": co.ticker, "name": co.name,
            "name_cn": co.name_cn, "company_type": co.company_type,
            **info,
        })

    # 计算各区间涨跌幅（从 MarketData）
    if core:
        core_ids = [c["id"] for c in core]
        all_md = (db.query(MarketData)
                  .filter(MarketData.company_id.in_(core_ids), MarketData.stock_price.isnot(None))
                  .order_by(MarketData.company_id, MarketData.date)
                  .all())
        md_by_cid = defaultdict(list)
        for md in all_md:
            md_by_cid[md.company_id].append(md)
        for company in core:
            cid = company["id"]
            records = md_by_cid.get(cid, [])
            if len(records) >= 2:
                dates = [r.date for r in records]
                prices = [r.stock_price for r in records]
                latest_px = prices[-1]
                today = dates[-1]
                periods = {"chg_1w": 7, "chg_1m": 30, "chg_3m": 90,
                           "chg_6m": 180, "chg_1y": 365, "chg_3y": 1095}
                for key, days in periods.items():
                    target = today - timedelta(days=days)
                    idx = bisect_right(dates, target) - 1
                    if idx >= 0:
                        px = prices[idx]
                        company[key] = round((latest_px - px) / px * 100, 2) if px and latest_px else None
                    else:
                        company[key] = None

    return DashboardOverview(
        total_companies=total_companies, total_products=total_products,
        total_storage_products=total_storage,
        industry_chains=chains, core_companies=core,
    )


# =========================================================================
# 2. 产业链环节
# =========================================================================

@app.get("/api/chain-links", response_model=list[IndustryChainLinkOut])
def list_chain_links(db: Session = Depends(get_db)):
    return db.query(IndustryChainLink).order_by(IndustryChainLink.sort_order).all()


@app.get("/api/chain-links/{link_id}", response_model=ChainLinkDetail)
def get_chain_link(link_id: int, db: Session = Depends(get_db)):
    cl = (db.query(IndustryChainLink)
          .options(joinedload(IndustryChainLink.companies)
                   .joinedload(CompanyChainLink.company))
          .filter(IndustryChainLink.id == link_id).first())
    if not cl:
        raise HTTPException(404, "产业链环节不存在")
    return cl


@app.get("/api/chain-links/{link_id}/companies", response_model=list[CompanyChainLinkOut])
def get_chain_companies(link_id: int, db: Session = Depends(get_db)):
    return (db.query(CompanyChainLink)
            .options(joinedload(CompanyChainLink.company))
            .filter(CompanyChainLink.chain_link_id == link_id)
            .order_by(CompanyChainLink.is_leader.desc(), CompanyChainLink.market_share.desc())
            .all())


# =========================================================================
# 3. 公司
# =========================================================================

@app.get("/api/companies", response_model=list[CompanyOut])
def list_companies(db: Session = Depends(get_db)):
    companies = db.query(Company).all()
    company_ids = [c.id for c in companies]

    # 读取 Financial 表中 2025 年营收(优先) + StockInfoCache 中的 revenue_b
    fin_2025 = db.query(Financial).filter(
        Financial.company_id.in_(company_ids),
        Financial.fiscal_year == 2025,
    ).all()
    fin_map = {f.company_id: f.revenue for f in fin_2025 if f.revenue is not None}

    # StockInfoCache 作为补充(已刷新的实时数据)
    tickers = [c.ticker for c in companies if c.ticker]
    cache_records = db.query(StockInfoCache).filter(
        StockInfoCache.ticker.in_(tickers)
    ).all()
    cache_map = {}
    for r in cache_records:
        if isinstance(r.data_json, dict) and r.data_json.get("revenue_b") is not None:
            cache_map[r.ticker.upper()] = r.data_json["revenue_b"]

    result = []
    for c in companies:
        # 2025 营收: 优先 StockInfoCache(实时刷新), 其次 Financials, 最后 None
        rev_2025 = None
        if c.ticker and c.ticker.upper() in cache_map:
            # cache 中 revenue_b 是 亿(100M), /10 转为 B(10亿)
            rev_2025 = round(float(cache_map[c.ticker.upper()]) / 10, 1)
        if rev_2025 is None and c.id in fin_map:
            rev_2025 = round(float(fin_map[c.id]) / 10, 1) if fin_map[c.id] else None

        company_out = CompanyOut(
            id=c.id, name=c.name, name_cn=c.name_cn,
            ticker=c.ticker, sector=c.sector,
            description=c.description, logo_url=c.logo_url,
            is_listed=c.is_listed, company_type=c.company_type,
            revenue_2024=c.revenue_2024,
            employee_count=c.employee_count,
            revenue_2025=rev_2025,
        )
        result.append(company_out)

    return result


@app.get("/api/companies/{company_id}", response_model=CompanyDetail)
def get_company(company_id: int, db: Session = Depends(get_db)):
    c = db.query(Company).options(
        joinedload(Company.products).joinedload(Product.metrics),
        joinedload(Company.market_data),
    ).filter(Company.id == company_id).first()
    if not c:
        raise HTTPException(404, "公司不存在")
    return c


@app.get("/api/companies/{company_id}/financials", response_model=list[FinancialOut])
def get_company_financials(company_id: int, db: Session = Depends(get_db)):
    return (db.query(Financial).filter(Financial.company_id == company_id)
            .order_by(Financial.fiscal_year.desc()).all())


@app.get("/api/companies/{company_id}/forecasts", response_model=list[ForecastOut])
def get_company_forecasts(company_id: int, db: Session = Depends(get_db)):
    return (db.query(Forecast).filter(Forecast.company_id == company_id)
            .order_by(Forecast.target_year).all())


# =========================================================================
# 4. 供需分析
# =========================================================================

@app.get("/api/supply-demand")
def get_supply_demand(chain_link_id: int = None, period: str = None, db: Session = Depends(get_db)):
    q = db.query(SupplyDemand)
    if chain_link_id:
        q = q.filter(SupplyDemand.chain_link_id == chain_link_id)
    if period:
        q = q.filter(SupplyDemand.period == period)
    return q.all()


# =========================================================================
# 5. 关键指标
# =========================================================================

@app.get("/api/indicators", response_model=list[KeyIndicatorOut])
def list_indicators(category: str = None, db: Session = Depends(get_db)):
    q = db.query(KeyIndicator)
    if category:
        q = q.filter(KeyIndicator.category == category)
    return q.all()


@app.get("/api/indicator-categories")
def get_indicator_categories(db: Session = Depends(get_db)):
    rows = db.query(KeyIndicator.category, func.count(KeyIndicator.id).label("count"))\
             .group_by(KeyIndicator.category).all()
    # name mapping for Chinese display
    cat_names = {
        "price_supply": "价格与供需",
        "industry": "行业景气度",
        "lead_time": "产业链交期",
        "financial": "公司财务追踪",
        "technology": "技术前沿",
        "sentiment": "市场情绪",
    }
    return [{"category": row[0], "name_cn": cat_names.get(row[0], row[0]), "count": row[1]} for row in rows]


@app.get("/api/indicators/{indicator_id}", response_model=IndicatorDetail)
def get_indicator(indicator_id: int, db: Session = Depends(get_db)):
    ind = (db.query(KeyIndicator)
           .options(joinedload(KeyIndicator.observations))
           .filter(KeyIndicator.id == indicator_id).first())
    if not ind:
        raise HTTPException(404, "指标不存在")
    return ind


@app.get("/api/indicators/{indicator_id}/observations", response_model=list[IndicatorObservationOut])
def get_indicator_observations(indicator_id: int, limit: int = 90, db: Session = Depends(get_db)):
    return (db.query(IndicatorObservation)
            .filter(IndicatorObservation.indicator_id == indicator_id)
            .order_by(IndicatorObservation.date.desc())
            .limit(limit).all())


# =========================================================================
# 5b. 产业数据 (Industry Data API)
# =========================================================================

from pydantic import BaseModel
from typing import Optional
import asyncio

class IndustryIndicatorOut(BaseModel):
    id: int
    name: str
    name_cn: Optional[str] = None
    unit: Optional[str] = None
    source: Optional[str] = None
    source_url: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    update_frequency: Optional[str] = None
    # Latest observation
    latest_value: Optional[float] = None
    latest_date: Optional[str] = None
    change_pct: Optional[float] = None
    previous_value: Optional[float] = None
    data_quality: Optional[str] = None
    last_updated: Optional[str] = None

class DataSourceStatus(BaseModel):
    source: str
    status: str  # ok / stale / error / never
    last_updated: Optional[str] = None
    indicators_count: int = 0

@app.get("/api/industry/indicators")
def list_industry_indicators(
    category: str = None,
    source: str = None,
    db: Session = Depends(get_db),
):
    """返回全部产业指标 + 最新观测值 + 边际变化"""
    q = db.query(KeyIndicator)
    if category:
        q = q.filter(KeyIndicator.category == category)
    if source:
        q = q.filter(KeyIndicator.source == source)

    indicators = q.order_by(KeyIndicator.category, KeyIndicator.id).all()
    result = []

    for ind in indicators:
        latest = (db.query(IndicatorObservation)
                  .filter(IndicatorObservation.indicator_id == ind.id)
                  .order_by(IndicatorObservation.date.desc())
                  .first())

        item = IndustryIndicatorOut(
            id=ind.id,
            name=ind.name,
            name_cn=ind.name_cn,
            unit=ind.unit,
            source=ind.source,
            source_url=ind.source_url,
            category=ind.category,
            description=ind.description,
            update_frequency=ind.update_frequency,
        )

        if latest:
            item.latest_value = latest.value
            item.latest_date = str(latest.date)
            item.change_pct = latest.change_pct
            item.previous_value = latest.previous_value
            item.data_quality = latest.data_quality
            item.last_updated = str(latest.date)

        result.append(item)

    return result


@app.get("/api/industry/indicators/{indicator_id}")
def get_industry_indicator(indicator_id: int, limit: int = 20, db: Session = Depends(get_db)):
    """单指标详情 + 历史时序"""
    ind = db.query(KeyIndicator).filter(KeyIndicator.id == indicator_id).first()
    if not ind:
        raise HTTPException(404, "指标不存在")

    observations = (db.query(IndicatorObservation)
                    .filter(IndicatorObservation.indicator_id == indicator_id)
                    .order_by(IndicatorObservation.date.desc())
                    .limit(limit)
                    .all())

    return {
        "id": ind.id,
        "name": ind.name,
        "name_cn": ind.name_cn,
        "unit": ind.unit,
        "source": ind.source,
        "category": ind.category,
        "description": ind.description,
        "observations": [
            {
                "date": str(o.date),
                "value": o.value,
                "change_pct": o.change_pct,
                "previous_value": o.previous_value,
                "note": o.note,
                "data_quality": o.data_quality,
            }
            for o in observations
        ],
    }


@app.post("/api/industry/collect")
def trigger_industry_collect(
    source: str = None,
    db: Session = Depends(get_db),
):
    """触发产业数据采集，采集后自动创建 TimelineEvent"""
    from models import IndicatorObservation as ObsModel

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(run_industry_collectors(source=source, db=db))
        loop.close()

        # 为每个成功采集的指标创建 TimelineEvent
        timeline_created = 0
        for r in results.get("success", []):
            try:
                indicator_name = r.get("indicator", "")
                ind = db.query(KeyIndicator).filter(KeyIndicator.name == indicator_name).first()
                if not ind:
                    continue

                # 获取刚写入的最新 observation
                obs = (
                    db.query(ObsModel)
                    .filter(ObsModel.indicator_id == ind.id)
                    .order_by(ObsModel.date.desc())
                    .first()
                )
                if not obs:
                    continue

                # 检查是否已存在对应的 TimelineEvent
                existing_tl = db.query(TimelineEvent).filter(
                    TimelineEvent.indicator_observation_id == obs.id
                ).first()
                if existing_tl:
                    continue

                # 确定相关 ticker (基于 category 或 indicator name)
                tickers = _get_indicator_tickers(ind)

                value_display = f"{obs.value}{' ' + ind.unit if ind.unit else ''}"
                if obs.change_pct is not None:
                    value_display += f" ({obs.change_pct:+.1f}%)"

                tl = TimelineEvent(
                    event_type="collection",
                    event_time=datetime.now(),
                    title=ind.name_cn or ind.name,
                    description=ind.description or "",
                    related_tickers=",".join(tickers) if tickers else None,
                    related_indicators=ind.name_cn or ind.name,
                    indicator_observation_id=obs.id,
                    source_name=ind.source,
                    indicator_name_cn=ind.name_cn,
                    value_display=value_display,
                )
                db.add(tl)
                db.commit()
                db.refresh(tl)
                timeline_created += 1

                # 计算前10日涨跌幅
                if tl.related_tickers:
                    try:
                        update_timeline_returns(db, tl)
                    except Exception as e:
                        logger.warning(f"Failed to compute timeline returns for {indicator_name}: {e}")

            except Exception as e:
                logger.warning(f"Failed to create timeline event for collection: {e}")

        return {
            "success": True,
            "collected": len(results.get("success", [])),
            "errors": len(results.get("errors", [])),
            "timeline_created": timeline_created,
            "details": results,
        }
    except Exception as e:
        raise HTTPException(500, f"采集失败: {str(e)}")


@app.post("/api/industry/refresh-company-data")
def refresh_company_data(db: Session = Depends(get_db)):
    """从 Tencent API + yfinance 拉取所有链上公司的真实数据，更新本地数据库"""
    try:
        results = refresh_all_company_data(db)
        return {
            "success": True,
            "updated": results["updated"],
            "skipped": results["skipped"],
            "errors": results["errors"],
            "details": results["details"],
        }
    except Exception as e:
        raise HTTPException(500, f"数据刷新失败: {str(e)}")


@app.get("/api/industry/verify-data")
def verify_company_data(db: Session = Depends(get_db)):
    """校验公司数据真实性"""
    return verify_data_integrity(db)


# 指标 → 相关 ticker 映射 (共享模块)
from indicator_map import INDICATOR_TICKER_MAP


def _get_indicator_ticker_from_name(name: str) -> str:
    """从指标名称推断相关 ticker"""
    name_lower = name.lower()
    if "nvidia" in name_lower or "dc_revenue" in name_lower:
        return "NVDA"
    if "tsmc" in name_lower or "cowos" in name_lower or "foundry" in name_lower:
        return "TSM"
    if "dram" in name_lower or "nand" in name_lower or "memory" in name_lower or "hbm" in name_lower:
        return "MU"
    if "asml" in name_lower:
        return "ASML"
    if "semi_equipment" in name_lower:
        return "ASML"
    if "semiconductor_sales" in name_lower or "global" in name_lower:
        return "TSM"
    return ""


def _get_indicator_tickers(indicator) -> list[str]:
    """获取指标相关的 ticker 列表"""
    if indicator.name in INDICATOR_TICKER_MAP:
        return INDICATOR_TICKER_MAP[indicator.name]
    ticker = _get_indicator_ticker_from_name(indicator.name)
    return [ticker] if ticker else []


def _get_pe_from_cache(cache_map: dict, ticker: str | None, fin_fallback) -> float | None:
    """从 stock_info_cache 获取 PE_TTM，fallback 到 financials 表"""
    if ticker and ticker.upper() in cache_map:
        data = cache_map[ticker.upper()]
        pe = data.get("pe_ttm") if isinstance(data, dict) else None
        if pe is not None:
            return round(float(pe), 1)
    if fin_fallback and fin_fallback.pe_ttm is not None:
        return round(float(fin_fallback.pe_ttm), 1)
    return None


def _get_revenue_from_cache(cache_map: dict, ticker: str | None, fin_fallback) -> float | None:
    """获取 2025 年营收（B = billions USD），优先 stock_info_cache，fallback 到 financials
    数据库存储单位为 亿（100M），需除以 10 转换为 B（10亿）。
    """
    if ticker and ticker.upper() in cache_map:
        data = cache_map[ticker.upper()]
        rev = data.get("revenue_b") if isinstance(data, dict) else None
        if rev is not None:
            return round(float(rev) / 10, 1)
    if fin_fallback and fin_fallback.revenue is not None:
        return round(float(fin_fallback.revenue) / 10, 1)
    return None


def _get_data_source(cache_map: dict, ticker: str | None, field: str = "pe_ttm") -> str:
    """返回数据来源标记: 'tencent_api' | 'yfinance' | 'seed' | None"""
    if ticker and ticker.upper() in cache_map:
        data = cache_map[ticker.upper()]
        if isinstance(data, dict) and data.get(field) is not None:
            src = data.get("source", "tencent_api")
            return src if src else "tencent_api"
        return None
    return "seed"


def _get_cache_field(cache_map: dict, ticker: str | None, field: str) -> float | None:
    """从 stock_info_cache 获取指定字段，自动转换单位"""
    if ticker and ticker.upper() in cache_map:
        data = cache_map[ticker.upper()]
        val = data.get(field) if isinstance(data, dict) else None
        if val is not None:
            # market_cap_b 和 revenue_b 在 cache 中存储为 亿(100M)，需转 B(10亿)
            if field in ("market_cap_b", "revenue_b"):
                return round(float(val) / 10, 2)
            return round(float(val), 2) if isinstance(val, (int, float)) else val
    return None


@app.get("/api/industry/data-sources")
def get_data_source_status(db: Session = Depends(get_db)):
    """数据源状态 (最近更新时间, 是否可用)"""
    sources = db.query(
        KeyIndicator.source,
        func.max(IndicatorObservation.date).label("last_date"),
        func.count(KeyIndicator.id).label("ind_count"),
    ).join(
        IndicatorObservation,
        KeyIndicator.id == IndicatorObservation.indicator_id,
        isouter=True,
    ).group_by(KeyIndicator.source).all()

    today = date.today()
    result = []
    for source_name, last_date, ind_count in sources:
        if last_date is None:
            status = "never"
        else:
            days_diff = (today - last_date).days
            if days_diff <= 1:
                status = "ok"
            elif days_diff <= 3:
                status = "stale"
            else:
                status = "outdated"

        result.append(DataSourceStatus(
            source=source_name,
            status=status,
            last_updated=str(last_date) if last_date else None,
            indicators_count=ind_count,
        ))

    return result


# =========================================================================
# 6. 产品
# =========================================================================

@app.get("/api/products", response_model=list[ProductOut])
def list_products(category: str = None, db: Session = Depends(get_db)):
    q = db.query(Product).options(joinedload(Product.metrics))
    if category:
        q = q.filter(Product.category == category)
    return q.all()


@app.get("/api/products/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    return db.query(Product).options(joinedload(Product.metrics)).filter(Product.id == product_id).first()


# =========================================================================
# 7. 市场数据
# =========================================================================

@app.get("/api/market-data", response_model=list[MarketDataOut])
def list_market_data(company_id: int = None, days: int = 30, db: Session = Depends(get_db)):
    from datetime import timedelta
    cutoff = date.today() - timedelta(days=days)
    q = db.query(MarketData).filter(MarketData.date >= cutoff)
    if company_id:
        q = q.filter(MarketData.company_id == company_id)
    q = q.order_by(MarketData.date.desc())
    return q.all()


# =========================================================================
# 8. 存储产品
# =========================================================================

@app.get("/api/storage", response_model=list[StorageProductOut])
def list_storage(storage_type: str = None, db: Session = Depends(get_db)):
    q = db.query(StorageProduct)
    if storage_type:
        q = q.filter(StorageProduct.storage_type == storage_type)
    return q.all()


# =========================================================================
# 9. 分类
# =========================================================================

@app.get("/api/categories")
def get_categories(db: Session = Depends(get_db)):
    rows = db.query(Product.category).distinct().all()
    return [r[0] for r in rows]


# =========================================================================
# 10. 判断日志
# =========================================================================

@app.get("/api/judgment-logs", response_model=list[JudgmentLogOut])
def list_judgment_logs(db: Session = Depends(get_db)):
    return db.query(JudgmentLog).order_by(JudgmentLog.date.desc()).all()


@app.post("/api/judgment-logs", response_model=JudgmentLogOut)
def create_judgment_log(jl: JudgmentLogCreate, db: Session = Depends(get_db)):
    entry = JudgmentLog(**jl.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)

    # 同步创建 TimelineEvent
    try:
        event_dt = (
            datetime.combine(jl.date, datetime.min.time())
            if isinstance(jl.date, date)
            else jl.date
        )
        tl = TimelineEvent(
            event_type="judgment",
            event_time=event_dt,
            title=jl.title,
            description=jl.description,
            impact_level=jl.impact_level,
            related_tickers=jl.related_companies,
            related_indicators=jl.related_indicators,
            judgment_log_id=entry.id,
        )
        db.add(tl)
        db.commit()
        db.refresh(tl)

        # 计算前10日涨跌幅
        if tl.related_tickers:
            try:
                update_timeline_returns(db, tl)
            except Exception as e:
                logger.warning(f"Failed to compute timeline returns: {e}")
    except Exception as e:
        logger.warning(f"Failed to create timeline event: {e}")

    return entry


# =========================================================================
# 10b. 时间线 (Timeline)
# =========================================================================

@app.get("/api/timeline", response_model=list[TimelineEventOut])
def get_timeline(limit: int = 50, offset: int = 0, event_type: str = None, db: Session = Depends(get_db)):
    """返回合并时间线，按 event_time 降序排列"""
    q = db.query(TimelineEvent)
    if event_type:
        q = q.filter(TimelineEvent.event_type == event_type)
    return q.order_by(TimelineEvent.event_time.desc()).offset(offset).limit(limit).all()


@app.post("/api/timeline/{event_id}/refresh-returns")
def refresh_timeline_returns(event_id: int, db: Session = Depends(get_db)):
    """手动刷新某条目的涨跌幅数据"""
    tl = db.query(TimelineEvent).filter(TimelineEvent.id == event_id).first()
    if not tl:
        raise HTTPException(404, "时间线事件不存在")
    update_timeline_returns(db, tl)
    return {"success": True, "id": event_id}


@app.post("/api/timeline/refresh-pending")
def refresh_all_pending_returns(db: Session = Depends(get_db)):
    """刷新所有待更新 post_event 的条目 (>=10天)"""
    updated = refresh_pending_post_events(db)
    return {"success": True, "updated": updated}


# =========================================================================
# 10c. 产业情报统一接口 (Industry Intelligence)
# =========================================================================


# ── 边际变化计算辅助函数 ──

def _get_comparison_window_days(frequency: str | None) -> int:
    """根据更新频率返回比较窗口天数"""
    if not frequency:
        return 90
    freq = frequency.lower().strip()
    if freq in ("daily", "weekly", "日", "周"):
        return 30
    elif freq in ("monthly", "月"):
        return 90
    elif freq in ("quarterly", "季"):
        return 90
    else:  # annual / 年 / 不定期
        return 365


def _determine_comparison_window(frequency: str | None) -> str:
    """确定比较窗口标签"""
    if not frequency:
        return "90d"
    freq = frequency.lower().strip()
    if freq in ("daily", "weekly", "日", "周"):
        return "30d"
    elif freq in ("monthly", "quarterly", "月", "季"):
        return "90d"
    else:
        return "last_change"


def _compute_marginal_change(db, indicator: KeyIndicator, latest: IndicatorObservation):
    """
    计算指标的边际变化。
    高频(daily/weekly) → 对比30天前观测值
    中频(monthly/quarterly) → 对比90天前观测值
    低频(annual) → 对比最近一次观测值
    """
    from models import IndicatorObservation as ObsModel

    window = _determine_comparison_window(indicator.update_frequency)

    if window == "last_change":
        # 对比最近一次观测值
        prev = (
            db.query(ObsModel)
            .filter(
                ObsModel.indicator_id == indicator.id,
                ObsModel.date < latest.date,
            )
            .order_by(ObsModel.date.desc())
            .first()
        )
        if prev and prev.value and latest.value:
            old_val = prev.value
            if old_val != 0:
                latest.marginal_change_pct = round((latest.value - old_val) / old_val * 100, 2)
                latest.comparison_window = "last_change"
    else:
        days = int(window.replace("d", ""))
        cutoff = latest.date - timedelta(days=days)
        ref_obs = (
            db.query(ObsModel)
            .filter(
                ObsModel.indicator_id == indicator.id,
                ObsModel.date >= cutoff,
                ObsModel.date < latest.date,
            )
            .order_by(ObsModel.date.asc())
            .first()
        )
        if ref_obs and ref_obs.value and latest.value:
            old_val = ref_obs.value
            if old_val != 0:
                latest.marginal_change_pct = round((latest.value - old_val) / old_val * 100, 2)
                latest.comparison_window = window

    try:
        db.commit()
    except Exception:
        db.rollback()


# ── 产业影响分析批量生成 ──

def batch_analyze_industry_impact(db: Session, limit: int = 20):
    """为所有缺少 industry_impact 或 analysis 的最新观测值调用 MiniMax API 生成分析"""
    from models import IndicatorObservation as ObsModel

    obs_list = (
        db.query(ObsModel)
        .filter(
            ObsModel.value.isnot(None),
            ObsModel.marginal_change_pct.isnot(None),
        )
        .filter(
            (ObsModel.industry_impact.is_(None)) | (ObsModel.analysis.is_(None))
        )
        .order_by(ObsModel.date.desc())
        .limit(limit)
        .all()
    )

    updated = 0
    for obs in obs_list:
        ind = db.query(KeyIndicator).filter(KeyIndicator.id == obs.indicator_id).first()
        if not ind:
            continue

        # 1) 三重影响分析
        if not obs.industry_impact:
            try:
                result = ai_analysis.generate_industry_impact_analysis(
                    name_cn=ind.name_cn or ind.name,
                    category_cn=CATEGORY_CN_MAP.get(ind.category, ind.category or ""),
                    latest_value=obs.value,
                    previous_value=obs.previous_value,
                    change_pct=obs.change_pct,
                    marginal_change_pct=obs.marginal_change_pct,
                    comparison_window=obs.comparison_window,
                    unit=ind.unit or "",
                    related_tickers=ind.related_tickers or "",
                )
                if result:
                    obs.industry_impact = result.get("industry_impact", "")
                    obs.chain_impact = result.get("chain_impact", "")
                    obs.company_impact = result.get("company_impact", "")
                    db.commit()
                    updated += 1
            except Exception as e:
                logger.warning(f"Industry impact analysis failed for {ind.name}: {e}")
                db.rollback()

        # 2) 一句话边际变化分析
        if not obs.analysis and obs.change_pct is not None:
            try:
                one_liner = ai_analysis.generate_indicator_analysis(
                    name_cn=ind.name_cn or ind.name,
                    category_cn=CATEGORY_CN_MAP.get(ind.category, ind.category or ""),
                    latest_value=obs.value,
                    previous_value=obs.previous_value,
                    change_pct=obs.change_pct,
                    unit=ind.unit or "",
                    source=ind.source or "",
                )
                if one_liner:
                    obs.analysis = one_liner
                    db.commit()
                    updated += 1
            except Exception as e:
                logger.warning(f"Indicator one-sentence analysis failed for {ind.name}: {e}")
                db.rollback()

    return updated


class IndustryIntelligenceIndicator(BaseModel):
    """产业情报中的指标条目"""
    id: int
    name: str
    name_cn: Optional[str] = None
    category: Optional[str] = None
    category_cn: Optional[str] = None
    tier: Optional[int] = 3
    unit: Optional[str] = None
    source: Optional[str] = None
    source_url: Optional[str] = None
    update_frequency: Optional[str] = None
    description: Optional[str] = None
    related_tickers: Optional[str] = None

    # 最新观测值
    latest_value: Optional[float] = None
    latest_date: Optional[str] = None
    previous_value: Optional[float] = None
    previous_date: Optional[str] = None
    change_pct: Optional[float] = None
    data_quality: Optional[str] = None
    analysis: Optional[str] = None
    last_updated: Optional[str] = None

    # 边际变化
    marginal_change_pct: Optional[float] = None
    comparison_window: Optional[str] = None
    marginal_observations: Optional[list] = None   # 窗口期内的观测值列表

    # 行业/产业链/公司影响分析
    industry_impact: Optional[str] = None
    chain_impact: Optional[str] = None
    company_impact: Optional[str] = None

    # 前后10日涨跌幅
    pre_event_returns: Optional[dict] = None
    post_event_returns: Optional[dict] = None
    post_event_updated: bool = False


class IndustryIntelligenceTimeline(BaseModel):
    """时间线条目"""
    id: int
    event_type: str
    event_time: datetime
    title: str
    description: Optional[str] = None
    impact_level: Optional[str] = None
    related_tickers: Optional[str] = None
    pre_event_returns: Optional[dict] = None
    post_event_returns: Optional[dict] = None
    post_event_updated: bool = False
    indicator_name_cn: Optional[str] = None
    value_display: Optional[str] = None
    source_name: Optional[str] = None


class IndustryIntelligenceDataSource(BaseModel):
    """数据源状态"""
    source: str
    status: str
    last_updated: Optional[str] = None
    indicators_count: int = 0


class IndustryIntelligenceResponse(BaseModel):
    """产业情报统一响应"""
    indicators: list[IndustryIntelligenceIndicator]
    timeline: list[IndustryIntelligenceTimeline]
    data_sources: list[IndustryIntelligenceDataSource]
    stats: dict


@app.get("/api/industry-intelligence", response_model=IndustryIntelligenceResponse)
def get_industry_intelligence(db: Session = Depends(get_db)):
    """
    三合一产业情报接口:
    1. 按供应链位置分组的指标（含 tier/分析/涨跌幅）
    2. 近期时间线事件（含涨跌幅）
    3. 数据源状态 + 统计
    """
    # ── 1. 获取全部指标 + 最新观测值 ──
    indicators = (
        db.query(KeyIndicator)
        .order_by(KeyIndicator.tier, KeyIndicator.category, KeyIndicator.id)
        .all()
    )

    indicator_items = []
    tier_counts = {1: 0, 2: 0, 3: 0}
    with_data = 0

    for ind in indicators:
        latest = (
            db.query(IndicatorObservation)
            .filter(IndicatorObservation.indicator_id == ind.id)
            .order_by(IndicatorObservation.date.desc())
            .first()
        )

        item = IndustryIntelligenceIndicator(
            id=ind.id,
            name=ind.name,
            name_cn=ind.name_cn,
            category=ind.category,
            category_cn=CATEGORY_CN_MAP.get(ind.category, ind.category),
            tier=ind.tier or 3,
            unit=ind.unit,
            source=ind.source,
            source_url=ind.source_url,
            update_frequency=ind.update_frequency,
            description=ind.description,
            related_tickers=ind.related_tickers,
        )

        if ind.tier and ind.tier in tier_counts:
            tier_counts[ind.tier] += 1
        else:
            tier_counts[3] += 1

        if latest:
            item.latest_value = latest.value
            item.latest_date = str(latest.date)
            item.previous_value = latest.previous_value
            item.change_pct = latest.change_pct
            item.data_quality = latest.data_quality
            item.last_updated = str(latest.date)

            # 边际变化
            item.marginal_change_pct = latest.marginal_change_pct
            item.comparison_window = latest.comparison_window
            item.industry_impact = latest.industry_impact
            item.chain_impact = latest.chain_impact
            item.company_impact = latest.company_impact

            # 找上期的日期
            if latest.previous_value is not None:
                prev_obs = (
                    db.query(IndicatorObservation)
                    .filter(
                        IndicatorObservation.indicator_id == ind.id,
                        IndicatorObservation.date < latest.date,
                    )
                    .order_by(IndicatorObservation.date.desc())
                    .first()
                )
                if prev_obs:
                    item.previous_date = str(prev_obs.date)

            # ── 自动计算边际变化（如尚未计算） ──
            if latest.marginal_change_pct is None and latest.value is not None:
                _compute_marginal_change(db, ind, latest)

                # 刷新
                db.refresh(latest)
                item.marginal_change_pct = latest.marginal_change_pct
                item.comparison_window = latest.comparison_window

            # ── 窗口期观测值（用于前端曲线） ──
            window_days = _get_comparison_window_days(ind.update_frequency)
            cutoff = latest.date - timedelta(days=window_days)
            window_obs = (
                db.query(IndicatorObservation)
                .filter(
                    IndicatorObservation.indicator_id == ind.id,
                    IndicatorObservation.date >= cutoff,
                    IndicatorObservation.date <= latest.date,
                )
                .order_by(IndicatorObservation.date.asc())
                .all()
            )
            item.marginal_observations = [
                {"date": str(o.date), "value": o.value}
                for o in window_obs
            ]

            # ── 分析文本（仅从数据库读取缓存，不调用API） ──
            if latest.analysis:
                item.analysis = latest.analysis

            # ── ±10日涨跌幅（仅从 TimelineEvent 缓存读取，不实时拉取） ──
            if latest and ind.related_tickers:
                try:
                    tl_event = (
                        db.query(TimelineEvent)
                        .filter(
                            TimelineEvent.indicator_observation_id == latest.id,
                        )
                        .first()
                    )
                    if tl_event and tl_event.pre_event_returns:
                        item.pre_event_returns = tl_event.pre_event_returns
                        item.post_event_returns = tl_event.post_event_returns
                        item.post_event_updated = tl_event.post_event_updated
                except Exception as e:
                    logger.warning(f"Failed to read returns for {ind.name}: {e}")

            with_data += 1

        indicator_items.append(item)

    # ── 2. 获取近期时间线 ──
    tl_events = (
        db.query(TimelineEvent)
        .order_by(TimelineEvent.event_time.desc())
        .limit(20)
        .all()
    )

    timeline_items = [
        IndustryIntelligenceTimeline(
            id=e.id,
            event_type=e.event_type,
            event_time=e.event_time,
            title=e.title,
            description=e.description,
            impact_level=e.impact_level,
            related_tickers=e.related_tickers,
            pre_event_returns=e.pre_event_returns,
            post_event_returns=e.post_event_returns,
            post_event_updated=e.post_event_updated,
            indicator_name_cn=e.indicator_name_cn,
            value_display=e.value_display,
            source_name=e.source_name,
        )
        for e in tl_events
    ]

    # ── 3. 数据源状态 ──
    source_rows = (
        db.query(KeyIndicator.source, func.count(KeyIndicator.id).label("cnt"))
        .filter(KeyIndicator.source.isnot(None))
        .group_by(KeyIndicator.source)
        .all()
    )

    data_sources = []
    now_dt = datetime.now()
    for src, cnt in source_rows:
        latest_obs = (
            db.query(IndicatorObservation)
            .join(KeyIndicator)
            .filter(KeyIndicator.source == src)
            .order_by(IndicatorObservation.date.desc())
            .first()
        )
        status = "never"
        last_updated = None
        if latest_obs:
            last_updated = str(latest_obs.date)
            days_since = (now_dt.date() - latest_obs.date).days if latest_obs.date else 999
            if days_since <= 1:
                status = "ok"
            elif days_since <= 3:
                status = "stale"
            else:
                status = "outdated"

        data_sources.append(IndustryIntelligenceDataSource(
            source=src,
            status=status,
            last_updated=last_updated,
            indicators_count=cnt,
        ))

    # ── 4. 统计 ──
    stats = {
        "total_indicators": len(indicator_items),
        "tier1_count": tier_counts.get(1, 0),
        "tier2_count": tier_counts.get(2, 0),
        "tier3_count": tier_counts.get(3, 0),
        "with_data": with_data,
    }

    return IndustryIntelligenceResponse(
        indicators=indicator_items,
        timeline=timeline_items,
        data_sources=data_sources,
        stats=stats,
    )


# =========================================================================
# 10d. 批量AI分析 & 产业数据浏览
# =========================================================================


async def _batch_analyze_worker():
    """后台任务：每次最多分析 3 条观测值，避免阻塞主请求。"""
    from database import SessionLocal

    def _run():
        db = SessionLocal()
        try:
            analyzed = batch_analyze_industry_impact(db, limit=3)
            logger.info(f"Background batch analyze completed: {analyzed} observations")
        except Exception as e:
            logger.warning(f"Background batch analyze failed: {e}")
            db.rollback()
        finally:
            db.close()

    await asyncio.to_thread(_run)


@app.post("/api/industry/batch-analyze")
async def trigger_batch_analyze(background_tasks: BackgroundTasks):
    """触发批量AI分析：后台为缺少分析的观测值生成产业链影响分析"""
    background_tasks.add_task(_batch_analyze_worker)
    return {"success": True, "message": "后台批量分析已启动，每次最多处理 3 条观测值"}


@app.get("/api/industry/sequence-timeline")
def get_sequence_timeline(limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    """
    产业情报-序时: 纵向时间轴，每条记录显示比较值和影响解读。
    若前值1条 → 显示前值和新值
    若前值多条 → 显示前一条、前值中最高、前值中最低
    """
    # 合并采集事件和时间线事件，按时间倒序
    tl_events = (
        db.query(TimelineEvent)
        .filter(TimelineEvent.event_type == "collection")
        .order_by(TimelineEvent.event_time.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items = []
    import math as _math

    def _sanitize_floats(obj):
        """递归清洗 NaN/Inf(标准 JSON 不允许)→ None"""
        if isinstance(obj, dict):
            return {k: _sanitize_floats(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_sanitize_floats(v) for v in obj]
        if isinstance(obj, float):
            if _math.isnan(obj) or _math.isinf(obj):
                return None
        return obj

    for e in tl_events:
        item = {
            "id": e.id,
            "event_type": e.event_type,
            "event_time": e.event_time.isoformat() if e.event_time else None,
            "title": e.title,
            "description": e.description,
            "value_display": e.value_display,
            "source_name": e.source_name,
            "indicator_name_cn": e.indicator_name_cn,
            "related_tickers": e.related_tickers,
            "related_indicators": e.related_indicators,
            "impact_level": e.impact_level,
            "pre_event_returns": e.pre_event_returns,
            "post_event_returns": e.post_event_returns,
        }

        # 获取该指标的历史观测值（用于显示前值列表）
        if e.indicator_observation_id:
            obs = db.query(IndicatorObservation).filter(
                IndicatorObservation.id == e.indicator_observation_id
            ).first()
            if obs:
                indicator = db.query(KeyIndicator).filter(
                    KeyIndicator.id == obs.indicator_id
                ).first()
                if indicator:
                    # 获取该指标的所有历史观测值
                    history = (
                        db.query(IndicatorObservation)
                        .filter(
                            IndicatorObservation.indicator_id == indicator.id,
                        )
                        .order_by(IndicatorObservation.date.desc())
                        .limit(10)
                        .all()
                    )

                    # 构建前值列表
                    prev_values = []
                    for h in history:
                        if h.id == obs.id:
                            continue
                        prev_values.append({
                            "date": str(h.date),
                            "value": h.value,
                            "change_pct": h.change_pct,
                        })

                    # 计算前值统计
                    if len(prev_values) == 1:
                        item["previous_single"] = prev_values[0]
                    elif len(prev_values) > 1:
                        item["previous_last"] = prev_values[0]  # 前一条
                        values_only = [p["value"] for p in prev_values if p["value"] is not None]
                        if values_only:
                            item["previous_max"] = max(values_only)
                            item["previous_min"] = min(values_only)

                    # 当前值
                    item["current_value"] = obs.value
                    item["current_date"] = str(obs.date)
                    item["change_pct"] = obs.change_pct
                    item["marginal_change_pct"] = obs.marginal_change_pct
                    item["industry_impact"] = obs.industry_impact
                    item["chain_impact"] = obs.chain_impact
                    item["company_impact"] = obs.company_impact
                    item["unit"] = indicator.unit

        items.append(_sanitize_floats(item))

    return items


@app.get("/api/industry/company-data")
def get_company_data_browse(db: Session = Depends(get_db)):
    """数据浏览-公司: 返回所有公司的行情和财务数据"""
    companies = db.query(Company).all()

    # 批量加载 cache 数据
    cache_records = db.query(StockInfoCache).all()
    cache_map = {}
    for r in cache_records:
        if r.ticker and isinstance(r.data_json, dict):
            cache_map[r.ticker.upper()] = r.data_json

    # 批量加载财务数据
    fins = db.query(Financial).order_by(Financial.fiscal_year.desc()).all()
    fin_map = defaultdict(list)
    for f in fins:
        fin_map[f.company_id].append(f)

    result = []
    for c in companies:
        item = {
            "id": c.id,
            "name": c.name,
            "name_cn": c.name_cn,
            "ticker": c.ticker,
            "company_type": c.company_type,
            "sector": c.sector,
            "is_listed": c.is_listed,
        }

        # 实时行情
        if c.ticker and c.ticker.upper() in cache_map:
            d = cache_map[c.ticker.upper()]
            item["current_price"] = d.get("current_price")
            item["change_pct"] = d.get("change_pct")
            item["market_cap_b"] = d.get("market_cap_b")
            item["pe_ttm"] = d.get("pe_ttm")
            item["price_time"] = d.get("time")
            item["data_source"] = d.get("source", "tencent")

        # 财务数据
        company_fins = fin_map.get(c.id, [])
        item["financials"] = [
            {
                "fiscal_year": f.fiscal_year,
                "revenue": f.revenue,
                "net_income": f.net_income,
                "gross_margin": f.gross_margin,
                "operating_margin": f.operating_margin,
                "net_margin": f.net_margin,
                "pe": f.pe,
                "pb": f.pb,
                "roe": f.roe,
                "data_source": f.data_source,
                "last_verified": str(f.last_verified) if f.last_verified else None,
            }
            for f in company_fins[:5]  # 最近5年
        ]

        result.append(item)

    return result


# =========================================================================
# 11. 评分系统
# =========================================================================

@app.get("/api/scoring/dimensions", response_model=list[ScoringDimensionOut])
def get_scoring_dimensions(db: Session = Depends(get_db)):
    return db.query(ScoringDimension).filter(ScoringDimension.is_active == True).all()


@app.get("/api/scoring/scores", response_model=list[CompanyScoreSummary])
def get_company_scores(db: Session = Depends(get_db)):
    dims = db.query(ScoringDimension).filter(ScoringDimension.is_active == True).all()
    companies = db.query(Company).all()
    all_scores = db.query(CompanyScore).options(joinedload(CompanyScore.dimension)).all()

    score_map = {}
    for s in all_scores:
        score_map.setdefault(s.company_id, {})[s.dimension_id] = s

    result = []
    for c in companies:
        dim_scores = []
        total = 0
        c_scores = score_map.get(c.id, {})
        for d in dims:
            s = c_scores.get(d.id)
            if s:
                weighted = s.score * (d.weight / 100)
                total += weighted
                dim_scores.append({
                    "dimension": d.name_cn or d.name,
                    "weight": d.weight,
                    "score": s.score,
                    "weighted_score": round(weighted, 1),
                })
        result.append(CompanyScoreSummary(
            company_id=c.id, company_name=c.name, name_cn=c.name_cn, ticker=c.ticker,
            company_type=c.company_type, is_listed=c.is_listed,
            total_score=round(total, 1),
            dimension_scores=dim_scores,
        ))

    result.sort(key=lambda x: x.total_score, reverse=True)
    return result


# =========================================================================
# 12. 投资组合
# =========================================================================

@app.get("/api/portfolios", response_model=list[PortfolioOut])
def list_portfolios(db: Session = Depends(get_db)):
    return db.query(Portfolio).filter(Portfolio.is_active == True).all()


@app.get("/api/portfolios/{portfolio_id}", response_model=PortfolioDetail)
def get_portfolio(portfolio_id: int, db: Session = Depends(get_db)):
    p = (db.query(Portfolio)
         .options(
             joinedload(Portfolio.holdings).joinedload(PortfolioHolding.company),
             joinedload(Portfolio.performances),
             joinedload(Portfolio.evaluations),
         )
         .filter(Portfolio.id == portfolio_id).first())
    if not p:
        raise HTTPException(404, "组合不存在")
    return p


@app.get("/api/portfolios/{portfolio_id}/holdings", response_model=list[PortfolioHoldingOut])
def get_portfolio_holdings(portfolio_id: int, db: Session = Depends(get_db)):
    return (db.query(PortfolioHolding)
            .options(joinedload(PortfolioHolding.company))
            .filter(PortfolioHolding.portfolio_id == portfolio_id).all())


@app.get("/api/portfolios/{portfolio_id}/performance", response_model=list[PortfolioPerformanceOut])
def get_portfolio_performance(portfolio_id: int, limit: int = 60, db: Session = Depends(get_db)):
    return (db.query(PortfolioPerformance)
            .filter(PortfolioPerformance.portfolio_id == portfolio_id)
            .order_by(PortfolioPerformance.date.desc()).limit(limit).all())


@app.get("/api/portfolios/{portfolio_id}/evaluations", response_model=list[PortfolioEvaluationOut])
def get_portfolio_evaluations(portfolio_id: int, db: Session = Depends(get_db)):
    return (db.query(PortfolioEvaluation)
            .filter(PortfolioEvaluation.portfolio_id == portfolio_id)
            .order_by(PortfolioEvaluation.date.desc()).all())


@app.post("/api/portfolios/{portfolio_id}/evaluate")
def evaluate_portfolio(portfolio_id: int, db: Session = Depends(get_db)):
    """基于最新市场信息评估组合，给出调整建议"""
    portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    if not portfolio:
        raise HTTPException(404, "组合不存在")

    holdings = (db.query(PortfolioHolding)
                .options(joinedload(PortfolioHolding.company))
                .filter(PortfolioHolding.portfolio_id == portfolio_id).all())

    # Check latest market data for each holding
    latest_prices = {}
    for h in holdings:
        md = (db.query(MarketData)
              .filter(MarketData.company_id == h.company_id)
              .order_by(MarketData.date.desc()).first())
        if md:
            latest_prices[h.company_id] = md.stock_price

    # Check for recent judgment changes
    recent_judgments = (db.query(JudgmentLog)
                        .filter(JudgmentLog.date > func.date('now', '-7 days'))
                        .count())

    # Check latest indicators
    latest_indicators = {}
    for ind in db.query(KeyIndicator).all():
        obs = (db.query(IndicatorObservation)
               .filter(IndicatorObservation.indicator_id == ind.id)
               .order_by(IndicatorObservation.date.desc()).first())
        if obs:
            latest_indicators[ind.name_cn or ind.name] = obs.value

    total_value = db.query(PortfolioPerformance).filter(
        PortfolioPerformance.portfolio_id == portfolio_id
    ).order_by(PortfolioPerformance.date.desc()).first()

    suggestions = []
    warnings = []

    if recent_judgments > 0:
        warnings.append(f"近期有{recent_judgments}条新判断记录，建议查看判断日志页")

    for h in holdings:
        score_row = (db.query(func.avg(CompanyScore.score))
                     .filter(CompanyScore.company_id == h.company_id).scalar())
        if score_row and score_row < 50:
            suggestions.append(f"{h.company.name}综合评分{score_row:.0f}，建议关注是否需要调仓")

    if latest_indicators.get("HBM3E价格", 0) > 25:
        suggestions.append("HBM3E价格持续走高，利好SK海力士持仓")
    if latest_indicators.get("GPU交货周期", 0) < 25:
        warnings.append("GPU交货周期缩短，供应改善可能影响定价能力")

    evaluation = PortfolioEvaluation(
        portfolio_id=portfolio_id,
        date=func.date('now'),
        summary="基于最新市场数据的自动评估",
        adjustment_suggestion="; ".join(suggestions) if suggestions else "当前持仓配置合理，无需调整",
        risk_warnings="; ".join(warnings) if warnings else "暂无重大风险信号",
        suggested_changes={"suggestions": suggestions, "warnings": warnings},
        is_actionable=bool(suggestions) or bool(warnings),
        created_by="system",
    )
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)
    return evaluation


# ── 关注组合跟踪（基于 Follow 表，替代 Portfolio） ────────────

@app.get("/api/portfolio/tracking", response_model=PortfolioTrackingData)
def get_folio_tracking(db: Session = Depends(get_db)):
    """基于关注公司的组合跟踪数据：实时价+期间收益+PE/EPS"""
    follows = (db.query(Follow)
               .options(joinedload(Follow.company))
               .all())

    if not follows:
        return PortfolioTrackingData(
            portfolio_id=0,
            portfolio_name="关注组合",
            total_weight=0.0,
            cash_weight=100.0,
            holdings=[],
        )

    # 获取最后更新时间
    last_updated = None
    latest_cache = db.query(StockInfoCache).order_by(StockInfoCache.updated_at.desc()).first()
    if latest_cache and latest_cache.updated_at:
        if hasattr(latest_cache.updated_at, 'strftime'):
            last_updated = latest_cache.updated_at.strftime("%Y-%m-%d %H:%M")
        else:
            last_updated = str(latest_cache.updated_at)

    holding_data_list = []
    for f in follows:
        company = f.company
        if not company:
            continue

        cache = (db.query(StockInfoCache)
                 .filter(StockInfoCache.ticker == company.ticker)
                 .order_by(StockInfoCache.updated_at.desc()).first())
        cache_data = {}
        if cache and cache.data_json:
            dj = cache.data_json
            cache_data = {
                "current_price": dj.get("current_price"),
                "pe_ttm": dj.get("pe_ttm"),
                "market_cap_b": dj.get("market_cap_b"),
                "change_pct": dj.get("change_pct"),
            }
        else:
            cache_data = {"current_price": None, "pe_ttm": None, "market_cap_b": None, "change_pct": None}

        returns = compute_holding_returns(db, company.ticker) if company.ticker else {}
        eps = derive_eps_metrics(company.id, company.ticker, cache_data, db)

        holding_data_list.append(HoldingTrackingData(
            holding_id=f.id,
            company_id=company.id,
            ticker=company.ticker or "",
            company_name=company.name,
            name_cn=company.name_cn,
            weight=f.weight,
            current_price=cache_data.get("current_price"),
            change_pct=cache_data.get("change_pct"),
            pe_ttm=cache_data.get("pe_ttm"),
            market_cap_b=cache_data.get("market_cap_b"),
            return_1d=returns.get("return_1d"),
            return_1w=returns.get("return_1w"),
            return_1m=returns.get("return_1m"),
            return_3m=returns.get("return_3m"),
            return_6m=returns.get("return_6m"),
            return_1y=returns.get("return_1y"),
            return_3y=returns.get("return_3y"),
            eps_ttm=eps.get("eps_ttm"),
            eps_2025=eps.get("eps_2025"),
            growth_rate=eps.get("growth_rate"),
            eps_2026e=eps.get("eps_2026e"),
            eps_2027e=eps.get("eps_2027e"),
            forward_pe_2026e=eps.get("forward_pe_2026e"),
            forward_pe_2027e=eps.get("forward_pe_2027e"),
        ))

    aggregates = compute_portfolio_aggregates([d.model_dump() for d in holding_data_list])

    return PortfolioTrackingData(
        portfolio_id=0,
        portfolio_name="关注组合",
        last_updated=last_updated,
        total_weight=aggregates["total_weight"],
        cash_weight=aggregates["cash_weight"],
        weighted_pe=aggregates.get("weighted_pe"),
        weighted_eps_ttm=aggregates.get("weighted_eps_ttm"),
        weighted_eps_2026e=aggregates.get("weighted_eps_2026e"),
        weighted_eps_2027e=aggregates.get("weighted_eps_2027e"),
        weighted_forward_pe_2026e=aggregates.get("weighted_forward_pe_2026e"),
        weighted_forward_pe_2027e=aggregates.get("weighted_forward_pe_2027e"),
        weighted_return_1d=aggregates.get("weighted_return_1d"),
        weighted_return_1w=aggregates.get("weighted_return_1w"),
        weighted_return_1m=aggregates.get("weighted_return_1m"),
        weighted_return_3m=aggregates.get("weighted_return_3m"),
        weighted_return_6m=aggregates.get("weighted_return_6m"),
        weighted_return_1y=aggregates.get("weighted_return_1y"),
        weighted_return_3y=aggregates.get("weighted_return_3y"),
        holdings=holding_data_list,
    )


@app.put("/api/portfolio/weight/{follow_id}")
def update_folio_weight(follow_id: int, req: WeightUpdateRequest, db: Session = Depends(get_db)):
    """更新关注公司权重"""
    folio = db.query(Follow).filter(Follow.id == follow_id).first()
    if not folio:
        raise HTTPException(404, "关注记录不存在")
    folio.weight = round(max(0, min(100, req.weight)), 1)
    db.commit()
    return {"success": True, "follow_id": follow_id, "weight": folio.weight}


# =========================================================================
# 13. 综合：产业链总览数据
# =========================================================================

@app.get("/api/industry-overview")
def get_industry_overview(db: Session = Depends(get_db)):
    """获取产业链全景数据"""
    chains = db.query(IndustryChainLink).order_by(IndustryChainLink.sort_order).all()
    result = []
    for cl in chains:
        companies = (db.query(CompanyChainLink)
                     .options(joinedload(CompanyChainLink.company))
                     .filter(CompanyChainLink.chain_link_id == cl.id)
                     .order_by(CompanyChainLink.is_leader.desc())
                     .all())

        # 为每个公司查询 PE_TTM + 分析师预测 PE + 缓存数据
        company_ids = [ccl.company_id for ccl in companies]
        forecast_records = db.query(Forecast).filter(
            Forecast.company_id.in_(company_ids),
            Forecast.target_year.in_([2026, 2027]),
        ).all()
        forecast_map = {}
        for fr in forecast_records:
            forecast_map.setdefault(fr.company_id, {})[fr.target_year] = fr

        # 读取 Financial 表数据
        fin_records = db.query(Financial).filter(
            Financial.company_id.in_(company_ids),
        ).order_by(Financial.fiscal_year.desc()).all()
        latest_fin_map = {}
        fin_2025_map = {}
        for fr in fin_records:
            if fr.company_id not in latest_fin_map:
                latest_fin_map[fr.company_id] = fr
            if fr.fiscal_year == 2025:
                fin_2025_map[fr.company_id] = fr

        # 读取 StockInfoCache（Tencent API / yfinance 真实数据）
        from models import StockInfoCache
        cache_records = db.query(StockInfoCache).filter(
            StockInfoCache.ticker.in_([c.ticker for c in [ccl.company for ccl in companies] if c.ticker])
        ).all()
        cache_map = {r.ticker: r.data_json for r in cache_records}

        supply_demand = db.query(SupplyDemand).filter(
            SupplyDemand.chain_link_id == cl.id).all()

        result.append({
            "chain": {
                "id": cl.id, "name": cl.name, "name_cn": cl.name_cn,
                "market_size_2025": cl.market_size_2025,
                "market_size_2026": cl.market_size_2026,
                "market_size_2027": cl.market_size_2027,
                "growth_rate": cl.growth_rate,
                "entry_barriers": cl.entry_barriers,
                "expansion_difficulty": cl.expansion_difficulty,
                "supply_gap_2025": cl.supply_gap_2025,
                "supply_gap_2026": cl.supply_gap_2026,
                "supply_gap_2027": cl.supply_gap_2027,
                "key_drivers": cl.key_drivers,
                "risks": cl.risks,
            },
            "companies": [{
                "id": ccl.company_id,
                "name": ccl.company.name,
                "name_cn": ccl.company.name_cn,
                "ticker": ccl.company.ticker,
                "company_type": ccl.company.company_type,
                "is_listed": ccl.company.is_listed,
                "revenue_2024": ccl.company.revenue_2024,
                "market_share": ccl.market_share,
                "revenue_share": ccl.revenue_share,
                "is_leader": ccl.is_leader,
                "competitive_advantage": ccl.competitive_advantage,
                # PE_TTM: 优先使用 StockInfoCache（腾讯 API 实时数据）
                "pe_ttm": _get_pe_from_cache(cache_map, ccl.company.ticker, latest_fin_map.get(ccl.company_id)),
                # 数据来源标记: 'tencent_api' | 'seed'
                "pe_source": _get_data_source(cache_map, ccl.company.ticker, "pe_ttm"),
                # 2025 营收（亿 USD）: 优先使用 cache 中 yfinance/腾讯数据
                "revenue_2025_b": _get_revenue_from_cache(cache_map, ccl.company.ticker, fin_2025_map.get(ccl.company_id)),
                "revenue_source": _get_data_source(cache_map, ccl.company.ticker, "revenue_b"),
                # 价格数据
                "current_price": _get_cache_field(cache_map, ccl.company.ticker, "current_price"),
                "current_price_usd": (_get_cache_field(cache_map, ccl.company.ticker, "current_price_usd")
                                      or _get_cache_field(cache_map, ccl.company.ticker, "current_price")),
                "market_cap_b": _get_cache_field(cache_map, ccl.company.ticker, "market_cap_b"),
                "change_pct": _get_cache_field(cache_map, ccl.company.ticker, "change_pct"),
                # 分析师预测
                "analyst_pe_2026": getattr(forecast_map.get(ccl.company_id, {}).get(2026), "pe_est", None),
                "analyst_pe_2027": getattr(forecast_map.get(ccl.company_id, {}).get(2027), "pe_est", None),
                "analyst_consensus": getattr(forecast_map.get(ccl.company_id, {}).get(2026), "analyst_consensus", None),
            } for ccl in companies],
            "supply_demand": [{
                "period": sd.period, "supply": sd.supply, "demand": sd.demand,
                "gap_pct": sd.gap_pct, "capacity_utilization": sd.capacity_utilization,
                "lead_time_weeks": sd.lead_time_weeks,
            } for sd in supply_demand],
        })
    return result



# =========================================================================
# 13b. 用户关注（核心公司管理）
# =========================================================================


@app.get("/api/user/follows", response_model=list[FollowOut])
def get_follows(db: Session = Depends(get_db)):
    """获取用户关注的公司列表"""
    follows = db.query(Follow).order_by(Follow.created_at).all()
    company_ids = [f.company_id for f in follows]
    companies = {c.id: c for c in db.query(Company).filter(Company.id.in_(company_ids)).all()} if company_ids else {}
    result = []
    for f in follows:
        co = companies.get(f.company_id)
        result.append(FollowOut(
            id=f.id, company_id=f.company_id, created_at=f.created_at,
            ticker=co.ticker if co else None,
            name=co.name if co else None,
            name_cn=co.name_cn if co else None,
            company_type=co.company_type if co else None,
        ))
    return result


@app.post("/api/user/follow/{company_id}", response_model=FollowActionResponse)
def follow_company(company_id: int, db: Session = Depends(get_db)):
    """关注一家公司（最多7家）"""
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(404, "公司不存在")
    existing = db.query(Follow).filter(Follow.company_id == company_id).first()
    if existing:
        raise HTTPException(409, "该公司已被关注")
    current_count = db.query(Follow).count()
    if current_count >= 7:
        raise HTTPException(400, f"最多关注7家公司，当前已关注{current_count}家")
    follow = Follow(company_id=company_id)
    db.add(follow)
    db.commit()
    db.refresh(follow)
    return FollowActionResponse(success=True, message="关注成功", follow_count=current_count + 1)


@app.delete("/api/user/follow/{company_id}", response_model=FollowActionResponse)
def unfollow_company(company_id: int, db: Session = Depends(get_db)):
    """取消关注一家公司"""
    follow = db.query(Follow).filter(Follow.company_id == company_id).first()
    if not follow:
        raise HTTPException(404, "该公司未被关注")
    db.delete(follow)
    db.commit()
    current_count = db.query(Follow).count()
    return FollowActionResponse(success=True, message="已取消关注", follow_count=current_count)


@app.post("/api/user/follows/refresh-prices")
def refresh_follow_prices(db: Session = Depends(get_db)):
    """批量刷新已关注公司的实时价格（调用腾讯API）"""
    follows = db.query(Follow).all()
    if not follows:
        return {"success": True, "updated": 0, "errors": 0, "message": "暂无关注的公司"}
    f_company_ids = [f.company_id for f in follows]
    f_companies = {c.id: c for c in db.query(Company).filter(Company.id.in_(f_company_ids)).all()} if f_company_ids else {}
    updated = 0
    errors = 0
    for f in follows:
        co = f_companies.get(f.company_id)
        if not co or not co.ticker:
            continue
        try:
            live = get_stock_info(co.ticker)
            if live and live.get("source"):
                existing = db.query(StockInfoCache).filter(StockInfoCache.ticker == co.ticker.upper()).first()
                if existing:
                    existing.data_json = live
                    existing.updated_at = date.today()
                else:
                    db.add(StockInfoCache(ticker=co.ticker.upper(), data_json=live, updated_at=date.today()))
                updated += 1
        except Exception as e:
            logger.warning(f"刷新 {co.ticker} 价格失败: {e}")
            errors += 1
    db.commit()
    return {"success": True, "updated": updated, "errors": errors}


# =========================================================================
# 14. 估值模型
# =========================================================================

# 预定义同群组
PEER_GROUPS = {
    "gpu_ai": {
        "name_cn": "GPU/AI加速器",
        "description": "AI芯片设计核心厂商对比",
        "companies": ["NVIDIA", "AMD", "Intel", "Broadcom"],
    },
    "memory": {
        "name_cn": "存储/HBM",
        "description": "AI存储芯片核心厂商对比，含国内外公司",
        "companies": ["SK Hynix", "Samsung Memory", "Micron", "Kioxia", "YMTC"],
    },
    "foundry": {
        "name_cn": "晶圆代工",
        "description": "全球晶圆代工厂对比",
        "companies": ["TSMC", "Samsung", "SMIC", "UMC", "GlobalFoundries"],
    },
    "equipment": {
        "name_cn": "半导体设备",
        "description": "半导体设备龙头对比",
        "companies": ["ASML", "Applied Materials", "Lam Research", "Tokyo Electron", "KLA"],
    },
    "eda_ip": {
        "name_cn": "EDA/IP",
        "description": "芯片设计工具与IP授权商对比",
        "companies": ["Synopsys", "Cadence", "ARM", "Ansys"],
    },
    "packaging": {
        "name_cn": "先进封装",
        "description": "封装测试厂商对比，含中国大陆",
        "companies": ["ASE", "Amkor", "JCET", "Powertech"],
    },
    "cloud": {
        "name_cn": "云厂商",
        "description": "全球云服务商对比",
        "companies": ["Amazon", "Microsoft", "Google Cloud", "Oracle", "Alibaba Cloud", "Tencent Cloud"],
    },
    "llm_ai": {
        "name_cn": "大模型/AI",
        "description": "大模型公司对比（含未上市）",
        "companies": ["OpenAI", "Anthropic", "Baidu", "Tencent", "Alibaba"],
    },
    "application": {
        "name_cn": "AI应用终端",
        "description": "AI应用层龙头对比",
        "companies": ["Meta", "Tesla", "Xiaomi", "Meituan", "Pinduoduo"],
    },
    "networking": {
        "name_cn": "网络互联",
        "description": "AI网络互联厂商对比",
        "companies": ["Marvell", "Arista", "Cisco"],
    },
}


@app.get("/api/valuation/peer-groups")
def list_peer_groups(db: Session = Depends(get_db)):
    """列出所有预定义的同群组"""
    result = []
    for key, g in PEER_GROUPS.items():
        companies = db.query(Company).filter(Company.name.in_(g["companies"])).all()
        name_map = {c.name: c for c in companies}
        result.append({
            "name": key,
            "name_cn": g["name_cn"],
            "description": g["description"],
            "companies": [{
                "id": c.id,
                "name": c.name,
                "name_cn": c.name_cn,
                "ticker": c.ticker,
                "company_type": c.company_type,
                "is_listed": c.is_listed,
            } for name in g["companies"] if (c := name_map.get(name))],
        })
    return result


@app.get("/api/valuation/companies", response_model=list[ValuationCompanyData])
def get_valuation_companies(peer_group: str = None, db: Session = Depends(get_db)):
    """获取公司估值相关数据"""
    q = db.query(Company)
    if peer_group and peer_group in PEER_GROUPS:
        names = PEER_GROUPS[peer_group]["companies"]
        q = q.filter(Company.name.in_(names))
    companies = q.all()

    latest_fin = {}
    for c in companies:
        fin = (db.query(Financial)
               .filter(Financial.company_id == c.id)
               .order_by(Financial.fiscal_year.desc())
               .first())
        if fin:
            latest_fin[c.id] = fin

    # 获取最新市值
    latest_mcaps = {}
    for c in companies:
        md = (db.query(MarketData)
              .filter(MarketData.company_id == c.id)
              .order_by(MarketData.date.desc())
              .first())
        if md and md.market_cap:
            latest_mcaps[c.id] = md.market_cap
        else:
            # 用PE*净利润推算
            fin = latest_fin.get(c.id)
            if fin and fin.pe_ttm and fin.net_income:
                latest_mcaps[c.id] = round(fin.pe_ttm * fin.net_income, 1)

    cagr_cache = {}
    for c in companies:
        fins = (db.query(Financial)
                .filter(Financial.company_id == c.id)
                .order_by(Financial.fiscal_year.asc())
                .all())
        if len(fins) >= 2:
            first, last = fins[0], fins[-1]
            years = last.fiscal_year - first.fiscal_year
            if years > 0 and first.revenue and last.revenue and first.revenue > 0:
                cagr = ((last.revenue / first.revenue) ** (1 / years) - 1) * 100
                cagr_cache[c.id] = round(cagr, 1)

    result = []
    for c in companies:
        fin = latest_fin.get(c.id)
        is_cn = c.name in ("SMIC", "JCET", "Huawei", "YMTC", "ByteDance",
                           "Xiaomi", "Meituan", "Pinduoduo", "Alibaba",
                           "Alibaba Cloud", "Tencent", "Tencent Cloud", "Baidu")
        mcap = latest_mcaps.get(c.id)
        # 从PE_TTM推算市值
        if mcap is None and fin and fin.pe_ttm and fin.net_income:
            mcap = round(fin.pe_ttm * fin.net_income, 1)

        result.append(ValuationCompanyData(
            id=c.id, name=c.name, name_cn=c.name_cn, ticker=c.ticker,
            company_type=c.company_type, is_listed=c.is_listed,
            revenue=fin.revenue if fin else c.revenue_2024,
            net_income=fin.net_income if fin else None,
            net_margin=fin.net_margin if fin else None,
            pe_ttm=fin.pe_ttm if fin else None,
            ps_ttm=fin.ps_ttm if fin else None,
            market_cap=mcap,
            revenue_growth_3y=cagr_cache.get(c.id),
            employee_count=c.employee_count,
            is_chinese=is_cn,
        ))
    return result


@app.post("/api/valuation/calculate", response_model=PeerComparisonResultOut)
def calculate_valuation(params: ValuationParams, db: Session = Depends(get_db)):
    """执行Gordon Growth估值计算"""
    model = GordonGrowthModel(
        discount_rate=params.discount_rate,
        terminal_growth=params.terminal_growth,
        growth_years=params.growth_years,
        china_premium=params.china_premium,
    )

    names = PEER_GROUPS.get(params.peer_group, {}).get("companies", [])
    companies = db.query(Company).filter(Company.name.in_(names)).all()

    # 统一获取财务数据
    latest_fin = {}
    for c in companies:
        fin = (db.query(Financial)
               .filter(Financial.company_id == c.id)
               .order_by(Financial.fiscal_year.desc())
               .first())
        if fin:
            latest_fin[c.id] = fin

    latest_mcaps = {}
    for c in companies:
        md = (db.query(MarketData)
              .filter(MarketData.company_id == c.id)
              .order_by(MarketData.date.desc())
              .first())
        if md and md.market_cap:
            latest_mcaps[c.id] = md.market_cap
        else:
            fin = latest_fin.get(c.id)
            if fin and fin.pe_ttm and fin.net_income:
                latest_mcaps[c.id] = round(fin.pe_ttm * fin.net_income, 1)

    inputs = []
    for c in companies:
        fin = latest_fin.get(c.id)
        is_cn = c.name in ("SMIC", "JCET", "Huawei", "YMTC", "ByteDance",
                           "Xiaomi", "Meituan", "Pinduoduo", "Alibaba",
                           "Alibaba Cloud", "Tencent", "Tencent Cloud", "Baidu")
        mcap = latest_mcaps.get(c.id)
        if mcap is None and fin and fin.pe_ttm and fin.net_income:
            mcap = round(fin.pe_ttm * fin.net_income, 1)
        inputs.append(CompanyValuationInput(
            company_id=c.id, name=c.name, name_cn=c.name_cn,
            ticker=c.ticker, company_type=c.company_type,
            is_listed=c.is_listed,
            revenue=fin.revenue if fin else c.revenue_2024,
            net_income=fin.net_income if fin else None,
            net_margin=fin.net_margin if fin else None,
            pe_ttm=fin.pe_ttm if fin else None,
            ps_ttm=fin.ps_ttm if fin else None,
            market_cap=mcap,
            employee_count=c.employee_count,
            is_chinese=is_cn,
        ))

    result = model.compare_peers(
        peer_group=params.peer_group,
        peer_group_cn=PEER_GROUPS.get(params.peer_group, {}).get("name_cn", params.peer_group),
        companies=inputs,
        revenue_growth=params.revenue_growth,
        net_margin=params.net_margin,
    )

    return PeerComparisonResultOut(
        peer_group=result.peer_group,
        peer_group_cn=result.peer_group_cn,
        companies=[ValuationResultOut(**{
            k: v for k, v in c.__dict__.items()
            if k in ValuationResultOut.model_fields
        }) for c in result.companies],
        params=result.params,
    )


# =========================================================================
# 15. 实时价格数据 (yfinance)
# =========================================================================

@app.get("/api/price/{ticker}")
def get_price_data(ticker: str, days: int = 90, db: Session = Depends(get_db)):
    """获取个股历史价格数据（带缓存）"""
    data = get_price_history_cached(ticker, days=days, db=db)
    return {"ticker": ticker, "data": data}


@app.get("/api/stock-info/{ticker}")
def get_stock_info_endpoint(ticker: str, db: Session = Depends(get_db)):
    """获取股票实时信息（多数据源，带缓存）"""
    info = get_stock_info_cached(ticker, db=db)
    return info


@app.get("/api/market/hot-stocks")
def get_hot_stocks():
    """获取A股市场热门股票（涨跌榜）"""
    data = get_top_gainers_losers(top_n=10)
    return data


@app.get("/api/price/smart/{company_name}")
def get_smart_price(company_name: str, days: int = 90, db: Session = Depends(get_db)):
    """
    智能价格获取: 先查公司 DB 获取 ticker，再根据 ticker 类型选择数据源
    支持 A 股代码自动识别（6位数字 -> akshare）
    """
    company = db.query(Company).filter(Company.name == company_name).first()
    if not company:
        raise HTTPException(404, f"公司 {company_name} 不存在")

    ticker = company.ticker
    if not ticker:
        return {"company": company.name, "ticker": None, "data": [], "note": "该公司没有 ticker"}

    # A 股特别处理: 如果公司类型是中国公司且 ticker 是短格式，尝试映射
    cn_a_share = {
        "SMIC": "688981.SH",
        "JCET": "600584.SH",
    }
    actual_ticker = cn_a_share.get(company.name, ticker)

    data = fetch_price_history(actual_ticker, days=days)
    return {
        "company": company.name,
        "name_cn": company.name_cn,
        "ticker": actual_ticker,
        "data": data,
    }


# =========================================================================
# 16. 估值模型 v2 — 供需感知未来 PE
# =========================================================================

CHINESE_COMPANIES = {
    "SMIC", "JCET", "Huawei", "YMTC", "ByteDance",
    "Xiaomi", "Meituan", "Pinduoduo", "Alibaba",
    "Alibaba Cloud", "Tencent", "Tencent Cloud", "Baidu",
}


def _get_supply_data_for_company(db: Session, company_id: int) -> tuple[float, str, str, float]:
    """
    获取公司的供需聚合数据

    Returns:
        (composite_score, supply_verdict, pricing_power, chain_growth_rate)
    """
    chain_links = (db.query(CompanyChainLink)
                   .filter(CompanyChainLink.company_id == company_id)
                   .all())

    if not chain_links:
        return 50.0, "供需平衡", "定价权中性", 15.0

    analyzer = SupplyDemandAnalyzer()
    scores_with_weights = []
    max_growth = 0.0

    for cl in chain_links:
        chain_link = cl.chain_link or db.query(IndustryChainLink).filter(
            IndustryChainLink.id == cl.chain_link_id).first()
        if not chain_link:
            continue
        supply_records = db.query(SupplyDemand).filter(
            SupplyDemand.chain_link_id == cl.chain_link_id).all()
        score = analyzer.analyze_chain_from_db(chain_link, supply_records)
        weight = cl.revenue_share or cl.market_share or 1.0
        scores_with_weights.append((score, weight))
        if chain_link.growth_rate and chain_link.growth_rate > max_growth:
            max_growth = chain_link.growth_rate

    aggregated = analyzer.aggregate_company_score(scores_with_weights)
    return aggregated.composite_score, aggregated.supply_verdict, aggregated.pricing_power, max_growth


def _get_company_financial_data(db: Session, company_id: int) -> tuple:
    """获取公司最新财务数据和市场数据"""
    fin = (db.query(Financial)
           .filter(Financial.company_id == company_id)
           .order_by(Financial.fiscal_year.desc())
           .first())

    # 市值
    md = (db.query(MarketData)
          .filter(MarketData.company_id == company_id)
          .order_by(MarketData.date.desc())
          .first())
    mcap = md.market_cap if (md and md.market_cap) else None
    if mcap is None and fin and fin.pe_ttm and fin.net_income:
        mcap = round(fin.pe_ttm * fin.net_income, 1)

    # CAGR
    fins = (db.query(Financial)
            .filter(Financial.company_id == company_id)
            .order_by(Financial.fiscal_year.asc())
            .all())
    cagr = None
    if len(fins) >= 2:
        first, last = fins[0], fins[-1]
        years = last.fiscal_year - first.fiscal_year
        if years > 0 and first.revenue and last.revenue and first.revenue > 0:
            cagr = ((last.revenue / first.revenue) ** (1 / years) - 1) * 100
            cagr = round(cagr, 1)

    # 分析师预测
    forecasts = (db.query(Forecast)
                 .filter(Forecast.company_id == company_id)
                 .order_by(Forecast.target_year)
                 .all())
    analyst_pe_2026 = None
    analyst_pe_2027 = None
    analyst_growth = None
    analyst_consensus = None
    for f in forecasts:
        if f.target_year == 2026:
            analyst_pe_2026 = f.pe_est
            analyst_growth = f.revenue_growth_est
            analyst_consensus = f.analyst_consensus
        elif f.target_year == 2027:
            analyst_pe_2027 = f.pe_est
            if analyst_consensus is None:
                analyst_consensus = f.analyst_consensus

    return fin, mcap, cagr, analyst_growth, analyst_pe_2026, analyst_pe_2027, analyst_consensus


@app.get("/api/valuation-v2/chain-scores", response_model=list[ChainSupplyDemandScoreOut])
def get_v2_chain_scores(db: Session = Depends(get_db)):
    """获取所有产业链环节的供需量化分数"""
    chains = db.query(IndustryChainLink).order_by(IndustryChainLink.sort_order).all()
    analyzer = SupplyDemandAnalyzer()
    results = []

    for chain in chains:
        supply_records = db.query(SupplyDemand).filter(
            SupplyDemand.chain_link_id == chain.id).all()
        score = analyzer.analyze_chain_from_db(chain, supply_records)
        results.append(ChainSupplyDemandScoreOut(
            chain_link_id=score.chain_link_id,
            chain_name=score.chain_name,
            chain_name_cn=score.chain_name_cn,
            gap_pct=score.gap_pct,
            capacity_utilization=score.capacity_utilization,
            lead_time_weeks=score.lead_time_weeks,
            gap_score=score.gap_score,
            utilization_score=score.utilization_score,
            lead_time_score=score.lead_time_score,
            composite_score=score.composite_score,
            supply_verdict=score.supply_verdict,
            pricing_power=score.pricing_power,
        ))

    return results


@app.get("/api/valuation-v2/company-adjustments", response_model=list[CompanyAdjustmentOut])
def get_v2_company_adjustments(peer_group: str = None, db: Session = Depends(get_db)):
    """获取公司的推荐估值参数"""
    if peer_group and peer_group in PEER_GROUPS:
        names = PEER_GROUPS[peer_group]["companies"]
        companies = db.query(Company).filter(Company.name.in_(names)).all()
    else:
        companies = db.query(Company).all()

    results = []
    for c in companies:
        composite, verdict, power, chain_growth = _get_supply_data_for_company(db, c.id)
        fin, mcap, cagr, analyst_growth, _, _, _ = _get_company_financial_data(db, c.id)

        input_data = CompanyInput(
            company_id=c.id, name=c.name, name_cn=c.name_cn,
            ticker=c.ticker, company_type=c.company_type,
            revenue=fin.revenue if fin else c.revenue_2024,
            net_income=fin.net_income if fin else None,
            net_margin=fin.net_margin if fin else None,
            pe_ttm=fin.pe_ttm if fin else None,
            market_cap=mcap,
            chain_composite_score=composite,
            supply_verdict=verdict, pricing_power=power,
            cagr_3y=cagr, analyst_growth_est=analyst_growth,
            chain_growth_rate=chain_growth,
        )
        model = FuturePEModel()
        base_growth, supply_adj, final_growth = model.recommend_growth(input_data)
        final_margin = model.recommend_net_margin(input_data)

        results.append(CompanyAdjustmentOut(
            company_id=c.id, name=c.name, name_cn=c.name_cn,
            ticker=c.ticker,
            primary_chain="",
            chain_composite_score=composite,
            recommended_growth=round(final_growth, 1),
            recommended_net_margin=round(final_margin, 1),
            current_growth_cagr=cagr,
            analyst_growth_est=analyst_growth,
            current_net_margin=fin.net_margin if fin else None,
            supply_verdict=verdict,
        ))

    return results


@app.post("/api/valuation-v2/calculate", response_model=FuturePEComparisonResultOut)
def calculate_v2_future_pe(params: FuturePEValuationParams, db: Session = Depends(get_db)):
    """使用供需感知未来 PE 模型进行估值"""
    model = FuturePEModel(
        growth_years=params.growth_years,
        use_supply_demand=params.use_supply_demand,
    )

    names = PEER_GROUPS.get(params.peer_group, {}).get("companies", [])
    db_companies = db.query(Company).filter(Company.name.in_(names)).all()

    inputs = []
    for c in db_companies:
        composite, verdict, power, chain_growth = _get_supply_data_for_company(db, c.id)
        fin, mcap, cagr, analyst_growth, ape26, ape27, consensus = _get_company_financial_data(db, c.id)
        is_cn = c.name in CHINESE_COMPANIES

        inputs.append(CompanyInput(
            company_id=c.id, name=c.name, name_cn=c.name_cn,
            ticker=c.ticker, company_type=c.company_type,
            revenue=fin.revenue if fin else c.revenue_2024,
            net_income=fin.net_income if fin else None,
            net_margin=fin.net_margin if fin else None,
            pe_ttm=fin.pe_ttm if fin else None,
            ps_ttm=fin.ps_ttm if fin else None,
            market_cap=mcap,
            chain_composite_score=composite,
            supply_verdict=verdict,
            pricing_power=power,
            cagr_3y=cagr,
            analyst_growth_est=analyst_growth,
            chain_growth_rate=chain_growth,
            analyst_pe_2026=ape26,
            analyst_pe_2027=ape27,
            analyst_consensus=consensus,
        ))

    result = model.evaluate_peers(
        peer_group=params.peer_group,
        peer_group_cn=PEER_GROUPS.get(params.peer_group, {}).get("name_cn", params.peer_group),
        companies=inputs,
        user_growth=params.revenue_growth,
        user_net_margin=params.net_margin,
    )

    return FuturePEComparisonResultOut(
        peer_group=result.peer_group,
        peer_group_cn=result.peer_group_cn,
        companies=[FuturePEValuationResultOut(**{
            k: v for k, v in c.__dict__.items()
            if k in FuturePEValuationResultOut.model_fields
        }) for c in result.companies],
        params=result.params,
    )

# =========================================================================
# Static frontend (Zeabur / Docker deployment)
# =========================================================================

if os.path.exists("static") and os.path.isdir("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="frontend")
