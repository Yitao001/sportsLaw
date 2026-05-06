#!/usr/bin/env python3
"""
SportsLax — 体育法律咨询智能体 API 服务

核心功能：
  1. /chat         智能法律对话（RAG + LLM，流式输出）
  2. /report       生成律师咨询信息清单报告（流式输出）
  3. /sport        体育运动百科查询
  4. /sports/list  获取已收录运动列表
  5. /health       健康检查
"""
from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.security import APIKeyHeader
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from typing import Optional
import os

from agent.tools.agent_tools import (
    legal_chat_async,
    legal_chat_stream,
    generate_legal_info_report_async,
    generate_legal_info_report_stream,
    query_sport_knowledge_async,
    query_sport_knowledge_stream,
)
from knowledge.sports_knowledge import list_all_sports
from utils.config_handler import security_conf
from utils.logger_handler import logger
from model.factory import chat_model

# ──────────────────────────────────────────────
# 基础配置
# ──────────────────────────────────────────────
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="SportsLax — 体育法律咨询智能体",
    description=(
        "**SportsLax** 是专注于国际体育法律的 AI 智能顾问。\n\n"
        "### 核心功能\n"
        "- 🗣️ **智能法律对话**：基于 RAG + LLM 回答国际体育法律问题\n"
        "- 📋 **律师信息清单报告**：运动员描述情况后，自动生成可交给律师的结构化报告\n"
        "- 🏅 **体育运动百科**：了解各类运动的规则、管理机构及法律特点\n"
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    swagger_ui_parameters={"defaultModelsExpandDepth": -1},
)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    schema["components"]["securitySchemes"] = {
        "APIKeyHeader": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "请在请求头中传入 X-API-Key 进行认证",
        }
    }
    schema["security"] = [{"APIKeyHeader": []}]
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.on_event("startup")
async def startup():
    """服务启动时初始化向量库和文件监听。"""
    from rag.rag_engine import build_vector_store
    from rag.file_watcher import start_vault_watcher

    # 预热向量库（冷启动时顺便把 vault 文档也建进去）
    try:
        build_vector_store()
    except Exception:
        pass  # 不阻塞启动

    # 启动 vault 文件监听
    start_vault_watcher()

cors_origins = [o.strip() for o in security_conf.get("cors_origins", []) if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins if cors_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────
# 认证
# ──────────────────────────────────────────────
async def get_api_key(api_key: str = Depends(api_key_header)):
    configured_key = security_conf.get("api_key", "")
    if not configured_key:
        logger.warning("[API] 未配置 API Key，运行在非安全模式")
        return None
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少 API Key")
    if api_key != configured_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的 API Key")
    return api_key


# ──────────────────────────────────────────────
# 请求 / 响应模型
# ──────────────────────────────────────────────
RATE = security_conf.get("rate_limit_per_minute", 60)


class ChatRequest(BaseModel):
    question: str = Field(
        ...,
        description="用户的法律咨询问题",
        min_length=1,
        max_length=2000,
        json_schema_extra={"example": "运动员在CAS仲裁中如何提出上诉？"},
    )
    chat_history: Optional[list[dict]] = Field(
        default=None,
        description='历史对话记录，格式：[{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]',
    )
    stream: bool = Field(default=True, description="是否启用流式输出")

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("问题不能为空")
        return v


class ReportRequest(BaseModel):
    description: str = Field(
        ...,
        description="运动员描述自身遇到的法律情况（越详细越好）",
        min_length=10,
        max_length=5000,
        json_schema_extra={
            "example": (
                "我是一名职业游泳运动员，上个月在全国锦标赛赛后被通知兴奋剂检测阳性，"
                "检测出一种我从未服用过的物质，我怀疑是营养补剂污染。"
                "国家反兴奋剂机构要求我在30天内提交申辩书。请帮我整理需要准备的材料。"
            )
        },
    )
    stream: bool = Field(default=True, description="是否启用流式输出")

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 10:
            raise ValueError("情况描述至少需要10个字符")
        return v


class SportQueryRequest(BaseModel):
    sport_name: str = Field(
        ...,
        description="运动名称（中文）",
        min_length=1,
        max_length=50,
        json_schema_extra={"example": "足球"},
    )
    question: Optional[str] = Field(
        default=None,
        description="具体想了解的内容（可选，如不填则给出综合介绍）",
        json_schema_extra={"example": "FIFA转会规则有哪些法律风险？"},
    )
    stream: bool = Field(default=False, description="是否启用流式输出")


# ──────────────────────────────────────────────
# 异常处理
# ──────────────────────────────────────────────
@app.exception_handler(422)
async def validation_handler(request: Request, exc):
    return JSONResponse(
        status_code=422,
        content={
            "status": "error",
            "message": "请求参数验证失败，请检查请求体格式",
        },
    )


# ──────────────────────────────────────────────
# 端点 1：智能法律对话
# ──────────────────────────────────────────────
@app.post(
    "/chat",
    summary="智能法律对话",
    description=(
        "基于 RAG 知识库 + 大语言模型，回答国际体育法律问题。\n\n"
        "支持多轮对话（传入 `chat_history`），支持流式输出（`stream=true`）。\n\n"
        "**覆盖领域**：CAS仲裁、WADA反兴奋剂、FIFA转会、运动员权利、体育合同、媒体版权等。"
    ),
    tags=["核心功能"],
)
@limiter.limit(f"{RATE}/minute")
async def chat_endpoint(
    request: Request,
    body: ChatRequest,
    api_key: str = Depends(get_api_key),
):
    logger.info(f"[Chat] 收到问题: {body.question[:80]}...")

    if body.stream:
        async def generate():
            async for chunk in legal_chat_stream(body.question, body.chat_history):
                yield chunk

        return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")

    try:
        answer = await legal_chat_async(body.question, body.chat_history)
        return {"status": "success", "answer": answer}
    except Exception as e:
        logger.error(f"[Chat] 对话失败: {e}")
        raise HTTPException(status_code=500, detail=f"对话失败: {str(e)}")


# ──────────────────────────────────────────────
# 端点 2：生成律师信息清单报告
# ──────────────────────────────────────────────
@app.post(
    "/report",
    summary="生成律师信息清单报告",
    description=(
        "运动员输入自身遇到的法律情况描述，系统自动检索相关法律背景，\n\n"
        "生成一份结构完整、可直接交给律师的**信息清单报告**（Markdown格式）。\n\n"
        "报告包含：事实摘要、涉及法律领域、关键事实清单、文件清单、风险评估、建议行动等。"
    ),
    tags=["核心功能"],
)
@limiter.limit(f"{RATE}/minute")
async def report_endpoint(
    request: Request,
    body: ReportRequest,
    api_key: str = Depends(get_api_key),
):
    logger.info(f"[Report] 收到报告请求，描述长度: {len(body.description)} 字")

    if body.stream:
        async def generate():
            async for chunk in generate_legal_info_report_stream(body.description):
                yield chunk

        return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")

    try:
        report = await generate_legal_info_report_async(body.description)
        return {"status": "success", "report": report}
    except Exception as e:
        logger.error(f"[Report] 报告生成失败: {e}")
        raise HTTPException(status_code=500, detail=f"报告生成失败: {str(e)}")


# ──────────────────────────────────────────────
# 端点 3：体育运动百科查询
# ──────────────────────────────────────────────
@app.post(
    "/sport",
    summary="体育运动百科查询",
    description=(
        "查询指定运动项目的综合介绍，包含：\n\n"
        "- 管理机构与主要赛事\n"
        "- 基本规则简介\n"
        "- **法律特点**（兴奋剂、转会、合同等法律议题）\n"
        "- 职业化程度与奥运状态\n\n"
        "支持中文运动名称，如「足球」、「网球」、「电子竞技」等。"
    ),
    tags=["核心功能"],
)
@limiter.limit(f"{RATE}/minute")
async def sport_endpoint(
    request: Request,
    body: SportQueryRequest,
    api_key: str = Depends(get_api_key),
):
    logger.info(f"[Sport] 查询运动: {body.sport_name}")

    if body.stream:
        async def generate():
            async for chunk in query_sport_knowledge_stream(
                body.sport_name, body.question or ""
            ):
                yield chunk

        return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")

    try:
        result = await query_sport_knowledge_async(body.sport_name, body.question or "")
        return {"status": "success", "sport": body.sport_name, "content": result}
    except Exception as e:
        logger.error(f"[Sport] 查询失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@app.get(
    "/sports/list",
    summary="获取已收录运动列表",
    description="返回系统知识库中已收录的所有体育运动名称列表。",
    tags=["核心功能"],
)
@limiter.limit(f"{RATE}/minute")
async def sports_list_endpoint(
    request: Request,
    api_key: str = Depends(get_api_key),
):
    sports = list_all_sports()
    return {"status": "success", "count": len(sports), "sports": sports}


# ──────────────────────────────────────────────
# 端点 6：知识库管理
# ──────────────────────────────────────────────
@app.post(
    "/knowledge/reload",
    summary="重建向量知识库",
    description=(
        "手动触发向量知识库重建，将 Obsidian vault 中的 .md 文档同步到向量索引。\n\n"
        "**使用场景**：在 Obsidian 中编辑了知识库文档后，调用此接口使更改生效。"
    ),
    tags=["知识库管理"],
)
@limiter.limit(f"{RATE}/minute")
async def reload_knowledge_endpoint(
    request: Request,
    api_key: str = Depends(get_api_key),
):
    try:
        from rag.rag_engine import build_vector_store
        from rag.obsidian_loader import load_vault_documents

        vault_docs = load_vault_documents()
        vectorstore = build_vector_store(force_rebuild=True)
        return {
            "status": "success",
            "vault_doc_count": len(vault_docs),
            "message": f"知识库已重建，已同步 {len(vault_docs)} 个 Obsidian vault 文档。"
        }
    except Exception as e:
        logger.error(f"[Knowledge] 重建失败: {e}")
        raise HTTPException(status_code=500, detail=f"重建失败: {str(e)}")


@app.get(
    "/knowledge/vault",
    summary="查看 Obsidian Vault 状态",
    description="返回 vault 目录中的文档列表（不含正文），用于确认哪些文档已被加载。",
    tags=["知识库管理"],
)
@limiter.limit(f"{RATE}/minute")
async def vault_status_endpoint(
    request: Request,
    api_key: str = Depends(get_api_key),
):
    from rag.obsidian_loader import load_vault_documents

    docs = load_vault_documents()
    file_list = [
        {
            "title": d.metadata.get("title", "未命名"),
            "source": d.metadata.get("source", ""),
            "filename": d.metadata.get("filename", ""),
            "category": d.metadata.get("category", ""),
            "chars": len(d.page_content),
        }
        for d in docs
    ]
    return {"status": "success", "count": len(file_list), "files": file_list}


# ──────────────────────────────────────────────
# 健康检查
# ──────────────────────────────────────────────
@app.get(
    "/health",
    summary="健康检查",
    description="检查 API 服务与 LLM 连通性。",
    tags=["系统"],
)
@limiter.limit(f"{RATE}/minute")
async def health_check(request: Request, api_key: str = Depends(get_api_key)):
    llm_ok = False
    try:
        from langchain_core.messages import HumanMessage
        resp = chat_model().invoke([HumanMessage(content="回复OK")])
        llm_ok = bool(resp and resp.content)
    except Exception as e:
        logger.error(f"[Health] LLM 检查失败: {e}")

    return {
        "status": "ok" if llm_ok else "degraded",
        "checks": {
            "api": {"status": "ok"},
            "llm": {"status": "ok" if llm_ok else "error"},
        },
    }


@app.get(
    "/health/lite",
    summary="轻量健康检查",
    tags=["系统"],
)
@limiter.limit(f"{RATE}/minute")
async def health_lite(request: Request, api_key: str = Depends(get_api_key)):
    return {"status": "ok", "message": "SportsLax API 运行正常"}


# ──────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print("  SportsLax — 体育法律咨询智能体 API 启动中")
    print("=" * 60)
    print("  Swagger UI : http://localhost:8000/docs")
    print("  ReDoc      : http://localhost:8000/redoc")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000)
