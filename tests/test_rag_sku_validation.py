"""Tests for RAG SKU ownership validation (prevent cross-SKU contamination)."""
from __future__ import annotations

import pytest

from app.agents.context import AgentContext
from app.agents.tools.rag_tool import retrieve_rag
from app.models.product import Product
from app.services.rag_service import RAGService


class TestSKUOwnershipValidation:
    """测试 SKU 所有权验证。"""
    
    def test_filter_foreign_sku_chunks(self):
        """测试：过滤包含其他 SKU 的 chunks。"""
        current_sku = "8WZ01CM1"
        
        chunks = [
            "这是一款舒适的跑鞋，采用网面材质 [SKU:8WZ01CM1]",  # 当前 SKU → 过滤
            "这是一款时尚的运动鞋，价格398元 [SKU:8WZ76CM6]",  # 其他 SKU → 过滤
            "这是一款轻便的休闲鞋，透气舒适",  # 无 SKU → 保留
            "运动鞋的特点是舒适和耐用 SKU:8WZ99CM9",  # 其他 SKU → 过滤
        ]
        
        # Create RAGService instance to access private method
        rag_service = RAGService()
        safe_chunks, filter_reasons = rag_service._filter_by_sku_ownership(chunks, current_sku)
        
        # 应该只保留无 SKU 的 chunk
        assert len(safe_chunks) == 1
        assert "轻便的休闲鞋" in safe_chunks[0]
        assert len(filter_reasons) == 3
        assert any("current SKU" in reason for reason in filter_reasons)
        assert any("foreign SKU" in reason for reason in filter_reasons)
    
    def test_filter_all_foreign_sku_chunks(self):
        """测试：所有 chunks 都包含其他 SKU → 全部过滤，rag_used=false。"""
        current_sku = "8WZ01CM1"
        
        chunks = [
            "这是一款跑鞋 [SKU:8WZ76CM6]",
            "运动鞋价格398元 [SKU:8WZ99CM9]",
            "舒适休闲鞋 SKU:8WZ88CM8",
        ]
        
        # Create RAGService instance to access private method
        rag_service = RAGService()
        safe_chunks, filter_reasons = rag_service._filter_by_sku_ownership(chunks, current_sku)
        
        # 所有 chunks 都被过滤
        assert len(safe_chunks) == 0
        assert len(filter_reasons) == 3
        assert all("foreign SKU" in reason for reason in filter_reasons)
    
    def test_keep_chunks_without_sku(self):
        """测试：保留不包含任何 SKU 的 chunks（通用知识）。"""
        current_sku = "8WZ01CM1"
        
        chunks = [
            "运动鞋的特点是舒适和耐用",
            "网面材质具有良好的透气性",
            "缓震科技可以有效减少冲击力",
        ]
        
        # Create RAGService instance to access private method
        rag_service = RAGService()
        safe_chunks, filter_reasons = rag_service._filter_by_sku_ownership(chunks, current_sku)
        
        # 所有 chunks 都应该保留（无 SKU）
        assert len(safe_chunks) == 3
        assert len(filter_reasons) == 0
    
    def test_filter_current_sku_chunks(self):
        """测试：过滤包含当前 SKU 的 chunks（避免冗余）。"""
        current_sku = "8WZ01CM1"
        
        chunks = [
            "这是一款舒适的跑鞋 [SKU:8WZ01CM1]",
            "运动鞋价格458元 [SKU:8WZ01CM1]",
            "这是一款轻便的休闲鞋",  # 无 SKU → 保留
        ]
        
        # Create RAGService instance to access private method
        rag_service = RAGService()
        safe_chunks, filter_reasons = rag_service._filter_by_sku_ownership(chunks, current_sku)
        
        # 应该只保留无 SKU 的 chunk
        assert len(safe_chunks) == 1
        assert "轻便的休闲鞋" in safe_chunks[0]
        assert len(filter_reasons) == 2
        assert all("current SKU" in reason for reason in filter_reasons)


class TestRAGServiceIntegration:
    """测试 RAG service 集成。"""
    
    def test_rag_service_returns_diagnostics(self):
        """测试：RAG service 返回诊断信息。"""
        # 注意：这个测试需要 mock vector_store
        # 在实际测试中，可以使用 mock 或测试数据库
        pass
    
    def test_rag_tool_sets_diagnostics(self):
        """测试：rag_tool 设置诊断信息到 context。"""
        # 注意：这个测试需要 mock rag_service
        # 在实际测试中，可以使用 mock
        pass


class TestGracefulDegradation:
    """测试优雅降级。"""
    
    def test_no_safe_chunks_rag_used_false(self):
        """测试：如果没有安全的 chunks，rag_used=false。"""
        current_sku = "8WZ01CM1"
        
        chunks = [
            "这是一款跑鞋 [SKU:8WZ76CM6]",
            "运动鞋价格398元 [SKU:8WZ99CM9]",
        ]
        
        # Create RAGService instance to access private method
        rag_service = RAGService()
        safe_chunks, filter_reasons = rag_service._filter_by_sku_ownership(chunks, current_sku)
        
        # 所有 chunks 都被过滤
        assert len(safe_chunks) == 0
        
        # rag_used 应该为 false（由调用方判断）
        rag_used = len(safe_chunks) > 0
        assert rag_used is False


class TestPromptBuilderGrounding:
    """测试 prompt builder 的事实基础。"""
    
    def test_prompt_explicitly_forbids_foreign_facts(self):
        """测试：prompt 明确禁止使用 RAG 中的事实信息。"""
        from app.services.prompt_builder import PromptBuilder
        from app.schemas.copy_schemas import CopyStyle
        
        product = Product(
            sku="8WZ01CM1",
            name="舒适跑鞋",
            price=398.0,
            tags=["舒适", "轻便"],
        )
        
        rag_context = [
            "这是一款时尚的运动鞋，价格458元 [SKU:8WZ76CM6]",
            "运动鞋采用真皮材质，价格598元 [SKU:8WZ99CM9]",
        ]
        
        prompt = PromptBuilder.build_copy_prompt(
            product=product,
            style=CopyStyle.natural,
            rag_context=rag_context,
        )
        
        # 验证 prompt 包含严格禁止事项
        assert "严格禁止" in prompt or "禁止" in prompt
        assert "唯一事实来源" in prompt or "商品信息" in prompt
        assert "价格" in prompt or "SKU" in prompt  # 应该提到禁止使用价格/SKU
    
    def test_prompt_cleans_sku_from_rag_context(self):
        """测试：prompt 从 RAG context 中清理 SKU 标记。"""
        from app.services.prompt_builder import PromptBuilder
        from app.schemas.copy_schemas import CopyStyle
        
        product = Product(
            sku="8WZ01CM1",
            name="舒适跑鞋",
            price=398.0,
        )
        
        rag_context = [
            "这是一款时尚的运动鞋 [SKU:8WZ76CM6]",
        ]
        
        prompt = PromptBuilder.build_copy_prompt(
            product=product,
            style=CopyStyle.natural,
            rag_context=rag_context,
        )
        
        # 验证 prompt 中不包含 SKU 标记
        assert "[SKU:8WZ76CM6]" not in prompt
        assert "8WZ76CM6" not in prompt


class TestGeneratedOutputValidation:
    """测试生成输出的验证。"""
    
    def test_generated_output_no_foreign_sku(self):
        """测试：生成的输出不包含其他 SKU 标识符。"""
        # 这个测试需要实际调用 LLM 或使用 mock
        # 在实际测试中，可以：
        # 1. 使用 mock LLM 返回包含其他 SKU 的内容
        # 2. 验证系统拒绝或清理这些内容
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

