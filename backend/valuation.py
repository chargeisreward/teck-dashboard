"""
Gordon Growth 估值模型引擎

Two-stage DCF:
  第1阶段（高增长期 N 年）：按增长率和利润率假设逐年计算自由现金流
  第2阶段（永续期）：terminal multiple approach

核心计算：
  - Fair PE / Fair PS / Fair Value
  - Implied Growth Rate (breakeven) — 数值求解
  - 相对价值比较（同群组内 pairwise breakeven）
  - 中国公司国产替代溢价调整

参数可配置:
  - revenue_growth: 第1阶段年化营收增长率 (%)
  - net_margin:     稳态净利润率 (%)
  - discount_rate:  折现率 / WACC (%)
  - terminal_growth: 永续增长率 (%)
  - growth_years:   第1阶段持续年数
  - china_premium:  中国公司因国产替代的溢价调整 (% 加在growth上)
"""
from dataclasses import dataclass
from typing import Optional


# ── 结果容器 ─────────────────────────────────────────────────────

@dataclass
class CompanyValuationInput:
    """单家公司的估值输入"""
    company_id: int
    name: str
    name_cn: Optional[str] = None
    ticker: Optional[str] = None
    company_type: Optional[str] = None
    is_listed: bool = True

    # 最新财年数据
    revenue: Optional[float] = None           # 营收(亿美元)
    net_income: Optional[float] = None         # 净利润(亿美元)
    net_margin: Optional[float] = None         # 净利率(%)
    pe_ttm: Optional[float] = None             # PE(TTM)
    ps_ttm: Optional[float] = None             # PS(TTM)
    market_cap: Optional[float] = None         # 市值(亿美元)
    employee_count: Optional[int] = None

    # 产业链参数
    is_chinese: bool = False                   # 是否中国大陆公司
    moat_level: int = 2                        # 壁垒强度 1低/2中/3高
    market_growth: Optional[float] = None      # 所在环节市场增长率(%)


@dataclass
class ValuationResult:
    """估值计算结果"""
    company_id: int
    name: str
    name_cn: Optional[str] = None
    ticker: Optional[str] = None

    # 当前估值
    current_pe: Optional[float] = None
    current_ps: Optional[float] = None
    current_market_cap: Optional[float] = None

    # 假设参数
    assumed_growth: float = 20.0               # 营收增长率假设(%)
    assumed_net_margin: Optional[float] = None # 净利率假设(%)
    discount_rate: float = 10.0                # 折现率(%)
    terminal_growth: float = 3.0               # 永续增长率(%)
    growth_years: int = 5                      # 高增长年数

    # 计算结果
    fair_pe: Optional[float] = None            # 公允PE
    fair_market_cap: Optional[float] = None    # 公允市值(亿美元)
    upside_pct: Optional[float] = None         # 上涨空间(%)
    implied_growth: Optional[float] = None     # 隐含增长率(breakeven, %)
    is_overvalued: Optional[bool] = None       # 是否高估

    # 风险调整
    china_premium_applied: float = 0.0         # 国产替代溢价(%)

    # 详细阶段现金流
    stage1_pv: Optional[float] = None          # 第1阶段现值
    terminal_pv: Optional[float] = None        # 永续期现值


@dataclass
class PeerComparisonResult:
    """同群组对比结果"""
    peer_group: str
    peer_group_cn: str
    companies: list[ValuationResult]
    params: dict       # 使用的参数


# ── 估值模型 ─────────────────────────────────────────────────────

class GordonGrowthModel:
    """Gordon Growth 两阶段估值模型"""

    def __init__(self,
                 discount_rate: float = 10.0,
                 terminal_growth: float = 3.0,
                 growth_years: int = 5,
                 china_premium: float = 0.0):
        """
        Args:
            discount_rate: 折现率(%)
            terminal_growth: 永续增长率(%)
            growth_years: 高增长持续年数
            china_premium: 中国公司国产替代溢价(%)
        """
        self.discount_rate = discount_rate
        self.terminal_growth = terminal_growth
        self.growth_years = growth_years
        self.china_premium = china_premium

    def calculate(self,
                  input_data: CompanyValuationInput,
                  revenue_growth: Optional[float] = None,
                  net_margin: Optional[float] = None,
                  ) -> ValuationResult:
        """
        对一家公司执行两阶段估值。

        Args:
            input_data: 公司输入数据
            revenue_growth: 营收增长率(%), 默认使用input数据推断
            net_margin: 净利率(%), 默认使用input数据

        Returns:
            ValuationResult
        """
        r = self.discount_rate / 100.0
        g_term = self.terminal_growth / 100.0
        n_years = self.growth_years

        # 确定增长率
        g = revenue_growth
        if g is None:
            # 从市场增长率推断
            g = input_data.market_growth or 15.0
        g = g / 100.0

        # 中国公司溢价调整
        china_adj = 0.0
        if input_data.is_chinese and self.china_premium > 0:
            china_adj = self.china_premium / 100.0
            g = g + china_adj

        # 确定净利率
        nm = net_margin
        if nm is None:
            nm = input_data.net_margin or 20.0
        nm = nm / 100.0

        rev = input_data.revenue or 0
        ni = input_data.net_income or (rev * nm)

        result = ValuationResult(
            company_id=input_data.company_id,
            name=input_data.name,
            name_cn=input_data.name_cn,
            ticker=input_data.ticker,
            current_pe=input_data.pe_ttm,
            current_ps=input_data.ps_ttm,
            current_market_cap=input_data.market_cap,
            assumed_growth=round(g * 100 + china_adj * 100, 1),
            assumed_net_margin=round(nm * 100, 1),
            discount_rate=self.discount_rate,
            terminal_growth=self.terminal_growth,
            growth_years=n_years,
            china_premium_applied=round(china_adj * 100, 1),
        )

        if rev <= 0 or nm <= 0:
            return result

        # ── 第1阶段: 逐年计算净利润现值 ──
        stage1_pv = 0.0
        for year in range(1, n_years + 1):
            rev_t = rev * (1 + g) ** year
            ni_t = rev_t * nm
            pv = ni_t / (1 + r) ** year
            stage1_pv += pv

        # ── 第2阶段: 永续价值 ──
        rev_n = rev * (1 + g) ** n_years
        ni_n = rev_n * nm
        terminal_value = ni_n * (1 + g_term) / (r - g_term)
        terminal_pv = terminal_value / (1 + r) ** n_years

        fair_value = stage1_pv + terminal_pv

        result.stage1_pv = round(stage1_pv, 1)
        result.terminal_pv = round(terminal_pv, 1)

        # 公允PE: 公司价值 / 当前净利润
        current_ni = input_data.net_income or (rev * nm)
        if current_ni > 0:
            result.fair_pe = round(fair_value / current_ni, 1)

        # 公允市值（亿美元）
        result.fair_market_cap = round(fair_value, 1)

        # 上涨空间
        current_mc = input_data.market_cap
        if current_mc and current_mc > 0:
            result.upside_pct = round((fair_value / current_mc - 1) * 100, 1)
            result.is_overvalued = result.upside_pct < 0

        # 隐含增长率(breakeven): 数值求解
        if current_mc and current_mc > 0:
            implied_g = self._solve_implied_growth(
                rev=rev, nm=nm, current_mc=current_mc,
                r=r, g_term=g_term, n_years=n_years,
                china_adj=china_adj,
            )
            if implied_g is not None:
                result.implied_growth = round(implied_g * 100, 1)

        return result

    def _solve_implied_growth(self, rev: float, nm: float,
                               current_mc: float,
                               r: float, g_term: float,
                               n_years: int,
                               china_adj: float = 0.0) -> Optional[float]:
        """
        数值求解隐含增长率 (二分法)
        找到使 fair_value == current_mc 的增长率 g
        """
        lo, hi = -0.1, 1.0  # -10% ~ 100%

        for _ in range(50):  # 50次迭代足够
            mid = (lo + hi) / 2
            g = mid + china_adj

            pv = 0.0
            for year in range(1, n_years + 1):
                rev_t = rev * (1 + g) ** year
                ni_t = rev_t * nm
                pv += ni_t / (1 + r) ** year

            rev_n = rev * (1 + g) ** n_years
            ni_n = rev_n * nm
            tv = ni_n * (1 + g_term) / (r - g_term) if r > g_term else 0
            pv += tv / (1 + r) ** n_years

            diff = pv - current_mc
            if abs(diff) < 0.01:
                return mid
            if diff > 0:
                hi = mid
            else:
                lo = mid

        return round((lo + hi) / 2, 4)

    def compare_peers(self, peer_group: str, peer_group_cn: str,
                      companies: list[CompanyValuationInput],
                      revenue_growth: float = 20.0,
                      net_margin: Optional[float] = None,
                      ) -> PeerComparisonResult:
        """
        对同群组所有公司执行一致参数下的估值比较

        Args:
            peer_group: 群组英文名
            peer_group_cn: 群组中文名
            companies: 群组内公司列表
            revenue_growth: 统一营收增长率(%)
            net_margin: 统一净利率(%)

        Returns:
            PeerComparisonResult
        """
        results = []
        for c in companies:
            result = self.calculate(
                input_data=c,
                revenue_growth=revenue_growth,
                net_margin=net_margin or c.net_margin,
            )
            results.append(result)

        results.sort(key=lambda x: (x.upside_pct or 0), reverse=True)

        return PeerComparisonResult(
            peer_group=peer_group,
            peer_group_cn=peer_group_cn,
            companies=results,
            params={
                "revenue_growth": revenue_growth,
                "net_margin": net_margin,
                "discount_rate": self.discount_rate,
                "terminal_growth": self.terminal_growth,
                "growth_years": self.growth_years,
                "china_premium": self.china_premium,
            },
        )

    @staticmethod
    def compute_breakeven_matrix(results: list[ValuationResult]) -> dict:
        """
        计算成对breakeven: 公司A需要多少增长率才能达到公司B的估值水平
        返回 { (a_name, b_name): growth_needed, ... }
        """
        pairs = {}
        for a in results:
            for b in results:
                if a.company_id >= b.company_id:
                    continue
                key = f"{a.ticker or a.name} vs {b.ticker or b.name}"
                if a.implied_growth is not None and b.implied_growth is not None:
                    pairs[key] = {
                        "a": a.ticker or a.name,
                        "b": b.ticker or b.name,
                        "a_implied_growth": a.implied_growth,
                        "b_implied_growth": b.implied_growth,
                        "gap": round(a.implied_growth - b.implied_growth, 1),
                    }
        return pairs
