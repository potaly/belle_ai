# 流式 LLM 客户端使用指南

## 概述

`LLMClient.stream_chat()` 方法实现了 OpenAI 兼容的流式聊天接口，支持实时接收 LLM 响应文本块。

## 功能特性

- ✅ **OpenAI 兼容**：支持 OpenAI 格式的流式 API
- ✅ **实时流式输出**：使用异步生成器，实时产生文本块
- ✅ **错误恢复**：自动重试机制（最多 3 次，指数退避）
- ✅ **超时处理**：30 秒超时保护
- ✅ **容错设计**：单个 chunk 错误不会导致整个请求失败
- ✅ **详细日志**：记录请求、响应和性能指标

## 使用方法

### 基本用法

```python
from app.services.llm_client import get_llm_client

async def example():
    client = get_llm_client()
    
    async for chunk in client.stream_chat("请介绍运动鞋的特点"):
        print(chunk, end="", flush=True)
    print()  # 换行
```

### 完整示例

```python
import asyncio
from app.services.llm_client import get_llm_client

async def stream_example():
    client = get_llm_client()
    
    prompt = "请用一句话介绍运动鞋的特点"
    
    full_response = ""
    async for chunk in client.stream_chat(
        prompt,
        system="你是一个专业的鞋类销售顾问。",
        temperature=0.7,
        max_tokens=200,
    ):
        # 实时输出
        print(chunk, end="", flush=True)
        full_response += chunk
    
    print(f"\n完整响应: {full_response}")

# 运行
asyncio.run(stream_example())
```

### 在 FastAPI 中使用

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from app.services.llm_client import get_llm_client

app = FastAPI()

@app.post("/ai/stream")
async def stream_llm(prompt: str):
    """流式 LLM 响应接口"""
    client = get_llm_client()
    
    async def generate():
        async for chunk in client.stream_chat(prompt):
            yield f"data: {chunk}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
```

## 参数说明

### `stream_chat()` 方法参数

- **prompt** (str, 必需): 用户输入的提示文本
- **system** (str, 可选): 系统消息，默认 "You are a helpful sales assistant."
- **temperature** (float, 可选): 温度参数，控制输出随机性
- **max_tokens** (int, 可选): 最大生成 token 数
- **其他参数**: 支持透传其他 OpenAI 兼容参数

### 返回值

- **AsyncGenerator[str, None]**: 异步生成器，每次 yield 一个文本块

## 错误处理

### 自动重试

- 最多重试 3 次
- 指数退避策略：0.5s, 1s, 2s
- 自动处理网络错误、超时、HTTP 错误

### 错误类型

- `LLMClientError`: LLM 相关错误（API 错误、超时等）
- 单个 chunk 解析错误不会中断整个流，只会记录警告

## 配置要求

### 环境变量

在 `.env` 文件中配置：

```env
# LLM API 配置
LLM_API_KEY=sk-your-api-key-here
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
LLM_MODEL=qwen-max
```

### 如果没有配置

如果没有配置 API Key 和 URL，会自动使用 stub 模式：
- 返回模拟的流式响应
- 不会调用真实 API
- 用于开发和测试

## 性能指标

客户端会自动记录：
- 第一个 chunk 的延迟时间
- 总 chunk 数量
- 总字符数
- 总耗时

日志示例：
```
[INFO] First chunk received: 运动鞋具有舒适... (245.32ms)
[INFO] LLM stream completed: 15 chunks, 128.0 chars, 1234.56 ms
```

## 测试

运行测试脚本：

```bash
python test_stream_llm.py
```

## 注意事项

1. **流式格式**：支持 Server-Sent Events (SSE) 格式
2. **JSON 解析**：自动处理 `data: {...}` 前缀
3. **[DONE] 信号**：自动识别并停止流式接收
4. **编码处理**：自动处理 UTF-8 编码，忽略无效字符
5. **资源管理**：使用 `async with` 确保连接正确关闭

## 兼容性

- ✅ OpenAI API
- ✅ 阿里百炼（OpenAI 兼容模式）
- ✅ 其他 OpenAI 兼容的 API 服务

