# V2.0.2 流式 LLM 集成说明

## 概述

已成功将真实的流式 LLM 客户端集成到 `/ai/generate/copy` 接口中，替换了原有的模板生成器。

## 实现内容

### 1. 流式 LLM 客户端 (`app/services/llm_client.py`)

**新增方法**：
- `async def stream_chat()`: 流式聊天方法，支持实时文本块生成

**特性**：
- ✅ OpenAI 兼容的流式 API
- ✅ 异步生成器，实时 yield 文本块
- ✅ 自动重试机制（最多 3 次，指数退避）
- ✅ 超时处理（30 秒）
- ✅ 错误恢复和容错设计
- ✅ 详细日志记录

### 2. 集成到 Copy 生成服务

**修改文件**：
- `app/services/streaming_generator.py`: 使用真实 LLM 生成文案
- `app/services/copy_service.py`: 更新模型名称记录

**工作流程**：
1. 首先尝试使用真实 LLM 生成文案
2. 如果 LLM 失败，自动回退到模板生成
3. 保持原有的 SSE 格式和结构
4. 确保第一个 chunk 在 500ms 内发出

## 使用方式

### 配置要求

在 `.env` 文件中配置 LLM API：

```env
LLM_API_KEY=sk-your-api-key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
LLM_MODEL=qwen-max
```

### 如果没有配置

如果没有配置 API Key，会自动使用模板生成（fallback），确保服务可用。

## API 行为

### 请求示例

```bash
POST /ai/generate/copy
Content-Type: application/json

{
    "sku": "8WZ01CM1",
    "style": "natural"
}
```

### 响应格式（SSE）

```
data: {"type":"start","total":3,"style":"natural"}

data: {"type":"post_start","index":1,"total":3}

data: {"type":"token","content":"今天推荐","index":1,"position":0}

data: {"type":"token","content":"这款运动鞋","index":1,"position":5}

...

data: {"type":"post_end","index":1,"content":"今天推荐这款运动鞋，舒适的设计真的很赞！..."}

data: {"type":"complete","posts":[...]}
```

## 性能指标

- **第一个 chunk 延迟**: < 500ms（通过立即发送 start 事件保证）
- **LLM 响应延迟**: 取决于 API 响应时间（通常 1-3 秒）
- **总生成时间**: 3 条文案，约 5-10 秒（取决于 LLM 响应速度）

## 错误处理

### LLM 失败场景

1. **API Key 未配置**: 自动使用模板生成
2. **网络错误**: 自动重试 3 次，失败后回退到模板
3. **API 错误**: 记录错误日志，回退到模板
4. **超时**: 记录超时日志，回退到模板

### 日志记录

- 所有 LLM 调用都会记录详细日志
- 失败时会记录错误原因
- 回退到模板时会记录警告

## 测试

### 测试流式 LLM 客户端

```bash
python test_stream_llm.py
```

### 测试 Copy 生成接口

```bash
curl -X POST http://127.0.0.1:8000/ai/generate/copy \
  -H "Content-Type: application/json" \
  -d '{"sku": "8WZ01CM1", "style": "natural"}'
```

## 优势

1. **真实 AI 生成**: 使用真实 LLM，文案更自然、多样
2. **实时流式输出**: 用户体验更好，看到实时生成过程
3. **容错设计**: LLM 失败时自动回退，确保服务可用
4. **性能优化**: 第一个 chunk 立即发送，满足延迟要求
5. **详细日志**: 便于监控和调试

## 后续优化

1. **缓存机制**: 可以缓存常见商品的文案
2. **批量生成**: 优化 3 条文案的生成顺序
3. **个性化**: 根据用户历史调整文案风格
4. **A/B 测试**: 对比 LLM 和模板的效果

