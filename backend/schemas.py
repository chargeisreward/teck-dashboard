from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional


# ---------- Original ─────────────────────────────────────────────

class CompanyBase(BaseModel):
    name: str
    name_cn: Optional[str] = None
    ticker: Optional[str] = None
    sector: str
    description: Optional[str] = None
    logo_url: Optional[str] = None
    is_listed: bool = True
    company_type: Optional[str] = None
    revenue_2024: Optional[float] = None
    employee_count: Optional[int] = None

class CompanyCreate(CompanyBase): pass

class CompanyOut(CompanyBase):
    id: int
    revenue_2025: Optional[float] = None
    model_config = {"from_attributes": True}

class ProductBase(BaseModel):
    name: str
    category: str
    architecture: Optional[str] = None
    release_date: Optional[date] = None
    description: Optional[str] = None

class ProductCreate(ProductBase):
    company_id: int

class ProductMetricOut(BaseModel):
    id: int; metric_name: str; metric_value: float; unit: str
    model_config = {"from_attributes": True}

class ProductOut(ProductBase):
    id: int; company_id: int; metrics: list[ProductMetricOut] = []
    model_config = {"from_attributes": True}

class MarketDataBase(BaseModel):
    date: date; stock_price: Optional[float] = None
    market_cap: Optional[float] = None; volume: Optional[float] = None

class MarketDataCreate(MarketDataBase):
    company_id: int

class MarketDataOut(MarketDataBase):
    id: int; company_id: int
    model_config = {"from_attributes": True}

class StorageProductBase(BaseModel):
    name: str; storage_type: str; capacity: Optional[str] = None
    read_speed: Optional[float] = None; write_speed: Optional[float] = None
    price: Optional[float] = None; description: Optional[str] = None

class StorageProductOut(StorageProductBase):
    id: int; company_id: int
    model_config = {"from_attributes": True}

class CompanyDetail(CompanyOut):
    products: list[ProductOut] = []
    market_data: list[MarketDataOut] = []

class DashboardSummary(BaseModel):
    total_companies: int; total_products: int; total_storage_products: int
    latest_market_caps: list[dict]; product_categories: list[dict]


# ---------- 产业链环节 ─────────────────────────────────────────

class IndustryChainLinkOut(BaseModel):
    id: int; name: str; name_cn: Optional[str] = None
    description: Optional[str] = None
    market_size_2025: Optional[float] = None; market_size_2026: Optional[float] = None; market_size_2027: Optional[float] = None
    growth_rate: Optional[float] = None; entry_barriers: Optional[str] = None
    expansion_difficulty: Optional[str] = None
    supply_gap_2025: Optional[str] = None; supply_gap_2026: Optional[str] = None; supply_gap_2027: Optional[str] = None
    key_drivers: Optional[str] = None; risks: Optional[str] = None
    sort_order: Optional[int] = 0
    data_source: Optional[str] = None
    last_verified: Optional[date] = None
    model_config = {"from_attributes": True}

class CompanyChainLinkOut(BaseModel):
    id: int; company_id: int; chain_link_id: int
    market_share: Optional[float] = None; revenue_share: Optional[float] = None
    is_leader: bool = False; competitive_advantage: Optional[str] = None
    notes: Optional[str] = None
    data_source: Optional[str] = None
    last_verified: Optional[date] = None
    company: Optional[CompanyOut] = None
    chain_link: Optional[IndustryChainLinkOut] = None
    model_config = {"from_attributes": True}

class ChainLinkDetail(IndustryChainLinkOut):
    companies: list[CompanyChainLinkOut] = []


# ---------- 财务与估值 ─────────────────────────────────────────

class FinancialOut(BaseModel):
    id: int; company_id: int; fiscal_year: int
    revenue: Optional[float] = None; revenue_growth: Optional[float] = None
    net_income: Optional[float] = None; gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None; net_margin: Optional[float] = None
    eps: Optional[float] = None; pe: Optional[float] = None
    pb: Optional[float] = None; ps: Optional[float] = None
    ev_ebitda: Optional[float] = None; roe: Optional[float] = None
    debt_equity: Optional[float] = None; dividend_yield: Optional[float] = None
    pe_ttm: Optional[float] = None; ps_ttm: Optional[float] = None
    data_source: Optional[str] = None
    last_verified: Optional[date] = None
    model_config = {"from_attributes": True}


# ---------- 供需分析 ───────────────────────────────────────────

class SupplyDemandOut(BaseModel):
    id: int; chain_link_id: int; period: str
    supply: Optional[float] = None; demand: Optional[float] = None
    unit: Optional[str] = None; gap_pct: Optional[float] = None
    gap_description: Optional[str] = None
    capacity_utilization: Optional[float] = None
    lead_time_weeks: Optional[int] = None
    model_config = {"from_attributes": True}


# ---------- 关键指标 ───────────────────────────────────────────

class KeyIndicatorOut(BaseModel):
    id: int; name: str; name_cn: Optional[str] = None
    unit: Optional[str] = None; source: Optional[str] = None
    source_url: Optional[str] = None; category: Optional[str] = None
    description: Optional[str] = None; impact_analysis: Optional[str] = None
    is_automated: bool = False; update_frequency: Optional[str] = None
    collection_method: Optional[str] = None
    model_config = {"from_attributes": True}

class IndicatorObservationOut(BaseModel):
    id: int; indicator_id: int; date: date; value: float
    previous_value: Optional[float] = None; change_pct: Optional[float] = None
    note: Optional[str] = None; data_quality: Optional[str] = None
    marginal_change_pct: Optional[float] = None
    comparison_window: Optional[str] = None
    industry_impact: Optional[str] = None
    chain_impact: Optional[str] = None
    company_impact: Optional[str] = None
    model_config = {"from_attributes": True}

class IndicatorDetail(KeyIndicatorOut):
    observations: list[IndicatorObservationOut] = []


# ---------- 预测 ───────────────────────────────────────────────

class ForecastOut(BaseModel):
    id: int; company_id: int; target_year: int
    revenue_est: Optional[float] = None; revenue_growth_est: Optional[float] = None
    pe_est: Optional[float] = None; ps_est: Optional[float] = None
    market_cap_est: Optional[float] = None
    supply_balance_note: Optional[str] = None; confidence: Optional[str] = None
    analyst_consensus: Optional[str] = None; key_assumptions: Optional[str] = None
    upside_risks: Optional[str] = None; downside_risks: Optional[str] = None
    model_config = {"from_attributes": True}


# ---------- 判断日志 ───────────────────────────────────────────

class JudgmentLogOut(BaseModel):
    id: int; date: date; title: str
    description: Optional[str] = None; previous_view: Optional[str] = None
    new_view: Optional[str] = None; impact_level: Optional[str] = None
    related_companies: Optional[str] = None; related_indicators: Optional[str] = None
    evidence: Optional[str] = None; action_taken: Optional[str] = None
    model_config = {"from_attributes": True}

class JudgmentLogCreate(BaseModel):
    date: date; title: str; description: Optional[str] = None
    previous_view: Optional[str] = None; new_view: Optional[str] = None
    impact_level: Optional[str] = None; related_companies: Optional[str] = None
    related_indicators: Optional[str] = None; evidence: Optional[str] = None
    action_taken: Optional[str] = None


# ---------- 时间线事件 ──────────────────────────────────────────

class TimelineEventOut(BaseModel):
    id: int
    event_type: str                                          # "judgment" | "collection"
    event_time: datetime
    title: str
    description: Optional[str] = None
    impact_level: Optional[str] = None
    related_tickers: Optional[str] = None
    related_indicators: Optional[str] = None
    pre_event_returns: Optional[dict] = None
    post_event_returns: Optional[dict] = None
    post_event_updated: bool = False
    judgment_log_id: Optional[int] = None
    indicator_observation_id: Optional[int] = None
    source_name: Optional[str] = None
    indicator_name_cn: Optional[str] = None
    value_display: Optional[str] = None
    model_config = {"from_attributes": True}


# ---------- 评分系统 ───────────────────────────────────────────

class ScoringDimensionOut(BaseModel):
    id: int; name: str; name_cn: Optional[str] = None
    weight: float; description: Optional[str] = None
    is_active: bool = True; min_score: float = 0; max_score: float = 100
    model_config = {"from_attributes": True}

class CompanyScoreOut(BaseModel):
    id: int; company_id: int; dimension_id: int
    score: float; reason: Optional[str] = None; date_updated: Optional[date] = None
    dimension: Optional[ScoringDimensionOut] = None
    model_config = {"from_attributes": True}

class CompanyScoreSummary(BaseModel):
    company_id: int; company_name: str; name_cn: Optional[str] = None; ticker: Optional[str] = None
    company_type: Optional[str] = None; is_listed: bool = True
    total_score: float; dimension_scores: list[dict]


# ---------- 投资组合 ───────────────────────────────────────────

class PortfolioOut(BaseModel):
    id: int; name: str; description: Optional[str] = None
    created_date: date; initial_capital: float = 1000000.0
    rebalance_frequency: str = "monthly"; is_active: bool = True
    strategy_notes: Optional[str] = None
    model_config = {"from_attributes": True}

class PortfolioHoldingOut(BaseModel):
    id: int; portfolio_id: int; company_id: int
    weight: float; actual_weight: Optional[float] = None
    shares: Optional[float] = None; avg_cost: Optional[float] = None
    current_price: Optional[float] = None; market_value: Optional[float] = None
    return_pct: Optional[float] = None; allocation_reason: Optional[str] = None
    date_added: Optional[date] = None
    company: Optional[CompanyOut] = None
    model_config = {"from_attributes": True}

class PortfolioPerformanceOut(BaseModel):
    id: int; portfolio_id: int; date: date
    total_value: float; cash: float = 0
    daily_return: Optional[float] = None; cumulative_return: Optional[float] = None
    benchmark_return: Optional[float] = None; alpha: Optional[float] = None
    sharpe_ratio: Optional[float] = None; max_drawdown: Optional[float] = None
    notes: Optional[str] = None
    model_config = {"from_attributes": True}

class PortfolioEvaluationOut(BaseModel):
    id: int; portfolio_id: int; date: date
    summary: Optional[str] = None; adjustment_suggestion: Optional[str] = None
    suggested_changes: Optional[dict] = None; risk_warnings: Optional[str] = None
    conviction_changes: Optional[str] = None; is_actionable: bool = False
    created_by: str = "system"
    model_config = {"from_attributes": True}

class PortfolioDetail(PortfolioOut):
    holdings: list[PortfolioHoldingOut] = []
    performances: list[PortfolioPerformanceOut] = []
    evaluations: list[PortfolioEvaluationOut] = []


# ---------- 组合跟踪 ───────────────────────────────────────────

class HoldingTrackingData(BaseModel):
    """单个持仓的实时跟踪数据"""
    holding_id: int
    company_id: int
    ticker: str
    company_name: str
    name_cn: Optional[str] = None
    weight: float               # 当前目标权重
    current_price: Optional[float] = None
    change_pct: Optional[float] = None
    pe_ttm: Optional[float] = None
    market_cap_b: Optional[float] = None

    # 期间涨跌幅
    return_1d: Optional[float] = None
    return_1w: Optional[float] = None
    return_1m: Optional[float] = None
    return_3m: Optional[float] = None
    return_6m: Optional[float] = None
    return_1y: Optional[float] = None
    return_3y: Optional[float] = None

    # EPS & 前瞻 PE
    eps_ttm: Optional[float] = None
    eps_2025: Optional[float] = None
    growth_rate: Optional[float] = None
    eps_2026e: Optional[float] = None
    eps_2027e: Optional[float] = None
    forward_pe_2026e: Optional[float] = None
    forward_pe_2027e: Optional[float] = None


class PortfolioTrackingData(BaseModel):
    """组合级汇总跟踪数据"""
    portfolio_id: int
    portfolio_name: str
    last_updated: Optional[str] = None

    # 权重
    total_weight: float
    cash_weight: float

    # 组合加权指标
    weighted_pe: Optional[float] = None
    weighted_eps_ttm: Optional[float] = None
    weighted_eps_2026e: Optional[float] = None
    weighted_eps_2027e: Optional[float] = None
    weighted_forward_pe_2026e: Optional[float] = None
    weighted_forward_pe_2027e: Optional[float] = None

    # 组合期间加权涨跌幅
    weighted_return_1d: Optional[float] = None
    weighted_return_1w: Optional[float] = None
    weighted_return_1m: Optional[float] = None
    weighted_return_3m: Optional[float] = None
    weighted_return_6m: Optional[float] = None
    weighted_return_1y: Optional[float] = None
    weighted_return_3y: Optional[float] = None

    # 持仓明细
    holdings: list[HoldingTrackingData] = []


class WeightUpdateRequest(BaseModel):
    """权重更新请求"""
    weight: float


# ---------- 估值模型 ─────────────────────────────────────────────

class ValuationParams(BaseModel):
    peer_group: str = "memory"                        # 同群组
    revenue_growth: float = 20.0                      # 营收增长率(%)
    net_margin: Optional[float] = None                # 净利率(%), 默认使用当前值
    discount_rate: float = 10.0                       # 折现率(%)
    terminal_growth: float = 3.0                      # 永续增长率(%)
    growth_years: int = 5                             # 高增长年数
    china_premium: float = 0.0                        # 国产替代溢价(%)


class PeerGroupDef(BaseModel):
    name: str
    name_cn: str
    description: str
    company_ids: list[int]


class ValuationCompanyData(BaseModel):
    id: int
    name: str
    name_cn: Optional[str] = None
    ticker: Optional[str] = None
    company_type: Optional[str] = None
    is_listed: bool = True
    revenue: Optional[float] = None
    net_income: Optional[float] = None
    net_margin: Optional[float] = None
    pe_ttm: Optional[float] = None
    ps_ttm: Optional[float] = None
    market_cap: Optional[float] = None
    revenue_growth_3y: Optional[float] = None
    employee_count: Optional[int] = None
    is_chinese: bool = False


class ValuationResultOut(BaseModel):
    company_id: int
    name: str
    name_cn: Optional[str] = None
    ticker: Optional[str] = None
    current_pe: Optional[float] = None
    current_ps: Optional[float] = None
    current_market_cap: Optional[float] = None
    assumed_growth: float = 20.0
    assumed_net_margin: Optional[float] = None
    discount_rate: float = 10.0
    terminal_growth: float = 3.0
    growth_years: int = 5
    fair_pe: Optional[float] = None
    fair_market_cap: Optional[float] = None
    upside_pct: Optional[float] = None
    implied_growth: Optional[float] = None
    is_overvalued: Optional[bool] = None
    china_premium_applied: float = 0.0
    stage1_pv: Optional[float] = None
    terminal_pv: Optional[float] = None


class PeerComparisonResultOut(BaseModel):
    peer_group: str
    peer_group_cn: str
    companies: list[ValuationResultOut]
    params: dict


class PriceDataPoint(BaseModel):
    date: str
    price: Optional[float] = None
    change_pct: Optional[float] = None
    volume: Optional[float] = None


# ---------- 估值模型 v2 — 供需感知未来 PE ────────────────────────

class ChainSupplyDemandScoreOut(BaseModel):
    """产业链环节供需量化分数"""
    chain_link_id: int
    chain_name: str
    chain_name_cn: Optional[str] = None
    gap_pct: Optional[float] = None
    capacity_utilization: Optional[float] = None
    lead_time_weeks: Optional[int] = None
    gap_score: float = 50.0
    utilization_score: float = 50.0
    lead_time_score: float = 50.0
    composite_score: float = 50.0
    supply_verdict: str = "供需平衡"
    pricing_power: str = "定价权中性"


class CompanyAdjustmentOut(BaseModel):
    """公司推荐调整参数"""
    company_id: int
    name: str
    name_cn: Optional[str] = None
    ticker: Optional[str] = None
    primary_chain: str = ""
    primary_chain_cn: Optional[str] = None
    chain_composite_score: float = 50.0
    recommended_growth: float = 15.0
    recommended_net_margin: float = 20.0
    current_growth_cagr: Optional[float] = None
    analyst_growth_est: Optional[float] = None
    current_net_margin: Optional[float] = None
    supply_verdict: str = "供需平衡"


class FuturePEValuationParams(BaseModel):
    """未来 PE 估值参数"""
    peer_group: str = "memory"
    growth_years: int = 5
    revenue_growth: Optional[float] = None    # None=系统推荐
    net_margin: Optional[float] = None        # None=系统推荐
    use_supply_demand: bool = True


class FuturePEValuationResultOut(BaseModel):
    """未来 PE 估值结果"""
    company_id: int
    name: str
    name_cn: Optional[str] = None
    ticker: Optional[str] = None
    company_type: Optional[str] = None

    current_pe: Optional[float] = None
    current_market_cap: Optional[float] = None

    # 供需背景
    chain_composite_score: float = 50.0
    supply_verdict: str = "供需平衡"
    pricing_power: str = "定价权中性"

    # 假设
    revenue_growth: float = 15.0
    net_margin: float = 20.0
    growth_years: int = 5
    is_growth_recommended: bool = True
    is_margin_recommended: bool = True

    # 未来 PE
    projected_net_income: Optional[float] = None
    future_pe: Optional[float] = None
    benchmark_pe: Optional[float] = None

    # 估值信号
    upside_pct: Optional[float] = None
    signal: str = "合理估值"

    # 分析师锚点
    analyst_pe_2026: Optional[float] = None
    analyst_pe_2027: Optional[float] = None
    analyst_consensus: Optional[str] = None

    # 增长率分解
    base_growth: Optional[float] = None
    supply_adjustment: float = 0.0


class FuturePEComparisonResultOut(BaseModel):
    """同群组未来 PE 对比结果"""
    peer_group: str
    peer_group_cn: str
    companies: list[FuturePEValuationResultOut]
    params: dict


# ---------- 用户关注（核心公司）────────────────────────────────────

class FollowOut(BaseModel):
    id: int
    company_id: int
    weight: float = 0.0
    created_at: Optional[datetime] = None
    ticker: Optional[str] = None
    name: Optional[str] = None
    name_cn: Optional[str] = None
    company_type: Optional[str] = None
    model_config = {"from_attributes": True}


class IndustryChainCard(BaseModel):
    """产业链卡片聚合数据"""
    company_type: str
    name_cn: str
    company_count: int
    avg_change_pct: Optional[float] = None
    total_revenue_ttm: Optional[float] = None
    total_net_income_ttm: Optional[float] = None
    total_market_cap: Optional[float] = None


class DashboardOverview(BaseModel):
    """市场概览页面聚合数据"""
    total_companies: int
    total_products: int
    total_storage_products: int
    industry_chains: list[IndustryChainCard]
    core_companies: list[dict]


class FollowActionResponse(BaseModel):
    success: bool
    message: str
    follow_count: int
