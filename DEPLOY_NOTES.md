# Docker 部署注意事项清单

## 一、避免端口冲突

### 1.1 检查端口占用

**部署前必须执行：**
```bash
# 检查默认端口 18000
netstat -tuln | grep 18000
ss -tuln | grep 18000

# 检查 MySQL 端口（如使用容器）
netstat -tuln | grep 3307

# 检查 Redis 端口（如使用容器）
netstat -tuln | grep 6379
```

**如果端口被占用：**
- 修改 `.env` 中的 `APP_PORT`（例如改为 `18001`）
- 修改 `.env` 中的 `MYSQL_PORT`（例如改为 `3308`）
- 修改 `.env` 中的 `REDIS_PORT`（例如改为 `6380`）

### 1.2 端口映射规则

- **应用端口：** `宿主机端口:容器内端口` = `${APP_PORT}:8000`
- **MySQL 端口：** `${MYSQL_PORT}:3306`（仅使用 mysql profile 时）
- **Redis 端口：** `${REDIS_PORT}:6379`（仅使用 redis profile 时）

## 二、避免容器名冲突

### 2.1 检查现有容器

```bash
# 检查容器名是否冲突
docker ps -a | grep belle-ai

# 如果存在冲突，修改 docker-compose.yml 中的 container_name
```

**默认容器名：**
- `belle-ai-service`（主应用）
- `belle-ai-mysql`（MySQL，仅使用 profile 时）
- `belle-ai-redis`（Redis，仅使用 profile 时）

### 2.2 修改容器名

在 `docker-compose.yml` 中修改：
```yaml
services:
  belle-ai-service:
    container_name: belle-ai-service-prod  # 修改为唯一名称
```

## 三、避免网络名冲突

### 3.1 检查现有网络

```bash
# 检查网络名是否冲突
docker network ls | grep belle_ai_net

# 如果存在冲突，修改 docker-compose.yml 中的网络名称
```

### 3.2 修改网络名

在 `docker-compose.yml` 中修改：
```yaml
networks:
  belle_ai_net:
    name: belle_ai_net_prod  # 修改为唯一名称
    driver: bridge
```

## 四、资源限制配置

### 4.1 当前资源限制

在 `docker-compose.yml` 中已配置：
```yaml
deploy:
  resources:
    limits:
      cpus: '2'        # 最大 2 核
      memory: 2G       # 最大 2GB 内存
    reservations:
      cpus: '0.5'      # 保留 0.5 核
      memory: 512M     # 保留 512MB 内存
```

### 4.2 调整资源限制

**根据服务器资源情况调整：**

```yaml
# 低配置服务器（1核2G）
deploy:
  resources:
    limits:
      cpus: '1'
      memory: 1G
    reservations:
      cpus: '0.25'
      memory: 256M

# 高配置服务器（4核8G）
deploy:
  resources:
    limits:
      cpus: '4'
      memory: 4G
    reservations:
      cpus: '1'
      memory: 1G
```

### 4.3 移除资源限制（不推荐）

如果服务器资源充足且需要最大性能：
```yaml
# 注释掉或删除 deploy 部分
# deploy:
#   resources:
#     ...
```

## 五、数据持久化

### 5.1 日志持久化

**已配置：**
```yaml
volumes:
  - ./logs:/app/logs
```

**注意：**
- 日志文件会保存在宿主机的 `./logs` 目录
- 确保目录有写入权限：`chmod 755 logs/`
- 定期清理旧日志文件

### 5.2 MySQL 数据持久化（使用容器时）

**已配置：**
```yaml
volumes:
  mysql_data:/var/lib/mysql
```

**数据位置：**
- Docker volume: `belle_ai_mysql_data`
- 查看：`docker volume inspect belle_ai_mysql_data`

### 5.3 Redis 数据持久化（使用容器时）

**已配置：**
```yaml
volumes:
  redis_data:/data
```

**数据位置：**
- Docker volume: `belle_ai_redis_data`
- 查看：`docker volume inspect belle_ai_redis_data`

## 六、环境变量安全

### 6.1 敏感信息管理

**不要提交到 Git：**
- `.env` 文件（已在 `.gitignore` 中）
- 包含真实密钥的配置文件

**使用环境变量：**
- 所有敏感信息通过 `.env` 文件注入
- 生产环境建议使用 Docker secrets 或 K8s secrets

### 6.2 环境变量优先级

1. `.env` 文件（docker-compose.yml 中的 env_file）
2. `docker-compose.yml` 中的 environment
3. 系统环境变量

## 七、网络隔离

### 7.1 独立网络

**已配置：**
```yaml
networks:
  belle_ai_net:
    name: belle_ai_net
    driver: bridge
```

**优势：**
- 与其他 Docker 应用网络隔离
- 容器间可通过服务名通信
- 不影响宿主机网络

### 7.2 访问外部服务

**访问宿主机服务：**
- Linux: 使用宿主机 IP 地址
- Mac/Windows: 使用 `host.docker.internal`

**示例：**
```env
# 访问宿主机 MySQL
DATABASE_URL=mysql+pymysql://user:pass@192.168.1.100:3306/belle_ai?charset=utf8mb4
```

## 八、健康检查配置

### 8.1 应用健康检查

**已配置：**
```yaml
healthcheck:
  test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()"]
  interval: 30s      # 每 30 秒检查一次
  timeout: 10s       # 超时 10 秒
  retries: 3         # 失败 3 次后标记为不健康
  start_period: 40s  # 启动后 40 秒内不检查
```

### 8.2 查看健康状态

```bash
# 查看容器健康状态
docker compose ps

# 查看健康检查日志
docker inspect belle-ai-service | grep -A 10 Health
```

## 九、日志查看

### 9.1 Docker Compose 日志

```bash
# 实时查看日志
docker compose logs -f belle-ai-service

# 查看最近 100 行
docker compose logs --tail=100 belle-ai-service

# 查看错误日志
docker compose logs belle-ai-service | grep ERROR
```

### 9.2 应用日志文件

```bash
# 查看 info 日志
tail -f logs/app-info.log

# 查看 error 日志
tail -f logs/app-error.log

# 搜索特定 trace_id
grep "trace_id=xxx" logs/app-info.log
```

## 十、备份与恢复

### 10.1 备份数据库（使用容器时）

```bash
# 备份 MySQL 数据
docker compose exec mysql mysqldump -u root -p belle_ai > backup_$(date +%Y%m%d).sql

# 或备份 volume
docker run --rm -v belle_ai_mysql_data:/data -v $(pwd):/backup alpine tar czf /backup/mysql_backup_$(date +%Y%m%d).tar.gz /data
```

### 10.2 备份日志

```bash
# 压缩日志目录
tar czf logs_backup_$(date +%Y%m%d).tar.gz logs/
```

## 十一、清理资源

### 11.1 清理容器和网络

```bash
# 停止并删除容器、网络
docker compose down

# 同时删除 volumes（谨慎使用，会删除数据）
docker compose down -v
```

### 11.2 清理镜像

```bash
# 删除未使用的镜像
docker image prune -a

# 删除特定镜像
docker rmi belle-ai-service:latest
```

## 十二、故障恢复

### 12.1 容器异常退出

```bash
# 查看退出原因
docker compose logs belle-ai-service

# 重启服务
docker compose restart belle-ai-service

# 强制重建
docker compose up -d --force-recreate belle-ai-service
```

### 12.2 数据库连接失败

```bash
# 测试数据库连接
docker compose exec belle-ai-service python -c "
from app.core.database import engine
from sqlalchemy import text
with engine.connect() as conn:
    result = conn.execute(text('SELECT 1'))
    print('OK')
"

# 检查网络连接
docker compose exec belle-ai-service ping mysql
```

## 十三、性能优化建议

### 13.1 数据库连接池

已在 `app/core/database.py` 中配置连接池，无需额外配置。

### 13.2 日志轮转

已在 `app/core/logging_config.py` 中配置按天滚动，保留 14 天。

### 13.3 缓存策略

如使用 Redis，确保 `REDIS_URL` 配置正确。

## 十四、安全检查清单

- [ ] 修改默认密码（MySQL root 密码）
- [ ] 限制数据库访问 IP
- [ ] 使用 HTTPS（生产环境）
- [ ] 定期更新依赖包
- [ ] 监控异常访问
- [ ] 备份重要数据
- [ ] 配置防火墙规则
- [ ] 使用非 root 用户运行（已配置）

