"""
MiniMax AI 分析生成模块
为指标边际变化生成"一句话分析"，解释变化驱动逻辑。
"""

import json
import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_BASE_URL = os.getenv("MINIMAX_BASE_URL", "https://api.minimax.io/v1")
MINIMAX_MODEL = os.getenv("MINIMAX_MODEL", "MiniMax-M3")
API_URL = f"{MINIMAX_BASE_URL}/chat/completions"

# 内存缓存避免同一指标同一值重复调用 MiniMax API
_analysis_cache = {}


def _strip_thinking(content: str) -> str:
    """Strip <think>...</think> reasoning blocks from model output."""
    if not content:
        return content
    # Remove <think>...</think> (MiniMax-M3 style)
    while "<think>" in content and "</think>" in content:
        start = content.find("<think>")
        end = content.find("</think>", start) + len("</think>")
        content = content[:start] + content[end:]
    # Also handle <thinking> variants
    while "<thinking>" in content and "</thinking>" in content:
        start = content.find("<thinking>")
        end = content.find("</thinking>", start) + len("</thinking>")
        content = content[:start] + content[end:]
    return content.strip()


def _strip_json_fences(content: str) -> str:
    """Remove markdown JSON fences like ```json ... ```."""
    if not content:
        return content
    content = content.strip()
    if content.startswith("```"):
        # Drop first fence line
        lines = content.splitlines()
        if lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines).strip()
    return content


def _call_minimax(
    prompt: str,
    max_tokens: int = 400,
    temperature: float = 0.3,
    response_format: Optional[dict] = None,
    timeout: int = 90,
) -> Optional[str]:
    """调用 MiniMax OpenAI-compatible Chat Completions API，返回原始文本内容。"""
    if not MINIMAX_API_KEY:
        logger.warning("MINIMAX_API_KEY not set, skipping AI analysis")
        return None

    payload = {
        "model": MINIMAX_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if response_format:
        payload["response_format"] = response_format

    try:
        resp = requests.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {MINIMAX_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout,
        )
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"].strip()
            return _strip_thinking(content)
        else:
            logger.warning(f"MiniMax API error ({resp.status_code}): {resp.text[:300]}")
            return None
    except Exception as e:
        logger.warning(f"MiniMax API call failed: {e}")
        return None


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
    调用 MiniMax API 生成指标边际变化的"一句话分析"。
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

    result = _call_minimax(prompt, max_tokens=1500, temperature=0.3)
    if result:
        result = result.strip("\"'「」")
        _analysis_cache[cache_key] = result
        logger.info(f"AI analysis generated for {name_cn}: {result[:60]}...")
    return result


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

    content = _call_minimax(
        prompt,
        max_tokens=1500,
        temperature=0.3,
        response_format={"type": "json_object"},
        timeout=90,
    )
    if not content:
        return None

    content = _strip_json_fences(content)

    try:
        result = json.loads(content)
        logger.info(f"Industry impact analysis generated for {name_cn}")
        return result
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse MiniMax JSON response for {name_cn}: {e}; content={content[:200]}")
        return None


def clear_cache():
    """清空内存缓存（用于测试）"""
    _analysis_cache.clear()
