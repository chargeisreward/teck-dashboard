"""
供需感知未来 PE 估值模型引擎 (v2)

核心思路: 用「未来 PE = 当前市值 / N 年后预测净利润」替代 DCF 公允价值。
供需紧张 → 定价权强 → 增长/利润率上调 → 未来PE越低 → 越低估
供需宽松 → 定价权弱 → 增长/利润率下调 → 未来PE越高 → 越高估

模块组成:
  1. SupplyDemandAnalyzer — 量化供应链供需，产出 0-100 综合分数
  2. FuturePEModel — 基于调整后的增长/利润率计算未来 PE 与估值信号
"""
import logging
from dataclasses import dataclass
from statistics import median
from typing import Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# 1. 供需分析器
# ═══════════════════════════════════════════════════════════════

@dataclass
class ChainSupplyDemandScore:
    """单个产业链环节的供需量化分数"""
    chain_link_id: int
    chain_name: str
    chain_name_cn: Optional[str] = None

    # 原始数据
    gap_pct: Optional[float] = None
    capacity_utilization: Optional[float] = None
    lead_time_weeks: Optional[int] = None

    # 子维度分数 (0-100)
    gap_score: float = 50.0
    utilization_score: float = 50.0
    lead_time_score: float = 50.0
    composite_score: float = 50.0  # 加权总分

    # 文字判断
    supply_verdict: str = "供需平衡"       # 严重短缺 / 轻度短缺 / 供需平衡 / 供应过剩
    pricing_power: str = "定价权中性"       # 强劲定价权 / 温和定价权 / 定价权中性 / 无定价权


class SupplyDemandAnalyzer:
    """
    供需分析器: 将 gap_pct / capacity_utilization / lead_time 量化打分
    """

    # 权重配置 (可调整)
    WEIGHT_GAP = 0.40
    WEIGHT_UTIL = 0.35
    WEIGHT_LEAD = 0.25

    @staticmethod
    def _score_gap(gap_pct: Optional[float]) -> tuple[float, str, str]:
        """
        供需缺口评分: 缺口越大(越负) → 分越高 → 定价权越强
        缺口=0 → 50分(中性)
        """
        if gap_pct is None:
            return 50.0, "数据不足", "定价权中性"

        if gap_pct < 0:
            # 短缺: -10% → 30分, -20% → 60分, -33%+ → 100分
            score = min(abs(gap_pct) * 3.0, 100.0)
        else:
            # 过剩: +10% → 70分, +20% → 40分, +33%+ → 0分
            score = max(100.0 - gap_pct * 3.0, 0.0)

        if score >= 75:
            verdict = "严重短缺"
            power = "强劲定价权"
        elif score >= 50:
            verdict = "轻度短缺"
            power = "温和定价权"
        elif score >= 25:
            verdict = "供需平衡"
            power = "定价权中性"
        else:
            verdict = "供应过剩"
            power = "无定价权"

        return round(score, 1), verdict, power

    @staticmethod
    def _score_utilization(util: Optional[float]) -> float:
        """产能利用率评分: >90% = 满产=高分, <70% = 过剩=低分"""
        if util is None:
            return 50.0
        if util >= 90:
            return min(90.0 + (util - 90) * 1.0, 100.0)
        elif util >= 70:
            return 50.0 + (util - 70) * 2.0
        else:
            return max(util * (50.0 / 70.0), 0.0)

    @staticmethod
    def _score_lead_time(weeks: Optional[int]) -> float:
        """交期评分: >24周 = 极度紧张=100, <4周 = 正常=低分"""
        if weeks is None:
            return 50.0
        if weeks >= 24:
            return 100.0
        elif weeks >= 12:
            return 60.0 + (weeks - 12) * (40.0 / 12.0)
        elif weeks >= 4:
            return 20.0 + (weeks - 4) * (40.0 / 8.0)
        else:
            return max(weeks * 5.0, 0.0)

    def analyze_chain(self, gap_pct: Optional[float] = None,
                      capacity_utilization: Optional[float] = None,
                      lead_time_weeks: Optional[int] = None) -> ChainSupplyDemandScore:
        """
        分析单个环节的供需数据，返回量化分数

        Args:
            gap_pct: 供需缺口(%)
            capacity_utilization: 产能利用率(%)
            lead_time_weeks: 交期(周)

        Returns:
            ChainSupplyDemandScore
        """
        gap_score, verdict, power = self._score_gap(gap_pct)
        util_score = self._score_utilization(capacity_utilization)
        lead_score = self._score_lead_time(lead_time_weeks)

        composite = (
            gap_score * self.WEIGHT_GAP
            + util_score * self.WEIGHT_UTIL
            + lead_score * self.WEIGHT_LEAD
        )

        # 综合判断: 用 composite 重新得出最终裁决
        if composite >= 75:
            final_verdict = "严重短缺"
            final_power = "强劲定价权"
        elif composite >= 55:
            final_verdict = "轻度短缺"
            final_power = "温和定价权"
        elif composite >= 35:
            final_verdict = "供需平衡"
            final_power = "定价权中性"
        else:
            final_verdict = "供应过剩"
            final_power = "无定价权"

        return ChainSupplyDemandScore(
            chain_link_id=0,
            chain_name="",
            chain_name_cn=None,
            gap_pct=gap_pct,
            capacity_utilization=capacity_utilization,
            lead_time_weeks=lead_time_weeks,
            gap_score=round(gap_score, 1),
            utilization_score=round(util_score, 1),
            lead_time_score=round(lead_score, 1),
            composite_score=round(composite, 1),
            supply_verdict=final_verdict,
            pricing_power=final_power,
        )

    def analyze_chain_from_db(self, chain_link, supply_demand_records: list) -> ChainSupplyDemandScore:
        """
        从 DB 对象分析链环节

        Args:
            chain_link: IndustryChainLink ORM 对象
            supply_demand_records: 该链的 SupplyDemand 记录列表

        Returns:
            ChainSupplyDemandScore
        """
        # 找最新期间的数据 (优先 2026E → 2025)
        period_priority = ["2026E", "2027E", "2025"]
        sd = None
        for p in period_priority:
            for r in supply_demand_records:
                if r.period == p:
                    sd = r
                    break
            if sd:
                break
        if not sd and supply_demand_records:
            sd = supply_demand_records[-1]

        result = self.analyze_chain(
            gap_pct=sd.gap_pct if sd else None,
            capacity_utilization=sd.capacity_utilization if sd else None,
            lead_time_weeks=sd.lead_time_weeks if sd else None,
        )
        result.chain_link_id = chain_link.id
        result.chain_name = chain_link.name
        result.chain_name_cn = chain_link.name_cn
        return result

    def aggregate_company_score(self, chain_scores: list[tuple[ChainSupplyDemandScore, float]]) -> ChainSupplyDemandScore:
        """
        按权重聚合公司所属多个链的分数

        Args:
            chain_scores: [(score, weight), ...], weight = revenue_share or market_share

        Returns:
            聚合后的 ChainSupplyDemandScore (composite_score 为加权结果)
        """
        if not chain_scores:
            return ChainSupplyDemandScore(
                chain_link_id=0, chain_name="", chain_name_cn=None,
                composite_score=50.0, supply_verdict="供需平衡", pricing_power="定价权中性",
            )

        total_weight = sum(w for _, w in chain_scores)
        if total_weight <= 0:
            total_weight = len(chain_scores)
            chain_scores = [(s, 1.0) for s, _ in chain_scores]

        weighted_gap = sum(s.gap_score * w for s, w in chain_scores) / total_weight
        weighted_util = sum(s.utilization_score * w for s, w in chain_scores) / total_weight
        weighted_lead = sum(s.lead_time_score * w for s, w in chain_scores) / total_weight
        weighted_composite = sum(s.composite_score * w for s, w in chain_scores) / total_weight

        result = ChainSupplyDemandScore(
            chain_link_id=chain_scores[0][0].chain_link_id,
            chain_name=chain_scores[0][0].chain_name,
            chain_name_cn=chain_scores[0][0].chain_name_cn,
            gap_score=round(weighted_gap, 1),
            utilization_score=round(weighted_util, 1),
            lead_time_score=round(weighted_lead, 1),
            composite_score=round(weighted_composite, 1),
        )

        if weighted_composite >= 75:
            result.supply_verdict = "严重短缺"
            result.pricing_power = "强劲定价权"
        elif weighted_composite >= 55:
            result.supply_verdict = "轻度短缺"
            result.pricing_power = "温和定价权"
        elif weighted_composite >= 35:
            result.supply_verdict = "供需平衡"
            result.pricing_power = "定价权中性"
        else:
            result.supply_verdict = "供应过剩"
            result.pricing_power = "无定价权"

        return result


# ═══════════════════════════════════════════════════════════════
# 2. 未来 PE 估值模型
# ═══════════════════════════════════════════════════════════════

@dataclass
class CompanyInput:
    """公司数据输入(从DB查询后组装)"""
    company_id: int
    name: str
    name_cn: Optional[str] = None
    ticker: Optional[str] = None
    company_type: Optional[str] = None

    # 财务数据
    revenue: Optional[float] = None         # 最新营收(亿美元)
    net_income: Optional[float] = None      # 最新净利润(亿美元)
    net_margin: Optional[float] = None      # 最新净利率(%)
    pe_ttm: Optional[float] = None          # 当前PE
    ps_ttm: Optional[float] = None          # 当前PS
    market_cap: Optional[float] = None      # 当前市值(亿美元)

    # 供给端数据
    chain_composite_score: float = 50.0     # 供需综合分数
    supply_verdict: str = "供需平衡"
    pricing_power: str = "定价权中性"

    # 增长率参考
    cagr_3y: Optional[float] = None         # 近3年营收CAGR(%)
    analyst_growth_est: Optional[float] = None  # 分析师一致预期增长率(%)
    chain_growth_rate: Optional[float] = None   # 所在链市场增长率(%)
    analyst_pe_2026: Optional[float] = None     # 分析师2026E PE
    analyst_pe_2027: Optional[float] = None     # 分析师2027E PE
    analyst_consensus: Optional[str] = None     # 分析师共识


@dataclass
class FuturePEValuationResult:
    """未来 PE 估值结果"""
    company_id: int
    name: str
    name_cn: Optional[str] = None
    ticker: Optional[str] = None
    company_type: Optional[str] = None

    # 当前指标
    current_pe: Optional[float] = None
    current_market_cap: Optional[float] = None

    # 供需背景
    chain_composite_score: float = 50.0
    supply_verdict: str = "供需平衡"
    pricing_power: str = "定价权中性"

    # 使用的假设
    recommended_growth: float = 15.0        # 推荐增长率(%)
    recommended_net_margin: float = 20.0    # 推荐净利率(%)
    user_growth: Optional[float] = None     # 用户覆盖的增长率
    user_net_margin: Optional[float] = None # 用户覆盖的净利率
    growth_years: int = 5                   # 投影年数
    is_growth_recommended: bool = True      # True=系统推荐, False=用户覆盖
    is_margin_recommended: bool = True

    # 未来 PE 计算
    projected_net_income: Optional[float] = None  # N年后预测净利润
    future_pe: Optional[float] = None             # 未来PE
    benchmark_pe: Optional[float] = None          # 同群组基准PE

    # 估值信号
    upside_pct: Optional[float] = None       # (基准PE/未来PE - 1) * 100
    signal: str = "合理估值"                  # 低估 / 合理估值 / 高估

    # 分析师锚点
    analyst_pe_2026: Optional[float] = None
    analyst_pe_2027: Optional[float] = None
    analyst_consensus: Optional[str] = None

    # 增长率分解
    base_growth: Optional[float] = None      # 基础增长率
    supply_adjustment: float = 0.0           # 供需调整量


@dataclass
class FuturePEComparisonResult:
    """同群组未来 PE 对比"""
    peer_group: str
    peer_group_cn: str
    companies: list[FuturePEValuationResult]
    params: dict


class FuturePEModel:
    """
    未来 PE 估值模型

    核心逻辑:
      1. 自动推荐增长率(分析师→CAGR→链级增长率)
      2. 供需分数调整增长率
      3. 计算 N 年后净利润 → 未来PE
      4. 与基准PE比较 → 估值信号
    """

    # 供需调整系数
    SUPPLY_BOOST_HIGH = 1.25    # composite >= 75
    SUPPLY_BOOST_MED = 1.10     # composite >= 55
    SUPPLY_BOOST_NONE = 1.0     # composite >= 35
    SUPPLY_BOOST_NEG = 0.85     # composite < 35

    # 利润率调整
    MARGIN_BOOST_HIGH = 1.10    # util >= 90
    MARGIN_BOOST_NORMAL = 1.0   # util >= 70
    MARGIN_BOOST_LOW = 0.90     # util < 70

    def __init__(self, growth_years: int = 5, use_supply_demand: bool = True):
        """
        Args:
            growth_years: 投影年数
            use_supply_demand: 是否启用供需调整
        """
        self.growth_years = growth_years
        self.use_supply_demand = use_supply_demand

    def recommend_growth(self, input_data: CompanyInput) -> tuple[float, float, float]:
        """
        推荐增长率: 分析师一致预期 > CAGR > 链级增长率 > 默认值

        Returns:
            (base_growth, supply_adjustment, final_growth)
        """
        # 1. 确定基础增长率
        if input_data.analyst_growth_est is not None and input_data.analyst_growth_est > 0:
            base = input_data.analyst_growth_est
        elif input_data.cagr_3y is not None and input_data.cagr_3y > 0:
            base = input_data.cagr_3y
        elif input_data.chain_growth_rate is not None and input_data.chain_growth_rate > 0:
            base = input_data.chain_growth_rate
        else:
            base = 15.0  # 默认

        # 2. 供需调整
        supply_adj = 0.0
        if self.use_supply_demand:
            comp = input_data.chain_composite_score
            if comp >= 75:
                supply_adj = base * (self.SUPPLY_BOOST_HIGH - 1.0)
            elif comp >= 55:
                supply_adj = base * (self.SUPPLY_BOOST_MED - 1.0)
            elif comp >= 35:
                supply_adj = 0.0
            else:
                supply_adj = base * (self.SUPPLY_BOOST_NEG - 1.0)

        final = base + supply_adj
        return round(base, 1), round(supply_adj, 1), round(final, 1)

    def recommend_net_margin(self, input_data: CompanyInput,
                             user_net_margin: Optional[float] = None) -> float:
        """推荐净利率: 当前净利率 × 产能利用率调整"""
        if user_net_margin is not None:
            return user_net_margin

        base = input_data.net_margin or 20.0

        if not self.use_supply_demand:
            return base

        # 产能利用率调整
        # 注意: util 是链级数据, 我们无法直接从 CompanyInput 拿到
        # 这里用 composite_score 近似: 高分 = 高利用率
        comp = input_data.chain_composite_score
        if comp >= 70:
            return round(base * self.MARGIN_BOOST_HIGH, 1)
        elif comp >= 40:
            return round(base * self.MARGIN_BOOST_NORMAL, 1)
        else:
            return round(base * self.MARGIN_BOOST_LOW, 1)

    def compute_benchmark_pe(self, peers: list[CompanyInput]) -> Optional[float]:
        """计算同群组基准 PE: 有 PE_TTM 数据公司的中位数"""
        pes = [p.pe_ttm for p in peers if p.pe_ttm is not None and p.pe_ttm > 0]
        if not pes:
            return None
        return round(median(pes), 1)

    def evaluate(self, input_data: CompanyInput,
                 peers: list[CompanyInput],
                 user_growth: Optional[float] = None,
                 user_net_margin: Optional[float] = None,
                 ) -> FuturePEValuationResult:
        """
        对一家公司执行未来 PE 估值

        Args:
            input_data: 公司输入数据
            peers: 同群组公司(用于基准PE)
            user_growth: 用户覆盖的增长率(可选)
            user_net_margin: 用户覆盖的净利率(可选)

        Returns:
            FuturePEValuationResult
        """
        # 1. 确定增长率
        base_growth, supply_adj, final_growth = self.recommend_growth(input_data)
        is_growth_recommended = user_growth is None
        if user_growth is not None:
            final_growth = user_growth

        # 2. 确定净利率
        final_margin = self.recommend_net_margin(input_data, user_net_margin)
        is_margin_recommended = user_net_margin is None

        # 3. 计算未来 PE
        rev = input_data.revenue or 0
        nm = input_data.net_margin or 20.0
        ni = input_data.net_income

        # 如果没有净利润, 用 revenue * net_margin 估算
        if ni is None and rev > 0:
            ni = rev * nm / 100.0

        projected_ni = None
        future_pe = None
        if ni is not None and ni > 0:
            projected_ni = ni * (1 + final_growth / 100.0) ** self.growth_years
            mc = input_data.market_cap
            if mc and mc > 0:
                future_pe = round(mc / projected_ni, 1)

        # 4. 基准 PE
        benchmark_pe = self.compute_benchmark_pe(peers)

        # 5. 估值信号
        upside = None
        signal = "合理估值"
        if future_pe is not None and benchmark_pe is not None and benchmark_pe > 0:
            upside = round((benchmark_pe / future_pe - 1) * 100, 1)
            if upside > 20:
                signal = "低估"
            elif upside > 0:
                signal = "合理估值"
            elif upside > -20:
                signal = "略微高估"
            else:
                signal = "高估"

        return FuturePEValuationResult(
            company_id=input_data.company_id,
            name=input_data.name,
            name_cn=input_data.name_cn,
            ticker=input_data.ticker,
            company_type=input_data.company_type,
            current_pe=input_data.pe_ttm,
            current_market_cap=input_data.market_cap,
            chain_composite_score=input_data.chain_composite_score,
            supply_verdict=input_data.supply_verdict,
            pricing_power=input_data.pricing_power,
            recommended_growth=round(final_growth, 1),
            recommended_net_margin=round(final_margin, 1),
            user_growth=user_growth,
            user_net_margin=user_net_margin,
            growth_years=self.growth_years,
            is_growth_recommended=is_growth_recommended,
            is_margin_recommended=is_margin_recommended,
            projected_net_income=round(projected_ni, 1) if projected_ni else None,
            future_pe=future_pe,
            benchmark_pe=benchmark_pe,
            upside_pct=upside,
            signal=signal,
            analyst_pe_2026=input_data.analyst_pe_2026,
            analyst_pe_2027=input_data.analyst_pe_2027,
            analyst_consensus=input_data.analyst_consensus,
            base_growth=round(base_growth, 1),
            supply_adjustment=round(supply_adj, 1),
        )

    def evaluate_peers(self, peer_group: str, peer_group_cn: str,
                       companies: list[CompanyInput],
                       user_growth: Optional[float] = None,
                       user_net_margin: Optional[float] = None,
                       ) -> FuturePEComparisonResult:
        """
        对同群组所有公司执行一致参数下的未来 PE 估值比较

        Args:
            peer_group: 群组英文名
            peer_group_cn: 群组中文名
            companies: 群组内公司列表
            user_growth: 用户覆盖增长率(None=使用推荐值)
            user_net_margin: 用户覆盖净利率(None=使用推荐值)

        Returns:
            FuturePEComparisonResult
        """
        results = []
        for c in companies:
            result = self.evaluate(
                input_data=c,
                peers=companies,
                user_growth=user_growth,
                user_net_margin=user_net_margin,
            )
            results.append(result)

        results.sort(key=lambda x: (x.upside_pct or 0) if x.upside_pct is not None else -999, reverse=True)

        return FuturePEComparisonResult(
            peer_group=peer_group,
            peer_group_cn=peer_group_cn,
            companies=results,
            params={
                "growth_years": self.growth_years,
                "use_supply_demand": self.use_supply_demand,
                "user_growth": user_growth,
                "user_net_margin": user_net_margin,
            },
        )
