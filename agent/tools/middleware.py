"""
SportsLax 中间件层（占位文件）

原旧版使用了不存在的 LangChain/LangGraph API（langchain.agents.middleware、
langgraph.runtime 等），已全部废弃。

SportsLax 的业务逻辑已集中在 agent/tools/agent_tools.py 中，
通过 FastAPI 端点直接暴露，不再需要 middleware 层。
"""
