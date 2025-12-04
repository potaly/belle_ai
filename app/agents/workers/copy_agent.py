"""Copy agent for generating marketing copy."""
from __future__ import annotations

import logging

from app.agents.context import AgentContext
from app.agents.tools.copy_tool import generate_marketing_copy
from app.schemas.copy_schemas import CopyStyle

logger = logging.getLogger(__name__)


async def generate_copy_node(context: AgentContext) -> AgentContext:
    """
    文案生成节点：生成营销文案并保存到上下文消息。
    
    调用逻辑：
    - 通常在 retrieve_rag 之后执行（generate_copy），作为内容生成流程的最后一步
    - 前提条件：context.product 必须已设置，context.rag_chunks 可选（用于增强）
    - 调用场景：规划器在反打扰检查通过后才会添加此任务
    - 调用后：生成的文案添加到 context.messages，可通过 context.get_latest() 获取
    - 依赖关系：依赖商品信息和 RAG 上下文（如果有）来生成高质量文案
    
    Args:
        context: Agent context (must have product set, optionally rag_chunks)
    
    Returns:
        Updated AgentContext with generated copy added to messages
    
    Note:
        This node internally calls generate_marketing_copy tool.
        The style can be customized via context.extra["copy_style"].
    """
    logger.info("=" * 80)
    logger.info("[COPY_AGENT] Generating marketing copy")
    logger.info(
        f"[COPY_AGENT] Context: sku={context.sku}, "
        f"has_product={context.product is not None}, "
        f"rag_chunks={len(context.rag_chunks)}"
    )
    
    if not context.product:
        error_msg = "product is required in context to generate copy"
        logger.error(f"[COPY_AGENT] ✗ {error_msg}")
        context.add_message(
            "assistant",
            "抱歉，无法生成文案：缺少商品信息。",
        )
        return context
    
    try:
        # 获取文案风格（从上下文或使用默认值）
        style_str = context.extra.get("copy_style", "natural")
        try:
            style = CopyStyle(style_str)
        except ValueError:
            logger.warning(
                f"[COPY_AGENT] Invalid copy style '{style_str}', using 'natural'"
            )
            style = CopyStyle.natural
        
        # 核心逻辑：调用文案生成工具，生成营销文案
        context = await generate_marketing_copy(context, style=style)
        
        logger.info(
            f"[COPY_AGENT] ✓ Copy generated successfully, "
            f"messages_count={len(context.messages)}"
        )
        logger.info("=" * 80)
        
        return context
        
    except Exception as e:
        logger.error(
            f"[COPY_AGENT] ✗ Error generating copy: {e}",
            exc_info=True,
        )
        # 添加错误消息到上下文
        context.add_message(
            "assistant",
            "抱歉，文案生成过程中出现错误，请稍后重试。",
        )
        return context

