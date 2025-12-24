# 企业级运行日志 + trace_id 链路追踪使用指南

## 功能概述

本系统实现了企业级日志管理和 trace_id 链路追踪功能，用于解决多请求并发时日志混乱的问题。

### 核心特性

1. **按天滚动日志文件**
   - Info 日志：`logs/app-info-YYYY-MM-DD.log`（INFO 及以上）
   - Error 日志：`logs/app-error-YYYY-MM-DD.log`（ERROR 及以上）
   - 自动保留最近 N 天（默认 14 天）

2. **trace_id 链路追踪**
   - 每个请求自动生成或使用传入的 trace_id
   - 同一次请求的所有日志都带相同的 trace_id
   - 支持协程并发安全（使用 contextvars）

3. **响应头返回 trace_id**
   - 响应头包含 `X-Trace-Id`，便于前端/调用方关联

4. **Access Log**
   - 自动记录每个请求的 method/path/status/latency_ms/trace_id/client_ip

## 配置说明

### 环境变量配置

在 `.env` 文件中添加以下配置（可选）：

```bash
# 日志目录（默认：logs）
LOG_DIR=logs

# 日志保留天数（默认：14）
LOG_BACKUP_COUNT=14
```

### 代码配置

配置项在 `app/core/config.py` 中：

```python
log_dir: str = "logs"  # 日志目录
log_backup_count: int = 14  # 保留天数
```

## 日志格式

所有日志统一格式：

```
%(asctime)s %(levelname)s [trace_id=%(trace_id)s] %(name)s:%(lineno)d - %(message)s
```

示例：

```
2024-12-23 18:00:00 INFO [trace_id=a1b2c3d4e5f6g7h8] app.services.vision_analyze_service:125 - Vision model response received
2024-12-23 18:00:01 ERROR [trace_id=a1b2c3d4e5f6g7h8] app.core.middleware:85 - ACCESS POST /ai/product/vision_analyze status=500 latency_ms=1234 client_ip=127.0.0.1 trace_id=a1b2c3d4e5f6g7h8 error=...
```

## 使用方式

### 1. 自动生成 trace_id

不传入 `X-Trace-Id` 请求头，系统会自动生成：

```bash
curl -X POST http://127.0.0.1:8000/ai/product/vision_analyze \
  -H "Content-Type: application/json" \
  -d '{"image": "...", "brand_code": "50LY"}'
```

响应头会包含：
```
X-Trace-Id: a1b2c3d4e5f6g7h8
```

### 2. 传入自定义 trace_id

传入 `X-Trace-Id` 请求头，系统会使用该值：

```bash
curl -X POST http://127.0.0.1:8000/ai/product/vision_analyze \
  -H "Content-Type: application/json" \
  -H "X-Trace-Id: my-custom-trace-id-123" \
  -d '{"image": "...", "brand_code": "50LY"}'
```

响应头会返回相同的 trace_id：
```
X-Trace-Id: my-custom-trace-id-123
```

### 3. 在业务代码中使用

业务代码中直接使用 `logging.getLogger(__name__)`，trace_id 会自动注入：

```python
import logging

logger = logging.getLogger(__name__)

def my_service_function():
    logger.info("处理业务逻辑")  # 自动包含 trace_id
    logger.error("发生错误", exc_info=True)  # 自动包含 trace_id 和异常堆栈
```

## 日志文件说明

### Info 日志文件（app-info-YYYY-MM-DD.log）

包含所有 INFO、WARNING、ERROR 级别的日志。

用途：
- 日常运维查看
- 请求链路追踪
- 性能分析

### Error 日志文件（app-error-YYYY-MM-DD.log）

只包含 ERROR 及以上级别的日志，包含异常堆栈。

用途：
- 错误排查
- 异常分析
- 告警监控

## 验收测试

### 测试 1：并发请求 trace_id 隔离

同时发送两个请求：

```bash
# 终端 1
curl -X POST http://127.0.0.1:8000/ai/product/vision_analyze \
  -H "Content-Type: application/json" \
  -d '{"image": "...", "brand_code": "50LY"}' \
  -v 2>&1 | grep X-Trace-Id

# 终端 2（同时执行）
curl -X POST http://127.0.0.1:8000/ai/product/similar_skus \
  -H "Content-Type: application/json" \
  -d '{"brand_code": "50LY", "trace_id": "test-123"}' \
  -v 2>&1 | grep X-Trace-Id
```

检查日志文件，确认两个请求的日志 trace_id 不同且不串。

### 测试 2：正常请求日志分离

发送一个正常请求：

```bash
curl -X GET http://127.0.0.1:8000/health
```

检查：
- `logs/app-info-YYYY-MM-DD.log` 有记录
- `logs/app-error-YYYY-MM-DD.log` 无记录（除非有 ERROR）

### 测试 3：异常请求日志分离

发送一个会报错的请求：

```bash
curl -X POST http://127.0.0.1:8000/ai/product/vision_analyze \
  -H "Content-Type: application/json" \
  -d '{"image": "invalid", "brand_code": "50LY"}'
```

检查：
- `logs/app-info-YYYY-MM-DD.log` 有记录（包含请求日志）
- `logs/app-error-YYYY-MM-DD.log` 有记录（包含错误堆栈）
- 两个文件的 trace_id 一致

### 测试 4：trace_id 传播

发送请求并记录 trace_id：

```bash
TRACE_ID=$(curl -X POST http://127.0.0.1:8000/ai/product/vision_analyze \
  -H "Content-Type: application/json" \
  -d '{"image": "...", "brand_code": "50LY"}' \
  -v 2>&1 | grep -i "x-trace-id" | awk '{print $3}')

echo "Trace ID: $TRACE_ID"
```

在日志文件中搜索该 trace_id：

```bash
grep "$TRACE_ID" logs/app-info-*.log
```

确认该请求的所有日志（包括 service/repo 等子模块）都包含相同的 trace_id。

## 故障排查

### 问题 1：日志文件未生成

检查：
1. `logs/` 目录是否存在且有写权限
2. 查看控制台是否有初始化日志输出
3. 检查 `app/core/config.py` 中的 `log_dir` 配置

### 问题 2：trace_id 为 N/A

原因：在中间件之外或初始化之前使用了 logger。

解决：确保所有日志调用都在 FastAPI 请求生命周期内。

### 问题 3：并发请求 trace_id 串了

原因：未使用 contextvars 或中间件未正确设置。

解决：检查 `app/core/trace_context.py` 和 `app/core/middleware.py` 实现。

## 技术实现

### 架构设计

1. **trace_context.py**: 使用 `contextvars.ContextVar` 存储 trace_id（协程安全）
2. **logging_config.py**: 配置日志系统，使用 `TraceIdFilter` 注入 trace_id
3. **middleware.py**: FastAPI 中间件，处理请求头并设置 trace_id
4. **main.py**: 应用启动时初始化日志系统

### 关键点

- **协程安全**: 使用 `contextvars` 而非线程局部变量
- **自动注入**: 通过 `TraceIdFilter` 自动为每条日志注入 trace_id
- **文件分离**: 使用不同的 handler 和 filter 实现 info/error 分离
- **按天滚动**: 使用 `TimedRotatingFileHandler` 实现日志滚动

## 后续优化建议

1. **支持 span_id**: 在 trace_id 基础上增加 span_id，实现更细粒度的追踪
2. **日志聚合**: 集成 ELK/EFK 等日志聚合系统
3. **性能监控**: 基于 access log 实现性能监控和告警
4. **业务字段**: 支持在日志中额外记录 brand_code/user_id 等业务字段

