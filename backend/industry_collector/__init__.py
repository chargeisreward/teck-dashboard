"""
产业数据采集器 — 统一入口 + 调度器
按数据源组织的采集器集合，每个采集器独立文件。

Stub 采集器（distributor_data / hyperscaler_capex / osat_data）已在 2026-06-30
rebuild 计划中删除——这些只写 estimated 占位值，违反 "No mock/synthetic data" 原则。
替代方案：hyperscaler_capex 改为 SEC EDGAR XBRL 真实抓取（见 sec_edgar_capex.py）。
"""

from .base import BaseCollector
from .sources.tsmc_ir import TSMCMonthlyRevenueCollector, TSMCCoWoSCollector
from .sources.trendforce import TrendForceCollector
from .sources.wsts_sia import WSTSSIACollector
from .sources.semi_org import SEMICollector, SEMIWaferCollector
from .sources.asml_ir import ASMLCollector
from .sources.nvidia_ir import NVIDIAIRCollector
from .sources.china_customs import ChinaCustomsICImportCollector, ChinaCustomsICExportCollector
from .sources.sec_edgar_capex import (
    HyperscalerAmazonCapExCollector, HyperscalerMicrosoftCapExCollector,
    HyperscalerGoogleCapExCollector, HyperscalerMetaCapExCollector,
)
from .sources.vantage_gpu_price import (
    H100SingleGPUPriceCollector, H100EightGPUPriceCollector,
    H200EightGPUPriceCollector, B200EightGPUPriceCollector,
    A100EightGPUPriceCollector,
)
from .sources.synopsys_cadence import SynopsysBacklogCollector, CadenceBacklogCollector
from .sources.odm_server_data import (
    QuantaMonthlyRevenueCollector, WistronMonthlyRevenueCollector,
    InventecMonthlyRevenueCollector, PegatronMonthlyRevenueCollector,
    WiwynnMonthlyRevenueCollector,
)
from .sources.arm_ir import ARMRoyaltyCollector

# 全量采集器注册表
COLLECTORS = {
    "tsmc_ir": [TSMCMonthlyRevenueCollector, TSMCCoWoSCollector],
    "trendforce": [TrendForceCollector],
    "wsts_sia": [WSTSSIACollector],
    "semi_org": [SEMICollector, SEMIWaferCollector],
    "asml_ir": [ASMLCollector],
    "nvidia_ir": [NVIDIAIRCollector],
    "china_customs": [ChinaCustomsICImportCollector, ChinaCustomsICExportCollector],
    "sec_edgar_capex": [
        HyperscalerAmazonCapExCollector, HyperscalerMicrosoftCapExCollector,
        HyperscalerGoogleCapExCollector, HyperscalerMetaCapExCollector,
    ],
    "vantage_gpu_price": [
        H100SingleGPUPriceCollector, H100EightGPUPriceCollector,
        H200EightGPUPriceCollector, B200EightGPUPriceCollector,
        A100EightGPUPriceCollector,
    ],
    "synopsys_cadence": [SynopsysBacklogCollector, CadenceBacklogCollector],
    "odm_server": [QuantaMonthlyRevenueCollector, WistronMonthlyRevenueCollector,
                   InventecMonthlyRevenueCollector, PegatronMonthlyRevenueCollector,
                   WiwynnMonthlyRevenueCollector],
    "arm_ir": [ARMRoyaltyCollector],
}


def get_collectors(source: str = None):
    """获取采集器实例，可按数据源筛选"""
    if source:
        collector_classes = COLLECTORS.get(source, [])
        return [cls() for cls in collector_classes]

    instances = []
    for source_name, classes in COLLECTORS.items():
        for cls in classes:
            instances.append(cls())
    return instances


async def collect_all(source: str = None, db=None):
    """运行全部（或指定）采集器"""
    results = {"success": [], "errors": []}
    collectors = get_collectors(source)
    for collector in collectors:
        try:
            result = await collector.collect(db=db)
            results["success"].append({
                "source": collector.source,
                "indicator": collector.indicator_name,
                "result": result,
            })
        except Exception as e:
            results["errors"].append({
                "source": collector.source,
                "indicator": collector.indicator_name,
                "error": str(e),
            })
    return results
