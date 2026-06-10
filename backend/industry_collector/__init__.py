"""
产业数据采集器 — 统一入口 + 调度器
按数据源组织的采集器集合，每个采集器独立文件。
"""

from .base import BaseCollector
from .sources.tsmc_ir import TSMCMonthlyRevenueCollector, TSMCCoWoSCollector
from .sources.trendforce import TrendForceCollector
from .sources.wsts_sia import WSTSSIACollector
from .sources.semi_org import SEMICollector, SEMIWaferCollector
from .sources.asml_ir import ASMLCollector
from .sources.nvidia_ir import NVIDIAIRCollector
from .sources.china_customs import ChinaCustomsICImportCollector, ChinaCustomsICExportCollector
from .sources.hyperscaler_capex import (
    HyperscalerAmazonCapExCollector, HyperscalerMicrosoftCapExCollector,
    HyperscalerGoogleCapExCollector, HyperscalerMetaCapExCollector,
)
from .sources.gpu_cloud import GPUCloudPriceCollector
from .sources.synopsys_cadence import SynopsysBacklogCollector, CadenceBacklogCollector
from .sources.distributor_data import ArrowRevenueCollector, AvnetRevenueCollector, WPGRevenueCollector
from .sources.osat_data import OSATCoWoSCollector, OSATCapExCollector, ASERevenueCollector
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
    "hyperscaler_capex": [HyperscalerAmazonCapExCollector, HyperscalerMicrosoftCapExCollector, HyperscalerGoogleCapExCollector, HyperscalerMetaCapExCollector],
    "gpu_cloud": [GPUCloudPriceCollector],
    "synopsys_cadence": [SynopsysBacklogCollector, CadenceBacklogCollector],
    "distributor_data": [ArrowRevenueCollector, AvnetRevenueCollector, WPGRevenueCollector],
    "osat_data": [OSATCoWoSCollector, OSATCapExCollector, ASERevenueCollector],
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
