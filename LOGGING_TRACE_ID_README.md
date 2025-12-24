# 企业级运行日志 + trace_id 链路追踪 - 快速验收指南

## 快速开始

### 1. 启动服务

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

服务启动后会自动：
- 创建 `logs/` 目录（如果不存在）
- 初始化日志系统
- 注册 TraceIdMiddleware

### 2. 发送测试请求

#### 测试 1：自动生成 trace_id

```bash
curl -X GET http://127.0.0.1:8000/health -v
```

检查响应头：
```
< X-Trace-Id: a1b2c3d4e5f6g7h8
```

#### 测试 2：传入自定义 trace_id

```bash
curl -X GET http://127.0.0.1:8000/health \
  -H "X-Trace-Id: my-custom-trace-123" \
  -v
```

检查响应头应返回相同的 trace_id。

#### 测试 3：并发请求（验证 trace_id 隔离）

```bash
# 终端 1
curl -X GET http://127.0.0.1:8000/health -v 2>&1 | grep X-Trace-Id

# 终端 2（同时执行）
curl -X GET http://127.0.0.1:8000/health -v 2>&1 | grep X-Trace-Id
```

两个请求的 trace_id 应该不同。

### 3. 检查日志文件

#### 查看日志目录

```bash
# Windows PowerShell
Get-ChildItem logs -Filter "*.log"

# Linux/Mac
ls -lh logs/*.log
```

应该看到：
- `app-info.log` - 当前 info 日志文件
- `app-error.log` - 当前 error 日志文件（如果无错误可能为空）

#### 查看日志内容

```bash
# Windows PowerShell
Get-Content logs/app-info.log -Tail 20

# Linux/Mac
tail -20 logs/app-info.log
```

日志格式示例：
```
2024-12-24 17:30:00 INFO [trace_id=a1b2c3d4e5f6g7h8] app.core.middleware:85 - ACCESS GET /health status=200 latency_ms=5 client_ip=127.0.0.1 trace_id=a1b2c3d4e5f6g7h8
```

### 4. 运行自动化验收测试

```bash
python test_logging_trace_id.py
```

测试会验证：
- ✓ 并发请求 trace_id 隔离
- ✓ 正常请求日志分离（info 有，error 无）
- ✓ 异常请求日志分离（info 有，error 有）
- ✓ trace_id 传播（同一次请求的所有日志都带相同 trace_id）
- ✓ 自定义 trace_id 支持

## 验收标准检查清单

- [ ] **日志文件生成**
  - [ ] `logs/app-info.log` 存在
  - [ ] `logs/app-error.log` 存在（可能为空）

- [ ] **trace_id 功能**
  - [ ] 响应头包含 `X-Trace-Id`
  - [ ] 日志中每条记录都包含 `trace_id=xxx`
  - [ ] 并发请求的 trace_id 不同

- [ ] **日志分离**
  - [ ] 正常请求：info 日志有记录，error 日志无记录
  - [ ] 异常请求：info 日志有记录，error 日志也有记录（含堆栈）

- [ ] **日志格式**
  - [ ] 包含时间戳
  - [ ] 包含日志级别
  - [ ] 包含 trace_id
  - [ ] 包含模块名和行号
  - [ ] 包含日志消息

- [ ] **自定义 trace_id**
  - [ ] 传入 `X-Trace-Id` 请求头，响应头返回相同值
  - [ ] 日志中使用传入的 trace_id

## 常见问题

### Q: 日志文件未生成？

A: 检查：
1. `logs/` 目录是否有写权限
2. 查看控制台是否有初始化日志输出
3. 确认服务已启动并处理过请求

### Q: trace_id 显示为 N/A？

A: 可能原因：
1. 在中间件之外使用了 logger（如模块导入时）
2. contextvar 未正确设置

### Q: 日志文件命名不是 app-info-YYYY-MM-DD.log？

A: TimedRotatingFileHandler 会在午夜滚动时重命名。当前文件始终是 `app-info.log`，滚动后的历史文件会是 `app-info.log.2024-12-24` 格式（通过 namer 函数转换为 `app-info-2024-12-24.log`）。

## 配置说明

### 环境变量（可选）

在 `.env` 文件中添加：

```bash
LOG_DIR=logs              # 日志目录（默认：logs）
LOG_BACKUP_COUNT=14       # 保留天数（默认：14）
```

### 代码配置

在 `app/core/config.py` 中：

```python
log_dir: str = "logs"
log_backup_count: int = 14
```

## 技术实现

- **trace_id 存储**: `contextvars.ContextVar`（协程安全）
- **日志注入**: `TraceIdFilter`（自动为每条日志注入 trace_id）
- **中间件**: `TraceIdMiddleware`（处理请求头并设置 trace_id）
- **文件滚动**: `TimedRotatingFileHandler`（按天滚动）

## 文件清单

### 新增文件
- `app/core/trace_context.py` - trace_id 上下文管理
- `app/core/logging_config.py` - 日志配置
- `app/core/middleware.py` - TraceIdMiddleware
- `test_logging_trace_id.py` - 验收测试脚本
- `docs/logging_trace_id_guide.md` - 详细使用文档

### 修改文件
- `app/main.py` - 集成日志初始化和中间件
- `app/core/config.py` - 添加日志配置项

