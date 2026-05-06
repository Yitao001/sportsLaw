"""
SportsLax React Agent（保留文件结构，实际逻辑已迁移到 agent/tools/agent_tools.py）

本文件仅作为未来扩展使用。当前三大核心功能直接由 agent_tools 模块提供：
  - legal_chat / legal_chat_stream       —— 智能法律对话
  - generate_legal_info_report / _stream —— 律师信息清单报告
  - query_sport_knowledge / _stream      —— 体育运动百科
"""
from agent.tools.agent_tools import (
    legal_chat,
    legal_chat_stream,
    generate_legal_info_report,
    generate_legal_info_report_stream,
    query_sport_knowledge,
    query_sport_knowledge_stream,
)

__all__ = [
    "legal_chat",
    "legal_chat_stream",
    "generate_legal_info_report",
    "generate_legal_info_report_stream",
    "query_sport_knowledge",
    "query_sport_knowledge_stream",
]
