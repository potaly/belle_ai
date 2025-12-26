# 部署说明

## 一、服务器准备

### 1.1 检查 Docker 环境

```bash
# 检查 Docker 版本（需要 20.10+）
docker --version

# 检查 Docker Compose 版本（需要 2.0+）
docker compose version

# 如果未安装，参考官方文档：
# https://docs.docker.com/engine/install/
# https://docs.docker.com/compose/install/
```

### 1.2 检查端口占用

```bash
# 检查默认端口 18000 是否被占用
netstat -tuln | grep 18000
# 或
ss -tuln | grep 18000

# 如果被占用，修改 .env 中的 APP_PORT 值
```

### 1.3 检查网络冲突

```bash
# 检查网络名称是否冲突
docker network ls | grep belle_ai_net

# 如果存在冲突，修改 docker-compose.yml 中的网络名称
```

## 二、上传项目到服务器

### 2.1 方式一：Git Clone（推荐）

```bash
# 在服务器上克隆项目
cd /opt  # 或其他合适目录
git clone <your-repo-url> belle-ai-service
cd belle-ai-service
```

### 2.2 方式二：SCP 上传

```bash
# 在本地打包（排除不必要的文件）
tar --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.venv' \
    --exclude='logs' \
    --exclude='vector_store' \
    -czf belle-ai-service.tar.gz .

# 上传到服务器
scp belle-ai-service.tar.gz user@server:/opt/
ssh user@server
cd /opt
tar -xzf belle-ai-service.tar.gz -C belle-ai-service
cd belle-ai-service
```

## 三、配置环境变量

### 3.1 创建 .env 文件

```bash
# 复制模板文件
cp .env.example .env

# 编辑 .env 文件
vim .env  # 或使用 nano/vi
```

### 3.2 填写关键配置

**必须配置：**
- `DATABASE_URL`: 数据库连接字符串
- `APP_PORT`: 应用端口（默认 18000）

**可选配置：**
- `REDIS_URL`: Redis 连接（如使用缓存）
- `LLM_API_KEY`: LLM API 密钥
- `VISION_API_KEY`: Vision API 密钥

### 3.3 数据库连接配置示例

**使用外部 MySQL（推荐）：**
```env
DATABASE_URL=mysql+pymysql://username:password@192.168.1.100:3306/belle_ai?charset=utf8mb4
```

**使用 Docker 容器中的 MySQL：**
```env
DATABASE_URL=mysql+pymysql://belle_user:belle_password@mysql:3306/belle_ai?charset=utf8mb4
```

**注意：** 如果 MySQL 在宿主机上，使用 `host.docker.internal`（Mac/Windows）或宿主机 IP（Linux）。

## 四、启动服务

### 4.1 仅启动应用（使用外部 MySQL/Redis）

```bash
# 构建镜像
docker compose build

# 启动服务
docker compose up -d

# 查看日志
docker compose logs -f belle-ai-service
```

### 4.2 启动应用 + MySQL 容器

```bash
# 启动应用和 MySQL
docker compose --profile mysql up -d

# 查看所有服务状态
docker compose ps
```

### 4.3 启动应用 + MySQL + Redis

```bash
# 启动所有服务
docker compose --profile mysql --profile redis up -d
```

## 五、常用操作命令

### 5.1 服务管理

```bash
# 启动服务
docker compose up -d

# 停止服务
docker compose down

# 重启服务
docker compose restart belle-ai-service

# 查看服务状态
docker compose ps

# 查看日志（实时）
docker compose logs -f belle-ai-service

# 查看日志（最近 100 行）
docker compose logs --tail=100 belle-ai-service
```

### 5.2 更新服务

```bash
# 拉取最新代码
git pull  # 或重新上传代码

# 重新构建镜像
docker compose build --no-cache

# 重启服务
docker compose up -d --force-recreate belle-ai-service
```

### 5.3 进入容器调试

```bash
# 进入容器
docker compose exec belle-ai-service /bin/bash

# 查看应用日志（容器内）
tail -f /app/logs/app-info.log

# 测试健康检查
curl http://localhost:8000/health
```

## 六、验证部署

### 6.1 健康检查

```bash
# 检查容器健康状态
docker compose ps

# 手动测试健康端点
curl http://localhost:18000/health
# 或
curl http://<server-ip>:18000/health
```

预期响应：
```json
{"status": "ok", "version": "5.3.0"}
```

### 6.2 访问 API 文档

在浏览器中访问：
```
http://<server-ip>:18000/docs
```

### 6.3 测试 API 端点

```bash
# 测试根端点
curl http://<server-ip>:18000/

# 测试健康检查
curl http://<server-ip>:18000/health
```

## 七、常见问题排查

### 7.1 端口占用

**问题：** 容器启动失败，提示端口已被占用

**解决：**
```bash
# 检查端口占用
netstat -tuln | grep 18000

# 修改 .env 中的 APP_PORT
# 例如改为 18001
APP_PORT=18001

# 重启服务
docker compose up -d
```

### 7.2 容器无法启动

**问题：** 容器一直重启或无法启动

**排查：**
```bash
# 查看容器日志
docker compose logs belle-ai-service

# 查看容器状态
docker compose ps

# 进入容器检查
docker compose exec belle-ai-service /bin/bash
```

**常见原因：**
- 环境变量配置错误
- 数据库连接失败
- 依赖包安装失败

### 7.3 无法连接数据库

**问题：** 应用报错 "Can't connect to MySQL server"

**排查：**
```bash
# 检查数据库连接配置
docker compose exec belle-ai-service env | grep DATABASE_URL

# 测试数据库连接（从容器内）
docker compose exec belle-ai-service python -c "
from sqlalchemy import create_engine
import os
engine = create_engine(os.getenv('DATABASE_URL'))
conn = engine.connect()
print('Database connection OK')
"
```

**解决：**
- 确认 `DATABASE_URL` 格式正确
- 确认数据库服务可访问（防火墙、网络）
- 如使用宿主机 MySQL，Linux 需使用宿主机 IP 而非 `host.docker.internal`

### 7.4 CORS 错误

**问题：** 前端调用 API 时出现 CORS 错误

**解决：**
- 检查 `app/main.py` 中的 CORS 配置
- 确认允许的源地址包含前端域名

### 7.5 /docs 访问失败

**问题：** 无法访问 Swagger 文档

**排查：**
```bash
# 检查服务是否运行
docker compose ps

# 检查端口映射
docker compose port belle-ai-service 8000

# 检查防火墙
sudo ufw status
```

**解决：**
- 确认防火墙开放端口：`sudo ufw allow 18000/tcp`
- 确认服务正常运行：`docker compose ps`
- 检查浏览器控制台错误信息

### 7.6 日志文件权限问题

**问题：** 日志文件无法写入

**解决：**
```bash
# 检查日志目录权限
ls -la logs/

# 修复权限（如需要）
sudo chown -R $USER:$USER logs/
chmod -R 755 logs/
```

### 7.7 资源不足

**问题：** 容器因内存不足被杀死

**解决：**
- 调整 `docker-compose.yml` 中的资源限制
- 或移除资源限制（不推荐生产环境）

## 八、演示访问地址

部署成功后，可通过以下地址访问：

- **API 文档（Swagger）：** `http://<server-ip>:18000/docs`
- **健康检查：** `http://<server-ip>:18000/health`
- **根端点：** `http://<server-ip>:18000/`

**示例：**
```
http://192.168.1.100:18000/docs
http://demo.example.com:18000/docs
```

## 九、生产环境建议

1. **使用 HTTPS：** 配置 Nginx 反向代理，启用 SSL
2. **日志收集：** 配置日志收集系统（ELK、Loki 等）
3. **监控告警：** 配置 Prometheus + Grafana
4. **备份策略：** 定期备份数据库和日志
5. **安全加固：** 限制容器网络访问，使用 secrets 管理密钥

