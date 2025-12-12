"""Agent runner for executing agent nodes and plans."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, List, Optional

from app.agents.context import AgentContext

logger = logging.getLogger(__name__)

# Type alias for agent node functions
AgentNode = Callable[[AgentContext], Any]


class AgentRunner:
    
    """
    Runner for executing agent nodes and plans.
    
    The AgentRunner orchestrates the execution of agent nodes, providing
    logging, error handling, and explainability features.
    
    Example:
        >>> runner = AgentRunner()
        >>> context = AgentContext(user_id="user_001", sku="8WZ01CM1")
        >>> 
        >>> async def my_node(context: AgentContext) -> AgentContext:
        ...     context.add_message("assistant", "Hello!")
        ...     return context
        >>> 
        >>> result = await runner.run_node(my_node, context)
        >>> 
        >>> # Or execute a plan
        >>> plan = ["node1", "node2", "node3"]
        >>> result = await runner.execute_plan(plan, context, node_registry)
    """
    
    def __init__(self, enable_logging: bool = True) -> None:
        """
        Initialize agent runner.
        
        Args:
            enable_logging: Whether to enable detailed logging of node execution
        """
        self.enable_logging = enable_logging
        logger.info(f"[AGENT_RUNNER] Initialized with logging={enable_logging}")
    
    async def run_node(
        self,
        node: AgentNode,
        context: AgentContext,
        node_name: Optional[str] = None,
    ) -> AgentContext:
        """
        Execute a single agent node.
        
        This method runs a node function with the provided context, handles
        errors, and logs execution details for explainability.
        
        Args:
            node: Agent node function (async def node(context) -> context)
            context: Agent context to pass to the node
            node_name: Optional name for the node (for logging)
        
        Returns:
            Updated AgentContext after node execution
        
        Raises:
            Exception: Re-raises any exception from node execution
        
        Example:
            >>> async def analyze_intent(context: AgentContext) -> AgentContext:
            ...     # Do some analysis
            ...     context.intent_level = "high"
            ...     return context
            >>> 
            >>> runner = AgentRunner()
            >>> result = await runner.run_node(analyze_intent, context, "analyze_intent")
        """
        node_name = node_name or getattr(node, "__name__", "unknown_node")
        
        logger.info("=" * 80)
        logger.info(f"[AGENT_RUNNER] Executing node: {node_name}")
        logger.info(f"[AGENT_RUNNER] Context: {context}")
        
        start_time = time.time()
        
        try:
            # Execute the node
            if asyncio.iscoroutinefunction(node):
                result = await node(context)
            else:
                # Handle synchronous nodes
                result = node(context)
            
            # Validate result
            if not isinstance(result, AgentContext):
                logger.warning(
                    f"[AGENT_RUNNER] Node {node_name} returned non-Context result: {type(result)}"
                )
                # If node doesn't return context, assume it modified the input context
                result = context
            
            execution_time = time.time() - start_time
            
            logger.info(
                f"[AGENT_RUNNER] ✓ Node {node_name} completed successfully "
                f"in {execution_time:.3f}s"
            )
            logger.info(
                f"[AGENT_RUNNER] Context after execution: "
                f"messages={len(result.messages)}, "
                f"rag_chunks={len(result.rag_chunks)}, "
                f"intent_level={result.intent_level}"
            )
            logger.info("=" * 80)
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            
            logger.error(
                f"[AGENT_RUNNER] ✗ Node {node_name} failed after {execution_time:.3f}s: {e}",
                exc_info=True,
            )
            logger.info("=" * 80)
            
            # Re-raise the exception for caller to handle
            raise
    
    async def execute_plan(
        self,
        plan: List[str],
        context: AgentContext,
        node_registry: dict[str, AgentNode],
    ) -> AgentContext:
        
        """
        Execute a plan (sequence of node names).
        
        This method executes nodes in sequence according to the plan, with
        full logging and error handling for each step.
        
        Args:
            plan: List of node names to execute in order
            context: Initial agent context
            node_registry: Dictionary mapping node names to node functions
        
        Returns:
            Final AgentContext after all nodes have executed
        
        Raises:
            KeyError: If a node name in plan is not found in registry
            Exception: Re-raises any exception from node execution
        
        Example:
            >>> node_registry = {
            ...     "load_product": load_product_node,
            ...     "analyze_intent": analyze_intent_node,
            ...     "generate_response": generate_response_node,
            ... }
            >>> 
            >>> plan = ["load_product", "analyze_intent", "generate_response"]
            >>> runner = AgentRunner()
            >>> result = await runner.execute_plan(plan, context, node_registry)
        """
        logger.info("=" * 80)
        logger.info(f"[AGENT_RUNNER] Executing plan with {len(plan)} nodes")
        logger.info(f"[AGENT_RUNNER] Plan: {' -> '.join(plan)}")
        logger.info("=" * 80)
        
        current_context = context
        
        for i, node_name in enumerate(plan, 1):
            logger.info(f"[AGENT_RUNNER] Step {i}/{len(plan)}: {node_name}")
            
            # Look up node in registry
            if node_name not in node_registry:
                error_msg = (
                    f"Node '{node_name}' not found in registry. "
                    f"Available nodes: {list(node_registry.keys())}"
                )
                logger.error(f"[AGENT_RUNNER] ✗ {error_msg}")
                raise KeyError(error_msg)
            
            node = node_registry[node_name]
            
            # Execute node
            try:
                current_context = await self.run_node(node, current_context, node_name)
            except Exception as e:
                logger.error(
                    f"[AGENT_RUNNER] ✗ Plan execution failed at step {i}/{len(plan)} "
                    f"(node: {node_name}): {e}"
                )
                raise
        
        logger.info("=" * 80)
        logger.info(
            f"[AGENT_RUNNER] ✓ Plan execution completed successfully. "
            f"Final context: messages={len(current_context.messages)}, "
            f"intent_level={current_context.intent_level}"
        )
        logger.info("=" * 80)
        
        return current_context
    
    def create_node_registry(self, *nodes: tuple[str, AgentNode]) -> dict[str, AgentNode]:
        """
        Create a node registry from node tuples.
        
        Convenience method for creating a node registry.
        
        Args:
            *nodes: Variable number of (name, node_function) tuples
        
        Returns:
            Dictionary mapping node names to node functions
        
        Example:
            >>> registry = runner.create_node_registry(
            ...     ("load_product", load_product_node),
            ...     ("analyze_intent", analyze_intent_node),
            ... )
        """
        registry = {}
        for name, node_func in nodes:
            registry[name] = node_func
        logger.debug(f"[AGENT_RUNNER] Created node registry with {len(registry)} nodes")
        return registry

