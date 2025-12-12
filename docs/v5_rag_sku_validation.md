# V5.2.0: RAG SKU 所有权验证（防止串货风险）

## 问题背景

当前 RAG 可能召回"相似 SKU"的内容，在零售场景中会导致：
- **串货**：将其他商品的 SKU 混入当前商品
- **价格错误**：使用其他商品的价格信息
- **材质错误**：混淆不同商品的材质信息

这是生产级系统中**最高风险问题之一**，必须从设计上彻底规避。

## 解决方案

### 1. 严格 SKU 所有权验证

在 `app/services/rag_service.py` 中实现：

- **`_filter_by_sku_ownership()`**：严格过滤包含其他 SKU 的 chunks
- **过滤规则**：
  - 包含当前 SKU 的 chunks → 过滤（避免冗余）
  - 包含其他 SKU 的 chunks → 过滤（防止串货）
  - 不包含任何 SKU 的 chunks → 保留（通用知识）

### 2. RAG 诊断信息

新增 `RAGDiagnostics` 数据结构：

```python
@dataclass
class RAGDiagnostics:
    retrieved_count: int      # 检索到的 chunks 总数
    filtered_count: int       # 被过滤的 chunks 数量
    safe_count: int           # 安全的 chunks 数量（最终使用）
    filter_reasons: List[str] # 过滤原因列表
```

### 3. 优雅降级

如果没有安全的 chunks：
- 返回空列表（`rag_chunks = []`）
- `rag_used = false`
- 系统继续运行，但不使用 RAG（基于产品数据生成）

### 4. Prompt Builder 强化

在 `app/services/prompt_builder.py` 中：

- **明确指示 LLM**：
  - 当前商品信息是**唯一事实来源**
  - RAG 内容仅用于表达方式或背景知识
  - **严格禁止**使用 RAG 中的价格、SKU、材质等具体信息

- **清理 RAG Context**：
  - 移除所有 SKU 标记（`[SKU:xxx]`）
  - 移除价格信息
  - 移除其他数字规格

### 5. API 响应增强

在响应中添加 `rag_diagnostics` 字段：

```json
{
    "rag_used": true,
    "rag_chunks_count": 3,
    "rag_diagnostics": {
        "retrieved_count": 6,
        "filtered_count": 3,
        "safe_count": 3,
        "filter_reasons": [
            "Chunk contains foreign SKU(s): 8WZ76CM6 (prevent cross-SKU contamination)",
            "Chunk contains current SKU 8WZ01CM1 (redundant with product data)"
        ]
    }
}
```

## 核心业务规则

1. **当前 SKU 是唯一的事实来源**
   - 所有价格、SKU、材质等信息必须来自产品数据
   - RAG 不能引入新的事实

2. **RAG 内容仅用于表达方式或背景知识**
   - 可以参考如何描述商品特点
   - 不能使用其中的具体事实信息

3. **任何包含其他 SKU 的 chunk 必须被过滤**
   - 防止串货、价格错误、材质错误

4. **如果没有安全的 chunks，系统必须优雅降级**
   - `rag_used=false`
   - 系统继续运行，基于产品数据生成

## 实现细节

### RAG Service 更新

```python
def retrieve_context(
    self,
    query: str,
    top_k: int = 3,
    current_sku: Optional[str] = None,
) -> tuple[List[str], RAGDiagnostics]:
    """
    检索相关上下文，并严格验证 SKU 所有权。
    
    返回：
        (safe_chunks, diagnostics)
    """
```

### RAG Tool 更新

```python
async def retrieve_rag(
    context: AgentContext,
    top_k: int = 3,
) -> AgentContext:
    """
    检索 RAG 上下文（严格 SKU 验证）。
    
    更新：
        context.rag_chunks = safe_chunks
        context.extra["rag_diagnostics"] = diagnostics.to_dict()
    """
```

### Prompt Builder 更新

- 添加"严格禁止事项"部分
- 明确标注"商品信息（唯一事实来源）"
- 清理 RAG context 中的所有 SKU 和价格信息

## 测试覆盖

测试文件：`tests/test_rag_sku_validation.py`

### 测试用例

1. **`test_filter_foreign_sku_chunks`**
   - 验证：包含其他 SKU 的 chunks 被过滤

2. **`test_filter_all_foreign_sku_chunks`**
   - 验证：所有 chunks 都包含其他 SKU → 全部过滤，`rag_used=false`

3. **`test_keep_chunks_without_sku`**
   - 验证：不包含任何 SKU 的 chunks 被保留（通用知识）

4. **`test_filter_current_sku_chunks`**
   - 验证：包含当前 SKU 的 chunks 被过滤（避免冗余）

5. **`test_prompt_explicitly_forbids_foreign_facts`**
   - 验证：prompt 明确禁止使用 RAG 中的事实信息

6. **`test_prompt_cleans_sku_from_rag_context`**
   - 验证：prompt 从 RAG context 中清理 SKU 标记

## 架构改进

### 之前的问题

```
RAG 检索 → 可能包含其他 SKU → LLM 混淆 → 串货/价格错误
```

### 现在的流程

```
RAG 检索 → SKU 验证过滤 → 只保留安全 chunks → 
清理 SKU/价格 → Prompt 明确指示 → LLM 基于产品数据生成
```

## 关键原则

1. **事实基础优先**：当前 SKU 是唯一事实来源
2. **防御性设计**：宁可不用 RAG，不可引入错误事实
3. **可观测性**：`rag_diagnostics` 记录所有过滤原因
4. **优雅降级**：没有安全 chunks 时，系统继续运行

## 向后兼容性

- 现有 API 调用不受影响
- 新增 `rag_diagnostics` 字段为可选（但始终返回）
- 如果没有诊断信息，使用默认值

## 后续优化建议

1. **更细粒度的过滤**：不仅过滤 SKU，还可以过滤价格范围、材质类型等
2. **RAG 质量评分**：为每个 chunk 评分，优先使用高质量 chunks
3. **缓存机制**：缓存已过滤的 chunks，避免重复过滤

