from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, ForeignKey, Date, DateTime, Text, Boolean, JSON, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from database import Base


# ── Original Tables (kept) ────────────────────────────────────────

class Company(Base):
    __tablename__ = "companies"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    name_cn = Column(String, nullable=True)                  # 中文名称
    ticker = Column(String, nullable=True, index=True)
    sector = Column(String)
    description = Column(Text, nullable=True)
    logo_url = Column(String, nullable=True)
    is_listed = Column(Boolean, default=True)               # 是否上市
    company_type = Column(String, nullable=True)             # chip_design, manufacturing, memory, equipment, eda, cloud, llm, application, packaging, networking
    revenue_2024 = Column(Float, nullable=True)              # 2024年营收(亿美元)
    employee_count = Column(Integer, nullable=True)          # 员工数

    products = relationship("Product", back_populates="company")
    market_data = relationship("MarketData", back_populates="company")
    chain_links = relationship("CompanyChainLink", back_populates="company")
    financials = relationship("Financial", back_populates="company")
    forecasts = relationship("Forecast", back_populates="company")
    scores = relationship("CompanyScore", back_populates="company")


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    name = Column(String, index=True)
    category = Column(String)
    architecture = Column(String, nullable=True)
    release_date = Column(Date, nullable=True)
    description = Column(Text, nullable=True)
    company = relationship("Company", back_populates="products")
    metrics = relationship("ProductMetric", back_populates="product")


class ProductMetric(Base):
    __tablename__ = "product_metrics"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    metric_name = Column(String)
    metric_value = Column(Float)
    unit = Column(String)
    product = relationship("Product", back_populates="metrics")


class MarketData(Base):
    __tablename__ = "market_data"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    date = Column(Date, index=True)
    stock_price = Column(Float, nullable=True)
    market_cap = Column(Float, nullable=True)
    volume = Column(Float, nullable=True)
    company = relationship("Company", back_populates="market_data")


class StorageProduct(Base):
    __tablename__ = "storage_products"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    name = Column(String, index=True)
    storage_type = Column(String)
    capacity = Column(String, nullable=True)
    read_speed = Column(Float, nullable=True)
    write_speed = Column(Float, nullable=True)
    price = Column(Float, nullable=True)
    description = Column(Text, nullable=True)


# ── NEW: 产业链环节 ─────────────────────────────────────────────

class IndustryChainLink(Base):
    """产业链环节"""
    __tablename__ = "industry_chain_links"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)          # 环节名称
    name_cn = Column(String, nullable=True)                 # 中文名称
    description = Column(Text, nullable=True)
    market_size_2025 = Column(Float, nullable=True)         # 2025市场容量(亿美元)
    market_size_2026 = Column(Float, nullable=True)         # 2026E
    market_size_2027 = Column(Float, nullable=True)         # 2027E
    growth_rate = Column(Float, nullable=True)              # CAGR %
    entry_barriers = Column(Text, nullable=True)            # 进入壁垒描述
    expansion_difficulty = Column(String, nullable=True)    # 扩产难度: 高/中/低
    supply_gap_2025 = Column(String, nullable=True)         # 供需缺口描述
    supply_gap_2026 = Column(String, nullable=True)
    supply_gap_2027 = Column(String, nullable=True)
    key_drivers = Column(Text, nullable=True)               # 增长驱动力
    risks = Column(Text, nullable=True)                     # 风险因素
    sort_order = Column(Integer, default=0)                 # 排序
    data_source = Column(String, nullable=True)              # 数据来源: fred_api / wind_api / tradingeconomics / world_bank / web_scrape
    last_verified = Column(Date, nullable=True)              # 最后验证日期

    companies = relationship("CompanyChainLink", back_populates="chain_link")


class CompanyChainLink(Base):
    """公司与产业链环节关联"""
    __tablename__ = "company_chain_links"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    chain_link_id = Column(Integer, ForeignKey("industry_chain_links.id"))
    market_share = Column(Float, nullable=True)             # 市场份额 %
    revenue_share = Column(Float, nullable=True)            # 收入占比 %
    is_leader = Column(Boolean, default=False)              # 是否龙头
    competitive_advantage = Column(Text, nullable=True)     # 竞争优势
    notes = Column(Text, nullable=True)
    data_source = Column(String, nullable=True)              # 数据来源
    last_verified = Column(Date, nullable=True)              # 最后验证日期

    company = relationship("Company", back_populates="chain_links")
    chain_link = relationship("IndustryChainLink", back_populates="companies")


class DataSource(Base):
    """数据来源追踪 — 记录每行数据的完整来源链"""
    __tablename__ = "data_sources"
    id = Column(Integer, primary_key=True, index=True)
    table_name = Column(String, index=True)                  # "industry_chain_links" / "company_chain_links" / "financials"
    row_id = Column(Integer)                                 # 对应行 ID
    source_type = Column(String)                             # "fred_api" / "tradingeconomics" / "world_bank" / "wind_api" / "web_scrape" / "alice_mkt_sizing"
    source_detail = Column(Text, nullable=True)              # 具体描述 e.g. "FRED series INDPRO, retrieved 2026-06-11"
    confidence = Column(String, nullable=True)               # "高" / "中" / "低"
    collected_at = Column(DateTime, default=datetime.utcnow)  # 采集时间
    url = Column(String, nullable=True)                      # 来源 URL (for web scraped data)


# ── NEW: 公司财务与估值 ────────────────────────────────────────

class Financial(Base):
    """公司年度财务与估值指标"""
    __tablename__ = "financials"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    fiscal_year = Column(Integer, index=True)               # 财年
    revenue = Column(Float, nullable=True)                  # 营收(亿美元)
    revenue_growth = Column(Float, nullable=True)           # 营收增长率 %
    net_income = Column(Float, nullable=True)               # 净利润(亿美元)
    gross_margin = Column(Float, nullable=True)             # 毛利率 %
    operating_margin = Column(Float, nullable=True)         # 营业利润率 %
    net_margin = Column(Float, nullable=True)               # 净利率 %
    eps = Column(Float, nullable=True)                      # 每股收益
    pe = Column(Float, nullable=True)                       # PE
    pb = Column(Float, nullable=True)                       # PB
    ps = Column(Float, nullable=True)                       # PS
    ev_ebitda = Column(Float, nullable=True)                # EV/EBITDA
    roe = Column(Float, nullable=True)                      # ROE %
    debt_equity = Column(Float, nullable=True)              # 负债权益比
    dividend_yield = Column(Float, nullable=True)           # 股息率 %
    pe_ttm = Column(Float, nullable=True)                    # PE(TTM)
    ps_ttm = Column(Float, nullable=True)                    # PS(TTM)
    data_source = Column(String, nullable=True)              # 数据来源: wind_api / fred_api / estimated
    last_verified = Column(Date, nullable=True)              # 最后验证日期
    currency = Column(String, nullable=True)              # 报表币种: USD/KRW/TWD/JPY/EUR
    fx_rate = Column(Float, nullable=True)                # 报表币种 / USD 汇率
    original_revenue = Column(Float, nullable=True)       # 原始营收（报表币种单位）
    original_net_income = Column(Float, nullable=True)    # 原始净利润（报表币种单位）

    company = relationship("Company", back_populates="financials")


# ── NEW: 供需分析 ──────────────────────────────────────────────

class SupplyDemand(Base):
    """产业链供需数据"""
    __tablename__ = "supply_demand"
    id = Column(Integer, primary_key=True, index=True)
    chain_link_id = Column(Integer, ForeignKey("industry_chain_links.id"))
    period = Column(String)                                  # 2025, 2026E, 2027E
    supply = Column(Float, nullable=True)                   # 供应量
    demand = Column(Float, nullable=True)                   # 需求量
    unit = Column(String, nullable=True)                    # 单位
    gap_pct = Column(Float, nullable=True)                  # 缺口百分比
    gap_description = Column(Text, nullable=True)           # 缺口描述
    capacity_utilization = Column(Float, nullable=True)     # 产能利用率 %
    lead_time_weeks = Column(Integer, nullable=True)        # 交货周期(周)

    chain_link = relationship("IndustryChainLink")


# ── NEW: 关键可观察指标 ────────────────────────────────────────

class KeyIndicator(Base):
    """关键可观察指标定义"""
    __tablename__ = "key_indicators"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)                       # 指标名称
    name_cn = Column(String, nullable=True)                 # 中文名称
    unit = Column(String, nullable=True)                    # 单位
    source = Column(String, nullable=True)                  # 数据来源
    source_url = Column(String, nullable=True)              # 来源URL
    category = Column(String, nullable=True)                # 分类
    description = Column(Text, nullable=True)
    impact_analysis = Column(Text, nullable=True)           # 影响分析
    is_automated = Column(Boolean, default=False)           # 是否可自动采集
    update_frequency = Column(String, nullable=True)        # 更新频率: "daily"/"weekly"/"monthly"/"quarterly"/"annual"
    collection_method = Column(Text, nullable=True)         # 采集方法描述
    tier = Column(Integer, default=3)                      # 1=P0核心 2=P1重要 3=P2参考
    related_tickers = Column(String, nullable=True)        # 关联ticker "TSM,NVDA,AMD"

    # 边际变化配置
    comparison_window = Column(String, nullable=True)       # 默认比较窗口: "30d"/"90d"/"last_change"
                                                            # daily/weekly → 30d
                                                            # monthly/quarterly → 90d
                                                            # quarterly+ → last_change

    observations = relationship("IndicatorObservation", back_populates="indicator")
    _cached_observations = None


class IndicatorObservation(Base):
    """指标观测值"""
    __tablename__ = "indicator_observations"
    id = Column(Integer, primary_key=True, index=True)
    indicator_id = Column(Integer, ForeignKey("key_indicators.id"))
    date = Column(Date, index=True)
    value = Column(Float)
    previous_value = Column(Float, nullable=True)           # 上期值
    change_pct = Column(Float, nullable=True)               # 变化百分比
    note = Column(Text, nullable=True)                      # 备注/解读
    data_quality = Column(String, nullable=True)            # 数据质量
    analysis = Column(Text, nullable=True)                 # AI生成/人工编写的一句话分析

    # 边际变化分析字段
    marginal_change_pct = Column(Float, nullable=True)      # 边际变化百分比（对比最近一次值）
    comparison_window = Column(String, nullable=True)       # 比较窗口: "30d" / "90d" / "last_change"
    industry_impact = Column(Text, nullable=True)          # 行业景气度影响分析（AI生成）
    chain_impact = Column(Text, nullable=True)             # 产业链影响分析
    company_impact = Column(Text, nullable=True)           # 重点公司影响分析

    indicator = relationship("KeyIndicator", back_populates="observations")


# ── NEW: 预测数据 ──────────────────────────────────────────────

class Forecast(Base):
    """龙头公司预测"""
    __tablename__ = "forecasts"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    target_year = Column(Integer, index=True)                # 预测年度
    revenue_est = Column(Float, nullable=True)               # 营收预测(亿美元)
    revenue_growth_est = Column(Float, nullable=True)        # 营收增长预测 %
    pe_est = Column(Float, nullable=True)                    # PE预测
    ps_est = Column(Float, nullable=True)                    # PS预测
    market_cap_est = Column(Float, nullable=True)            # 市值预测(亿美元)
    supply_balance_note = Column(Text, nullable=True)        # 供需平衡判断
    confidence = Column(String, nullable=True)               # 置信度: 高/中/低
    analyst_consensus = Column(String, nullable=True)        # 分析师共识
    key_assumptions = Column(Text, nullable=True)            # 关键假设
    upside_risks = Column(Text, nullable=True)               # 上行风险
    downside_risks = Column(Text, nullable=True)             # 下行风险

    company = relationship("Company", back_populates="forecasts")


# ── NEW: 判断日志 ──────────────────────────────────────────────

class JudgmentLog(Base):
    """重大判断变化记录"""
    __tablename__ = "judgment_logs"
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, index=True)
    title = Column(String)                                   # 标题
    description = Column(Text, nullable=True)                # 描述
    previous_view = Column(Text, nullable=True)              # 此前判断
    new_view = Column(Text, nullable=True)                   # 新判断
    impact_level = Column(String, nullable=True)             # 影响程度: 重大/中等/轻微
    related_companies = Column(String, nullable=True)        # 相关公司(逗号分隔)
    related_indicators = Column(String, nullable=True)       # 相关指标(逗号分隔)
    evidence = Column(Text, nullable=True)                   # 证据/依据
    action_taken = Column(Text, nullable=True)               # 采取行动


# ── NEW: 评分系统 ──────────────────────────────────────────────

class ScoringDimension(Base):
    """评分维度定义"""
    __tablename__ = "scoring_dimensions"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)                       # 维度名称
    name_cn = Column(String, nullable=True)                  # 中文名称
    weight = Column(Float)                                   # 权重(%)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    min_score = Column(Float, default=0)
    max_score = Column(Float, default=100)


class CompanyScore(Base):
    """公司评分"""
    __tablename__ = "company_scores"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    dimension_id = Column(Integer, ForeignKey("scoring_dimensions.id"))
    score = Column(Float)                                    # 得分
    reason = Column(Text, nullable=True)                     # 评分理由
    date_updated = Column(Date, nullable=True)

    company = relationship("Company", back_populates="scores")
    dimension = relationship("ScoringDimension")


# ── NEW: 投资组合 ──────────────────────────────────────────────

class Portfolio(Base):
    """投资组合"""
    __tablename__ = "portfolios"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)                                    # 组合名称
    description = Column(Text, nullable=True)
    created_date = Column(Date)
    initial_capital = Column(Float, default=1000000.0)       # 初始资金(美元)
    rebalance_frequency = Column(String, default="monthly")  # 调仓频率
    is_active = Column(Boolean, default=True)
    strategy_notes = Column(Text, nullable=True)             # 策略说明

    holdings = relationship("PortfolioHolding", back_populates="portfolio")
    performances = relationship("PortfolioPerformance", back_populates="portfolio")
    evaluations = relationship("PortfolioEvaluation", back_populates="portfolio")


class PortfolioHolding(Base):
    """组合持仓"""
    __tablename__ = "portfolio_holdings"
    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"))
    company_id = Column(Integer, ForeignKey("companies.id"))
    weight = Column(Float)                                   # 目标权重(%)
    actual_weight = Column(Float, nullable=True)             # 实际权重(%)
    shares = Column(Float, nullable=True)                    # 持股数
    avg_cost = Column(Float, nullable=True)                  # 平均成本
    current_price = Column(Float, nullable=True)             # 当前价格
    market_value = Column(Float, nullable=True)              # 市值
    return_pct = Column(Float, nullable=True)                # 收益率%
    allocation_reason = Column(Text, nullable=True)          # 配置理由
    date_added = Column(Date, nullable=True)

    portfolio = relationship("Portfolio", back_populates="holdings")
    company = relationship("Company")


class PortfolioPerformance(Base):
    """组合表现"""
    __tablename__ = "portfolio_performances"
    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"))
    date = Column(Date, index=True)
    total_value = Column(Float)                              # 总市值
    cash = Column(Float, default=0)                          # 现金
    daily_return = Column(Float, nullable=True)              # 日收益率%
    cumulative_return = Column(Float, nullable=True)         # 累计收益率%
    benchmark_return = Column(Float, nullable=True)          # 基准收益率%
    alpha = Column(Float, nullable=True)                     # 超额收益
    sharpe_ratio = Column(Float, nullable=True)              # 夏普比率
    max_drawdown = Column(Float, nullable=True)              # 最大回撤%
    notes = Column(Text, nullable=True)

    portfolio = relationship("Portfolio", back_populates="performances")


class PortfolioEvaluation(Base):
    """组合评价与调整建议"""
    __tablename__ = "portfolio_evaluations"
    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"))
    date = Column(Date, index=True)
    summary = Column(Text, nullable=True)                    # 评价总结
    adjustment_suggestion = Column(Text, nullable=True)      # 调整建议
    suggested_changes = Column(JSON, nullable=True)          # 建议变更(JSON)
    risk_warnings = Column(Text, nullable=True)              # 风险警告
    conviction_changes = Column(Text, nullable=True)         # 信心变化
    is_actionable = Column(Boolean, default=False)           # 是否需要行动
    created_by = Column(String, default="system")            # 创建者
    portfolio = relationship("Portfolio", back_populates="evaluations")


# ── 用户关注（核心公司）───────────────────────────────────────────

class Follow(Base):
    """用户关注的核心公司（最多7家）"""
    __tablename__ = "follows"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), unique=True, nullable=False)
    weight = Column(Float, default=0.0)           # 组合目标权重 %
    created_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", lazy="joined")


# ── 价格缓存 ──────────────────────────────────────────────────

# ── NEW: 时间线事件（合并采集日志和判断日志）────────────────────────

class TimelineEvent(Base):
    """统一时间线事件 — 合并采集日志和判断日志"""
    __tablename__ = "timeline_events"
    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String, index=True)               # "judgment" | "collection"
    event_time = Column(DateTime, index=True)              # 事件发生时间
    title = Column(String)                                 # 标题
    description = Column(Text, nullable=True)              # 描述
    impact_level = Column(String, nullable=True)           # 仅 judgment 类型: 重大/中等/轻微
    related_tickers = Column(String, nullable=True)        # 相关 ticker (逗号分隔)
    related_indicators = Column(String, nullable=True)     # 相关指标 (逗号分隔)

    # 涨跌幅缓存 (JSON dict: {"NVDA": {"abs": 5.2, "rel": 2.1}, "SOX": {"abs": 3.1}})
    pre_event_returns = Column(JSON, nullable=True)        # 事件前10日涨跌幅
    post_event_returns = Column(JSON, nullable=True)       # 事件后10日涨跌幅
    post_event_updated = Column(Boolean, default=False)    # +10日数据是否已获取

    # 关联来源
    judgment_log_id = Column(Integer, ForeignKey("judgment_logs.id"), nullable=True)
    indicator_observation_id = Column(Integer, ForeignKey("indicator_observations.id"), nullable=True)

    # 采集条目专用字段
    source_name = Column(String, nullable=True)            # 数据源名称 (tsmc_ir, ...)
    indicator_name_cn = Column(String, nullable=True)      # 指标中文名
    value_display = Column(String, nullable=True)          # 值展示文本 e.g. "NT$4,169亿"


class PriceCache(Base):
    """外部API价格数据缓存"""
    __tablename__ = "price_cache"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)                       # TSM, EWY, AIA
    date = Column(Date, index=True)                            # 交易日
    price = Column(Float)                                      # 收盘价
    change_pct = Column(Float, nullable=True)                  # 涨跌幅
    volume = Column(Float, nullable=True)                      # 成交量
    source = Column(String)                                    # tencent / yfinance / akshare / seed
    updated_at = Column(Date, nullable=True)                   # 缓存时间


class StockInfoCache(Base):
    """股票基本信息缓存"""
    __tablename__ = "stock_info_cache"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)
    data_json = Column(JSON)                                   # 完整info数据
    updated_at = Column(Date, nullable=True)                   # 缓存时间


class FxRateCache(Base):
    """USD 交叉汇率缓存（来自公开 CDN）"""
    __tablename__ = "fx_rate_cache"
    __table_args__ = (
        UniqueConstraint("base_currency", "date", name="uq_fx_rate_cache_base_date"),
    )
    id = Column(Integer, primary_key=True, index=True)
    base_currency = Column(String, index=True)   # e.g. KRW
    quote_currency = Column(String, index=True)  # USD
    rate = Column(Float)                         # 1 USD = rate base_currency
    date = Column(Date, index=True)
    source = Column(String, default="fawazahmed0-cdn")
    updated_at = Column(DateTime, default=datetime.utcnow)


class OverseasFinancialUpdate(Base):
    """海外公司 yfinance 数据补全进度表"""
    __tablename__ = "overseas_financial_updates"
    __table_args__ = (
        Index("ix_overseas_ticker_task", "ticker", "task"),
    )
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)
    task = Column(String, index=True)            # fy:2024 / fy:2025 / ttm:2026 / pe:2024-12-31 / pe:2025-12-31 / pe:latest
    status = Column(String, default="pending")   # pending / success / skipped / failed
    error_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    last_attempt = Column(DateTime, nullable=True)
    next_attempt = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CompanyValuationSnapshot(Base):
    """公司在指定日期的 PE_TTM / 市值快照"""
    __tablename__ = "company_valuation_snapshots"
    __table_args__ = (
        UniqueConstraint("company_id", "snapshot_date", name="uq_snapshot_company_date"),
    )
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), index=True)
    snapshot_date = Column(Date, index=True)
    price_usd = Column(Float, nullable=True)     # 当日收盘价（USD）
    eps_ttm = Column(Float, nullable=True)       # TTM EPS（USD）
    pe_ttm = Column(Float, nullable=True)        # 当日 PE(TTM)
    market_cap_b = Column(Float, nullable=True)  # 市值（亿美元）
    price_currency = Column(String, nullable=True)
    fx_rate = Column(Float, nullable=True)
    source = Column(String, default="yfinance")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
