"""
DeepSeek AI 分析生成模块
为指标边际变化生成"一句话分析"，解释变化驱动逻辑。
"""

import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

DEEPSEEK_API_KEY = "sk-9d3f81c3a330455e8851ff263daa1e40"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
API_URL = f"{DEEPSEEK_BASE_URL}/v1/chat/completions"

# 内存缓存避免同一指标同一值重复调用 DeepSeek API
_analysis_cache = {}


def generate_indicator_analysis(
    name_cn: str,
    category_cn: str,
    latest_value: float,
    previous_value: Optional[float],
    change_pct: Optional[float],
    unit: str,
    source: str,
) -> Optional[str]:
    """
    调用 DeepSeek API 生成指标边际变化的"一句话分析"。
    返回的中文文本约 50-100 字，解释边际变化的驱动逻辑与产业链含义。

    缓存策略:
    - 内存缓存 _analysis_cache: key=f"{name_cn}:{latest_value}:{change_pct}"
    - 调用方应持久化到 IndicatorObservation.analysis(DDB字段) 避免重复请求
    """
    cache_key = f"{name_cn}:{latest_value}:{change_pct}"
    if cache_key in _analysis_cache:
        logger.debug(f"AI analysis cache hit: {cache_key}")
        return _analysis_cache[cache_key]

    if change_pct is None:
        return None

    change_dir = "上涨" if change_pct > 0 else "下跌" if change_pct < 0 else "持平"

    prompt = (
        f"你是一位半导体行业分析师。请用一句话（50-80字）分析以下半导体产业指标的变化原因和含义：\n\n"
        f"指标名称: {name_cn}\n"
        f"供应链环节: {category_cn}\n"
        f"最新值: {latest_value} {unit}\n"
        f"上期值: {previous_value or '无'} {unit}\n"
        f"变化: {change_dir} {abs(change_pct):.1f}%\n"
        f"数据来源: {source}\n\n"
        f"要求：\n"
        f"- 只输出分析文本本身，不要任何前缀/引号\n"
        f"- 指出变化的方向和幅度，解释可能的驱动因素\n"
        f"- 站在产业链角度说明意义\n"
        f"- 语言简洁专业，50-80字"
    )

    try:
        resp = requests.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 200,
                "temperature": 0.3,
            },
            timeout=15,
        )
        if resp.status_code == 200:
            result = resp.json()["choices"][0]["message"]["content"].strip()
            # 清理可能的引号包裹
            result = result.strip("\"'「」")
            _analysis_cache[cache_key] = result
            logger.info(f"AI analysis generated for {name_cn}: {result[:60]}...")
            return result
        else:
            logger.warning(
                f"DeepSeek API error ({resp.status_code}): {resp.text[:200]}"
            )
            return None
    except Exception as e:
        logger.warning(f"DeepSeek API call failed for {name_cn}: {e}")
        return None


def clear_cache():
    """清空内存缓存（用于测试）"""
    _analysis_cache.clear()
