"""
SportsLax 智能体工具层
核心功能：
1. 智能法律对话 —— RAG + LLM 给出专业回答
2. 法律服务信息检索 —— 生成可交给律师的信息清单报告
3. 体育运动百科查询 —— 了解各种体育运动
"""
import asyncio
from typing import AsyncGenerator, Optional
from datetime import datetime

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from utils.logger_handler import logger
from utils.retry_utils import with_retry, llm_retry_config
from utils.path_tool import get_abs_path
from model.factory import chat_model
from rag.rag_engine import retrieve_sports_law
from knowledge.sports_knowledge import format_sport_info, list_all_sports


# ─────────────────────────────────────────────────────────────
# 1. 智能法律对话（RAG + LLM）
# ─────────────────────────────────────────────────────────────

LEGAL_CHAT_SYSTEM = """你是 SportsLax，一位专注于国际体育法律的专业智能顾问。
你的专业领域包括：CAS仲裁、WADA反兴奋剂规则、FIFA转会规则、运动员权利保护、
体育赛事合同、媒体转播权、反歧视规则、运动员伤害与保险等。

在回答问题时，请遵循以下原则：
1. 优先基于提供的知识库内容（RAG检索结果）给出专业回答
2. 引用具体规则条文、仲裁案例或机构名称，增强可信度
3. 如果问题超出体育法律范畴，礼貌说明并引导回体育法律相关话题
4. 在涉及具体案件时，提醒用户本回答为一般性法律信息，不构成正式法律意见，建议咨询执业律师
5. 语言专业但易于理解，避免过度使用法律术语

相关法律知识参考（来自知识库）：
{rag_context}
"""

LEGAL_CHAT_HUMAN = "用户问题：{question}"


@with_retry(config=llm_retry_config)
def legal_chat(question: str, chat_history: Optional[list] = None) -> str:
    """
    体育法律智能对话（同步版，供后台线程调用）
    Args:
        question: 用户问题
        chat_history: 历史对话记录 [{"role": "user/assistant", "content": "..."}]
    Returns:
        AI回答
    """
    # RAG检索
    rag_results = retrieve_sports_law(question, k=4)
    rag_context = _format_rag_context(rag_results)

    # 构建消息列表
    messages = [
        SystemMessage(content=LEGAL_CHAT_SYSTEM.format(rag_context=rag_context))
    ]

    # 加入历史对话
    if chat_history:
        for turn in chat_history[-6:]:  # 最多保留最近6轮
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            else:
                messages.append(AIMessage(content=content))

    messages.append(HumanMessage(content=question))

    response = chat_model().invoke(messages)
    return response.content


async def legal_chat_async(question: str, chat_history: Optional[list] = None) -> str:
    """
    体育法律智能对话（异步非阻塞版，供 async endpoint 调用）
    在线程池中运行同步 LLM 调用，不阻塞事件循环
    """
    return await asyncio.to_thread(legal_chat, question, chat_history)


async def legal_chat_stream(
    question: str,
    chat_history: Optional[list] = None
) -> AsyncGenerator[str, None]:
    """
    体育法律智能对话（流式输出版）
    Args:
        question: 用户问题
        chat_history: 历史对话
    Yields:
        回答文本片段
    """
    rag_results = retrieve_sports_law(question, k=4)
    rag_context = _format_rag_context(rag_results)

    messages = [
        SystemMessage(content=LEGAL_CHAT_SYSTEM.format(rag_context=rag_context))
    ]

    if chat_history:
        for turn in chat_history[-6:]:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            else:
                messages.append(AIMessage(content=content))

    messages.append(HumanMessage(content=question))

    async for chunk in chat_model().astream(messages):
        if hasattr(chunk, "content") and chunk.content:
            yield chunk.content


def _format_rag_context(rag_results: list[dict]) -> str:
    """将RAG检索结果格式化为上下文文本"""
    if not rag_results:
        return "（暂无直接相关的知识库内容，请基于通用体育法律知识回答）"

    parts = []
    for i, result in enumerate(rag_results, 1):
        source = result.get("source", "未知来源")
        category = result.get("category", "")
        content = result.get("content", "")
        parts.append(f"[{i}] 来源：{source}（{category}）\n{content}")

    return "\n\n---\n\n".join(parts)


# ─────────────────────────────────────────────────────────────
# 2. 法律服务信息检索 —— 生成律师信息清单报告
# ─────────────────────────────────────────────────────────────

LEGAL_INFO_EXTRACTION_PROMPT = """你是一位专业的体育法律顾问助手，帮助运动员整理向律师咨询所需的信息清单。

根据以下运动员提供的情况描述，生成一份结构清晰、专业完整的**律师咨询信息清单报告**。

## 运动员描述的情况
{athlete_description}

## 相关法律背景（供参考）
{rag_context}

## 报告生成要求
请严格按照以下格式输出报告，确保每个部分都包含完整信息：

---

# 体育法律咨询信息清单报告
**生成时间**：{current_time}
**用途说明**：本报告用于辅助运动员向执业律师提供完整的案件背景信息，不构成正式法律意见。

---

## 一、基本情况摘要
（根据描述提炼核心事实，包括当事人身份、事件性质、时间线）

## 二、涉及的法律领域
（列出本案可能涉及的体育法律领域，如：反兴奋剂、转会纠纷、合同纠纷等）

## 三、关键事实清单
（列出律师需要了解的核心事实要点，每项用"- "开头）

## 四、需要运动员提供的文件清单
（律师需要审阅的文件，每项注明重要程度：【必须】/【建议】/【可选】）

## 五、可能适用的规则与机构
（列出相关国际体育组织规则、仲裁机构、申诉程序）

## 六、初步法律风险评估
（基于提供信息，初步分析可能面临的法律风险，标注高/中/低风险）

## 七、建议后续行动
（推荐的下一步行动，按优先级排列）

## 八、补充问题清单
（律师可能向运动员提出的补充问题，帮助运动员提前准备）

---
*本报告由 SportsLax 体育法律智能顾问生成。建议在向律师咨询前，仔细核对以上信息的准确性。*
"""


@with_retry(config=llm_retry_config)
def generate_legal_info_report(athlete_description: str) -> str:
    """
    根据运动员描述生成律师咨询信息清单报告（同步版）
    Args:
        athlete_description: 运动员描述的情况
    Returns:
        格式化的律师信息清单报告（Markdown格式）
    """
    # 基于描述进行RAG检索
    rag_results = retrieve_sports_law(athlete_description, k=5)
    rag_context = _format_rag_context(rag_results)

    current_time = datetime.now().strftime("%Y年%m月%d日 %H:%M")

    prompt = LEGAL_INFO_EXTRACTION_PROMPT.format(
        athlete_description=athlete_description,
        rag_context=rag_context,
        current_time=current_time
    )

    response = chat_model().invoke([HumanMessage(content=prompt)])
    return response.content


async def generate_legal_info_report_async(athlete_description: str) -> str:
    """报告生成异步非阻塞版，供 async endpoint 调用"""
    return await asyncio.to_thread(generate_legal_info_report, athlete_description)


async def generate_legal_info_report_stream(athlete_description: str) -> AsyncGenerator[str, None]:
    """
    流式生成律师咨询信息清单报告
    Args:
        athlete_description: 运动员描述的情况
    Yields:
        报告文本片段
    """
    rag_results = retrieve_sports_law(athlete_description, k=5)
    rag_context = _format_rag_context(rag_results)
    current_time = datetime.now().strftime("%Y年%m月%d日 %H:%M")

    prompt = LEGAL_INFO_EXTRACTION_PROMPT.format(
        athlete_description=athlete_description,
        rag_context=rag_context,
        current_time=current_time
    )

    async for chunk in chat_model().astream([HumanMessage(content=prompt)]):
        if hasattr(chunk, "content") and chunk.content:
            yield chunk.content


# ─────────────────────────────────────────────────────────────
# 3. 体育运动百科查询
# ─────────────────────────────────────────────────────────────

SPORT_QUERY_PROMPT = """你是 SportsLax 体育知识顾问，专注于体育运动的规则、管理机构、法律特点等方面。

用户询问关于"{sport_name}"的信息。

## 本地知识库信息：
{sport_info}

## 补充要求
请基于以上信息，用友好、专业的语气向用户介绍该运动：
1. 首先给出运动的基本介绍
2. 重点介绍该运动的法律特点（如有）
3. 如果用户明确询问的是法律方面，深入展开法律细节
4. 语言生动，适当使用体育领域专业术语但保持可读性

用户的原始问题：{user_question}
"""


@with_retry(config=llm_retry_config)
def query_sport_knowledge(sport_name: str, user_question: str = "") -> str:
    """
    查询体育运动知识（含法律背景，同步版）
    Args:
        sport_name: 运动名称
        user_question: 用户原始问题
    Returns:
        运动知识介绍
    """
    sport_info = format_sport_info(sport_name)

    prompt = SPORT_QUERY_PROMPT.format(
        sport_name=sport_name,
        sport_info=sport_info,
        user_question=user_question or f"请介绍{sport_name}"
    )

    response = chat_model().invoke([HumanMessage(content=prompt)])
    return response.content


async def query_sport_knowledge_async(sport_name: str, user_question: str = "") -> str:
    """体育百科查询异步非阻塞版，供 async endpoint 调用"""
    return await asyncio.to_thread(query_sport_knowledge, sport_name, user_question)


async def query_sport_knowledge_stream(
    sport_name: str,
    user_question: str = ""
) -> AsyncGenerator[str, None]:
    """
    流式查询体育运动知识
    """
    sport_info = format_sport_info(sport_name)
    prompt = SPORT_QUERY_PROMPT.format(
        sport_name=sport_name,
        sport_info=sport_info,
        user_question=user_question or f"请介绍{sport_name}"
    )

    async for chunk in chat_model().astream([HumanMessage(content=prompt)]):
        if hasattr(chunk, "content") and chunk.content:
            yield chunk.content
