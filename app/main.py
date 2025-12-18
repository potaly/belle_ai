"""FastAPI application entry point."""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import (
    agent_sales_flow as agent_sales_flow_router,
    copy as copy_router,
    followup as followup_router,
    intent as intent_router,
    product as product_router,
    rag_debug as rag_debug_router,
    sales_graph as sales_graph_router,
    vector_search as vector_search_router,
)
from app.api.v1.router import router as v1_router
from app.core.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)

settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
    AI Smart Guide Service - 智能导购服务
    
    为鞋类零售行业提供 AI 驱动的销售助手服务。
    
    ## 功能特性
    
    ### V1 功能
    - 商品文案生成（流式 SSE）
    - 商品分析（规则驱动）
    
    ### V2 功能
    - 向量语义搜索
    - RAG 知识库
    - RAG 调试端点
    
    ### V3 功能
    - 用户行为分析
    - 意图分析
    - 跟进建议
    
    ### V4 功能（AI Agent 系统）
    - 核心 Agent 框架
    - Agent 工具层
    - Planner Agent
    - Worker Agents
    - LangGraph 状态机
    - **AI 智能销售 Agent API** ⭐（推荐使用）
    
    ## 主要 API
    
    - `POST /ai/agent/sales_flow` - AI 智能销售 Agent（V4 最终产物，推荐）
    - `POST /ai/generate/copy` - 生成朋友圈文案（流式）
    - `POST /ai/analyze/product` - 分析商品卖点
    - `POST /ai/vector/search` - 向量语义搜索
    - `POST /ai/analyze/intent` - 分析用户购买意图
    - `POST /ai/followup/suggest` - 生成跟进建议
    - `POST /ai/sales/graph` - 执行销售流程图
    
    详细文档请参考：https://github.com/potaly/belle_ai
    """,
    contact={
        "name": "AI Smart Guide Service",
        "url": "https://github.com/potaly/belle_ai",
    },
    license_info={
        "name": "MIT",
    },
    tags_metadata=[
        {
            "name": "ai",
            "description": "AI 相关接口，包括文案生成、商品分析、向量搜索、意图分析、跟进建议、Agent 系统等",
        },
        {
            "name": "agent",
            "description": "AI Agent 系统接口，包括销售流程图和智能销售 Agent",
        },
    ],
)

# Configure CORS (允许 Demo 页面跨域访问)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8080",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(v1_router)
app.include_router(copy_router.router)
app.include_router(product_router.router)
app.include_router(vector_search_router.router)  # V2: 向量搜索API
app.include_router(rag_debug_router.router)  # V2: RAG 调试端点（仅 DEBUG 模式）
app.include_router(intent_router.router)  # V3: 意图分析API
app.include_router(followup_router.router)  # V3: 跟进建议API
app.include_router(sales_graph_router.router)  # V4: 销售流程图API
app.include_router(agent_sales_flow_router.router)  # V4: AI智能销售Agent API（最终产物）


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "version": settings.app_version}


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
