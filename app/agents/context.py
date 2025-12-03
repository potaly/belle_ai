"""Agent context for managing state and memory during agent execution."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.models.product import Product

logger = logging.getLogger(__name__)


class AgentContext:
    """
    Context object that holds state and memory for agent execution.
    
    This context is passed between agent nodes and accumulates information
    throughout the agent's execution lifecycle.
    
    Attributes:
        user_id: Optional user identifier
        guide_id: Optional guide/salesperson identifier
        sku: Optional product SKU
        product: Optional Product instance
        behavior_summary: Optional behavior summary dictionary
        rag_chunks: List of RAG context chunks
        intent_level: Optional intent level (high/medium/low/hesitating)
        messages: List of conversation messages (memory)
        extra: Flexible dictionary for additional context data
    
    Example:
        >>> context = AgentContext(user_id="user_001", sku="8WZ01CM1")
        >>> context.add_message("user", "我想买一双舒适的运动鞋")
        >>> context.add_message("assistant", "好的，我为您推荐...")
        >>> prompt = context.to_prompt()
    """
    
    def __init__(
        self,
        user_id: Optional[str] = None,
        guide_id: Optional[str] = None,
        sku: Optional[str] = None,
        product: Optional[Product] = None,
        behavior_summary: Optional[dict] = None,
        rag_chunks: Optional[List[str]] = None,
        intent_level: Optional[str] = None,
        messages: Optional[List[dict]] = None,
        extra: Optional[dict] = None,
    ) -> None:
        """
        Initialize agent context.
        
        Args:
            user_id: User identifier
            guide_id: Guide/salesperson identifier
            sku: Product SKU
            product: Product instance
            behavior_summary: Behavior summary dictionary
            rag_chunks: List of RAG context chunks
            intent_level: Intent level string
            messages: Initial conversation messages
            extra: Additional context data
        """
        self.user_id = user_id
        self.guide_id = guide_id
        self.sku = sku
        self.product = product
        self.behavior_summary = behavior_summary
        self.rag_chunks = rag_chunks if rag_chunks is not None else []
        self.intent_level = intent_level
        self.messages = messages if messages is not None else []
        self.extra = extra if extra is not None else {}
        
        logger.debug(
            f"[AGENT_CONTEXT] Initialized context: user_id={user_id}, "
            f"sku={sku}, intent_level={intent_level}, messages_count={len(self.messages)}"
        )
    
    def add_message(self, role: str, content: str) -> None:
        """
        Add a message to the conversation memory.
        
        Args:
            role: Message role ("user", "assistant", "system")
            content: Message content
        
        Example:
            >>> context.add_message("user", "我想买一双鞋")
            >>> context.add_message("assistant", "好的，我为您推荐...")
        """
        if not role or not content:
            logger.warning(
                f"[AGENT_CONTEXT] Attempted to add empty message: role={role}, content={content}"
            )
            return
        
        message = {
            "role": role,
            "content": content,
        }
        self.messages.append(message)
        
        logger.debug(
            f"[AGENT_CONTEXT] Added message: role={role}, "
            f"content_length={len(content)}, total_messages={len(self.messages)}"
        )
    
    def get_latest(self, n: int = 1) -> List[dict]:
        """
        Get the latest N messages from memory.
        
        Args:
            n: Number of latest messages to retrieve (default: 1)
        
        Returns:
            List of message dictionaries (most recent first)
        
        Example:
            >>> latest = context.get_latest(3)
            >>> # Returns the last 3 messages
        """
        if n <= 0:
            logger.warning(f"[AGENT_CONTEXT] Invalid n={n}, returning empty list")
            return []
        
        if n >= len(self.messages):
            return self.messages.copy()
        
        return self.messages[-n:].copy()
    
    def to_prompt(self, include_system: bool = True, max_messages: Optional[int] = None) -> str:
        """
        Convert context state and memory into a prompt text.
        
        This method formats all relevant context information into a structured
        prompt that can be used for LLM generation or logging.
        
        Args:
            include_system: Whether to include system context information
            max_messages: Maximum number of messages to include (None = all)
        
        Returns:
            Formatted prompt string
        
        Example:
            >>> prompt = context.to_prompt()
            >>> # Returns formatted string with all context
        """
        parts = []
        
        # System context section
        if include_system:
            parts.append("## 系统上下文")
            
            if self.user_id:
                parts.append(f"用户ID: {self.user_id}")
            if self.guide_id:
                parts.append(f"导购ID: {self.guide_id}")
            if self.sku:
                parts.append(f"商品SKU: {self.sku}")
            if self.product:
                parts.append(f"商品名称: {self.product.name}")
                if self.product.price:
                    parts.append(f"商品价格: {self.product.price}元")
                if self.product.tags:
                    tags_str = ", ".join(self.product.tags) if isinstance(self.product.tags, list) else str(self.product.tags)
                    parts.append(f"商品标签: {tags_str}")
            if self.intent_level:
                parts.append(f"购买意图级别: {self.intent_level}")
            if self.behavior_summary:
                visit_count = self.behavior_summary.get("visit_count", 0)
                max_stay = self.behavior_summary.get("max_stay_seconds", 0)
                parts.append(f"行为摘要: 访问{visit_count}次, 最大停留{max_stay}秒")
            
            parts.append("")  # Empty line separator
        
        # RAG context section
        if self.rag_chunks:
            parts.append("## 相关商品信息")
            for i, chunk in enumerate(self.rag_chunks, 1):
                parts.append(f"{i}. {chunk}")
            parts.append("")  # Empty line separator
        
        # Conversation history section
        if self.messages:
            parts.append("## 对话历史")
            
            # Limit messages if specified
            messages_to_include = self.messages
            if max_messages is not None and max_messages > 0:
                messages_to_include = self.messages[-max_messages:]
            
            for msg in messages_to_include:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                role_display = {
                    "user": "用户",
                    "assistant": "助手",
                    "system": "系统",
                }.get(role, role)
                parts.append(f"{role_display}: {content}")
            
            parts.append("")  # Empty line separator
        
        # Extra context section
        if self.extra:
            parts.append("## 额外上下文")
            for key, value in self.extra.items():
                parts.append(f"{key}: {value}")
            parts.append("")  # Empty line separator
        
        prompt = "\n".join(parts)
        
        logger.debug(
            f"[AGENT_CONTEXT] Generated prompt: length={len(prompt)}, "
            f"messages_included={len(messages_to_include) if self.messages else 0}"
        )
        
        return prompt
    
    def copy(self) -> "AgentContext":
        """
        Create a deep copy of the context.
        
        Returns:
            New AgentContext instance with copied data
        
        Note:
            Product instance is not deep copied (reference is shared)
        """
        return AgentContext(
            user_id=self.user_id,
            guide_id=self.guide_id,
            sku=self.sku,
            product=self.product,
            behavior_summary=self.behavior_summary.copy() if self.behavior_summary else None,
            rag_chunks=self.rag_chunks.copy(),
            intent_level=self.intent_level,
            messages=[msg.copy() for msg in self.messages],
            extra=self.extra.copy(),
        )
    
    def __repr__(self) -> str:
        """String representation of the context."""
        return (
            f"AgentContext(user_id={self.user_id}, sku={self.sku}, "
            f"intent_level={self.intent_level}, messages={len(self.messages)}, "
            f"rag_chunks={len(self.rag_chunks)})"
        )

