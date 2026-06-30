"""
GPU 云租赁小时价采集器 — Vantage.sh 数据源

数据源: https://instances.vantage.sh/instances.json （公开 API，AWS/EC2 实例价格）
覆盖 GPU: H100 / H200 / B200 (Blackwell) / A100 / L40S / L4 / A10

为什么选 Vantage.sh:
- 完全公开 JSON API（无需 token / 登录）
- 每日更新
- 涵盖所有 GPU 系列 + 按 GPU 数量和地区
- 比各厂商自家定价页稳定（Lambda/Coreweave 大多 client-side 渲染难爬）

单位约定：
- AWS实例价都是 USD/小时/整实例
- 转换为 USD/GPU/小时 = 实例价 ÷ GPU 数量
- Indicator.value 存 USD per GPU per hour

频率：cron 每天 1-2 次足够（AWS 价格很少日内变）
"""
import json
import logging
import urllib.request
from datetime import date, datetime, timezone

from industry_collector.base import BaseCollector

logger = logging.getLogger(__name__)

VANTAGE_INSTANCES_URL = "https://instances.vantage.sh/instances.json"
USER_AGENT = "Mozilla/5.0"


class _VantageGPUBase(BaseCollector):
    """Vantage.sh GPU 价格采集的基类。

    每种 GPU 选代表性 SKU（最常见的 GPU 数量）：
    - 单卡版（如 p5.4xlarge = 1x H100）—— 个人开发者 / 小团队
    - 8 卡满配（如 p5.48xlarge = 8x H100）—— 大模型训练主力

    存两个数：per GPU hour 和 full instance hour
    """
    source = "vantage_gpu_price"
    unit = "USD/(GPU·hour)"
    category = "gpu_cloud"
    category_cn = "GPU 算力"
    update_frequency = "daily"
    description = ""
    source_url = VANTAGE_INSTANCES_URL
    collection_method = "Vantage.sh 公开 JSON API（AWS 实例价）"
    gpu_name = ""           # 子类覆盖: "H100", "B200", ...
    instance_type = ""      # 子类覆盖: "p5.4xlarge" (1 GPU) 等
    gpu_count = 1           # 子类覆盖
    db = None               # collect 时由 base.refresh_company_data 等设置

    def _fetch_vantage_data(self) -> list[dict]:
        """拉取 Vantage.sh 完整 instance 列表。"""
        req = urllib.request.Request(VANTAGE_INSTANCES_URL, headers={"User-Agent": USER_AGENT})
        try:
            data = json.loads(urllib.request.urlopen(req, timeout=60).read())
        except Exception as e:
            logger.warning(f"Vantage.sh fetch failed: {e}")
            return []
        return data

    def _extract_target_price(self, data: list[dict]) -> tuple[float, str] | None:
        """找到目标 instance 的 us-east-1 ondemand Linux 价格。"""
        for d in data:
            if d.get("instance_type") != self.instance_type:
                continue
            pricing = d.get("pricing", {}).get("us-east-1", {})
            linux = pricing.get("linux", {})
            ondemand = linux.get("ondemand")
            if ondemand is not None:
                try:
                    return float(ondemand), d.get("GPU_model", self.gpu_name)
                except (TypeError, ValueError):
                    pass
        return None

    def _save_price(self, value: float) -> dict:
        """写 DB。value 是实例 $/hour；存的是 per-GPU $/hour。"""
        per_gpu = round(value / self.gpu_count, 4) if self.gpu_count else value
        target_date = date.today().isoformat()

        if not self.db:
            return {"success": True, "value": per_gpu, "unit": self.unit,
                    "instance_per_hr": value, "instance_type": self.instance_type,
                    "gpu_count": self.gpu_count, "date": target_date}

        ind = self._get_or_create_indicator(self.db)
        # note 存原始 instance price（用于交叉验证）
        note = (f"AWS {self.instance_type} ({self.gpu_count}x {self.gpu_name}) us-east-1 "
                f"on-demand Linux ${value}/hr → ${per_gpu}/(GPU·hr). Source: vantage.sh")
        return self._write_observation(
            self.db, ind.id, per_gpu,
            target_date=target_date,
            note=note,
            data_quality="confirmed",
        )


# === H100 ===

class H100SingleGPUPriceCollector(_VantageGPUBase):
    """AWS p5.4xlarge — 1x NVIDIA H100 单卡 ondemand 价格。"""
    indicator_name = "h100_gpu_hourly_price"
    indicator_name_cn = "H100 单卡 云租赁小时价"
    gpu_name = "H100"
    instance_type = "p5.4xlarge"
    gpu_count = 1
    description = "AWS p5.4xlarge on-demand Linux USD/GPU/h（最常见 H100 单元配置）"

    async def collect(self, db=None) -> dict:
        self.db = db
        data = self._fetch_vantage_data()
        result = self._extract_target_price(data)
        if not result:
            return {"success": False, "error": "no_data",
                    "source": self.source, "indicator": self.indicator_name}
        price, gpu_model = result
        return self._save_price(price)


class H100EightGPUPriceCollector(_VantageGPUBase):
    """AWS p5.48xlarge — 8x NVIDIA H100 满配（典型大模型训练配置）。"""
    indicator_name = "h100_8gpu_hourly_price"
    indicator_name_cn = "H100 8卡 满配小时价"
    gpu_name = "H100"
    instance_type = "p5.48xlarge"
    gpu_count = 8
    description = "AWS p5.48xlarge 8×H100 on-demand (典型大模型训练配置)"

    async def collect(self, db=None) -> dict:
        self.db = db
        data = self._fetch_vantage_data()
        result = self._extract_target_price(data)
        if not result:
            return {"success": False, "error": "no_data",
                    "source": self.source, "indicator": self.indicator_name}
        price, gpu_model = result
        return self._save_price(price)


# === H200 ===

class H200EightGPUPriceCollector(_VantageGPUBase):
    """AWS p5en.48xlarge — 8x NVIDIA H200。"""
    indicator_name = "h200_8gpu_hourly_price"
    indicator_name_cn = "H200 8卡 满配小时价"
    gpu_name = "H200"
    instance_type = "p5en.48xlarge"
    gpu_count = 8
    description = "AWS p5en.48xlarge 8×H200 on-demand（H100 升级版）"

    async def collect(self, db=None) -> dict:
        self.db = db
        data = self._fetch_vantage_data()
        result = self._extract_target_price(data)
        if not result:
            return {"success": False, "error": "no_data",
                    "source": self.source, "indicator": self.indicator_name}
        price, gpu_model = result
        return self._save_price(price)


# === B200 (Blackwell) ===

class B200EightGPUPriceCollector(_VantageGPUBase):
    """AWS p6-b200.48xlarge — 8x NVIDIA Blackwell B200。

    用户优先级最高的信号："Blackwell 服务器价格"。
    """
    indicator_name = "b200_8gpu_hourly_price"
    indicator_name_cn = "Blackwell B200 8卡 满配小时价"
    gpu_name = "B200"
    instance_type = "p6-b200.48xlarge"
    gpu_count = 8
    description = "AWS p6-b200.48xlarge 8×B200 on-demand（NVIDIA 最新 Blackwell 旗舰）"

    async def collect(self, db=None) -> dict:
        self.db = db
        data = self._fetch_vantage_data()
        result = self._extract_target_price(data)
        if not result:
            return {"success": False, "error": "no_data",
                    "source": self.source, "indicator": self.indicator_name}
        price, gpu_model = result
        return self._save_price(price)


# === A100 ===

class A100EightGPUPriceCollector(_VantageGPUBase):
    """AWS p4d.24xlarge — 8x NVIDIA A100 老款价格（基线参考）。"""
    indicator_name = "a100_8gpu_hourly_price"
    indicator_name_cn = "A100 8卡 满配小时价"
    gpu_name = "A100"
    instance_type = "p4d.24xlarge"
    gpu_count = 8
    description = "AWS p4d.24xlarge 8×A100 on-demand（早期 AI 训练基线价格）"

    async def collect(self, db=None) -> dict:
        self.db = db
        data = self._fetch_vantage_data()
        result = self._extract_target_price(data)
        if not result:
            return {"success": False, "error": "no_data",
                    "source": self.source, "indicator": self.indicator_name}
        price, gpu_model = result
        return self._save_price(price)
