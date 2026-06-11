"""
DeepSeek AI 分析生成模块
为指标边际变化生成"一句话分析"，解释变化驱动逻辑。
"""

import json
import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
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
    - 调用方应持久化到 IndicatorObservation.analysis 避免重复请求
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
            result = result.strip("\"'「」")
            _analysis_cache[cache_key] = result
            logger.info(f"AI analysis generated for {name_cn}: {result[:60]}...")
            return result
        else:
            logger.warning(f"DeepSeek API error ({resp.status_code}): {resp.text[:200]}")
            return None
    except Exception as e:
        logger.warning(f"DeepSeek API call failed for {name_cn}: {e}")
        return None


def generate_industry_impact_analysis(
    name_cn: str,
    category_cn: str,
    latest_value: float,
    previous_value: Optional[float],
    change_pct: Optional[float],
    marginal_change_pct: Optional[float],
    comparison_window: Optional[str],
    unit: str,
    related_tickers: str,
) -> Optional[dict]:
    """
    生成行业景气度/产业链/重点公司的三重影响分析。
    返回 {"industry_impact": str, "chain_impact": str, "company_impact": str}
    """
    if change_pct is None and marginal_change_pct is None:
        return None

    change_desc = ""
    if change_pct is not None:
        change_desc += f"环比变化: {change_pct:+.1f}%"
    if marginal_change_pct is not None:
        change_desc += f" | 边际变化({comparison_window or '窗口'}): {marginal_change_pct:+.1f}%"

    prompt = (
        f"你是一位半导体产业链首席分析师。请分析以下指标变化对行业景气度、产业链环节和重点公司的影响。\n\n"
        f"指标名称: {name_cn}\n"
        f"供应链环节: {category_cn}\n"
        f"最新值: {latest_value} {unit}\n"
        f"上期值: {previous_value or '无'} {unit}\n"
        f"{change_desc}\n"
        f"关联公司: {related_tickers or '无'}\n\n"
        f"请严格按照以下JSON格式输出（不要任何前缀/后缀，只输出JSON）：\n"
        f"{{\n"
        f'  "industry_impact": "对行业整体景气度的影响，判断方向（向上/向下）及幅度，50字内",\n'
        f'  "chain_impact": "对产业链各环节的影响（利好哪些环节、利空哪些环节），50字内",\n'
        f'  "company_impact": "对重点公司估值的正面/负面影响，列举受影响最大的1-2家公司，50字内"\n'
        f"}}\n\n"
        f"注意：前值缺失时，不可以解读为没有变化。如果边际变化数据可用，优先基于边际变化分析。"
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
                "max_tokens": 500,
                "temperature": 0.3,
                "response_format": {"type": "json_object"},
            },
            timeout=20,
        )
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"].strip()
            result = json.loads(content)
            logger.info(f"Industry impact analysis generated for {name_cn}")
            return result
        else:
            logger.warning(f"DeepSeek API error ({resp.status_code}): {resp.text[:200]}")
            return None
    except Exception as e:
        logger.warning(f"Industry impact analysis failed for {name_cn}: {e}")
        return None


def clear_cache():
    """清空内存缓存（用于测试）"""
    _analysis_cache.clear()
