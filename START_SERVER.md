# 服务启动指南

## 快速启动

### 方法 1: 使用 uvicorn 命令（推荐）
```bash
uvicorn app.main:app --reload
```

### 方法 2: 使用启动脚本
```bash
python start_server.py
```

### 方法 3: 直接运行 main.py
```bash
python -m app.main
```

## 验证服务

服务启动后，访问以下端点验证：

1. **根端点**: http://127.0.0.1:8000/
   - 返回应用信息

2. **健康检查**: http://127.0.0.1:8000/health
   - 返回服务状态

3. **API v1 根**: http://127.0.0.1:8000/api/v1/
   - 返回 API 版本信息

4. **Ping 端点**: http://127.0.0.1:8000/api/v1/ping
   - 返回 BaseResponse 格式的响应

5. **API 文档**: http://127.0.0.1:8000/docs
   - Swagger UI 自动生成的 API 文档

## 使用验证脚本

运行验证脚本测试所有端点：
```bash
python verify_service.py
```

## 项目结构

```
app/
├── main.py              # FastAPI 应用入口
├── core/
│   ├── config.py       # 配置管理（Pydantic BaseSettings）
│   └── database.py     # SQLAlchemy 2.0 数据库配置
├── models/             # ORM 模型
│   ├── product.py
│   ├── guide.py
│   ├── user_behavior_log.py
│   └── ai_task_log.py
├── api/
│   └── v1/
│       └── router.py   # API v1 路由
└── schemas/
    └── base_schemas.py # 基础响应模型
```

## 环境变量

确保 `.env` 文件包含：
```env
DATABASE_URL=mysql+pymysql://root:password@localhost:3306/belle_ai?charset=utf8mb4
APP_NAME=AI Smart Guide Service
APP_VERSION=1.0.0
```

## 故障排查

如果服务无法启动：

1. 检查 Python 版本（需要 3.10+）
2. 检查依赖是否安装：`pip install -r requirements.txt`
3. 检查数据库连接配置
4. 查看错误日志

