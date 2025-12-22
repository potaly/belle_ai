# P-ETL-2 实现计划

## A. 仓库相关文件定位

### A1. 现有相关文件

#### 模型层
- `app/models/product.py` - Product 模型（需要修改：添加 brand_code，修改唯一约束）
- `app/models/__init__.py` - 模型导出

#### Repository 层
- `app/repositories/product_repository.py` - Product 查询方法（需要扩展）
- `app/repositories/__init__.py` - Repository 导出

#### Service 层
- `app/services/product_service.py` - 商品分析服务（不影响）
- `app/services/__init__.py` - Service 导出

#### 工具层
- `app/utils/__init__.py` - 工具函数导出

#### 数据库配置
- `app/core/database.py` - 数据库连接和 SessionLocal
- `app/core/config.py` - 配置管理

#### SQL 文件
- `sql/schema.sql` - 数据库表结构定义（需要添加新表）

#### 测试文件
- `tests/` - 测试目录（需要添加 ETL 相关测试）

### A2. 数据库表状态

#### 已存在表
- `belle_ai.products` - 目标表（需要修改唯一约束）
- `belle_ai.products_staging` - 源表（DBA 已准备，只读使用）

#### 需要创建的表
- `belle_ai.product_change_log` - 变更日志表
- `belle_ai.etl_watermark` - ETL 水位表

---

## B. 新增 / 修改文件清单

### B1. 新增文件（7 个）

#### 模型层（3 个）
1. `app/models/product_staging.py` - ProductStaging 模型
2. `app/models/product_change_log.py` - ProductChangeLog 模型
3. `app/models/etl_watermark.py` - ETLWatermark 模型

#### Repository 层（1 个）
4. `app/repositories/product_staging_repository.py` - ProductStagingRepository（分批查询）

#### Service 层（3 个）
5. `app/services/product_normalizer.py` - ProductNormalizer（JSON 规范化）
6. `app/services/data_version_calculator.py` - DataVersionCalculator（data_version 计算）
7. `app/services/product_upsert_service.py` - ProductUpsertService（upsert 逻辑）

#### 工具层（1 个）
8. `app/utils/json_utils.py` - JSON 工具函数（稳定序列化）

#### Worker/Script（1 个）
9. `app/agents/workers/etl_product_worker.py` - ETL 主流程 Worker

#### 测试文件（3 个）
10. `tests/test_product_normalizer.py` - ProductNormalizer 测试
11. `tests/test_data_version_calculator.py` - DataVersionCalculator 测试
12. `tests/test_product_upsert_service.py` - ProductUpsertService 测试

### B2. 修改文件（4 个）

#### 模型层（1 个）
1. `app/models/product.py` - 添加 `brand_code` 字段，修改唯一约束为 `(brand_code, sku)`

#### Repository 层（1 个）
2. `app/repositories/product_repository.py` - 添加 `get_product_by_brand_sku` 方法

#### SQL 文件（1 个）
3. `sql/schema.sql` - 添加新表定义和 Product 表修改

#### 导出文件（1 个）
4. `app/models/__init__.py` - 导出新模型
5. `app/repositories/__init__.py` - 导出新 Repository
6. `app/services/__init__.py` - 导出新 Service

---

## C. 分批消费策略说明

### C1. 设计目标

- ✅ **避免内存溢出**: 不一次性加载全表数据
- ✅ **避免事务过大**: 每批处理完成后提交事务
- ✅ **支持断点续跑**: 基于 `etl_watermark` 记录进度
- ✅ **支持限流**: 通过 `--limit` 参数控制每批处理量

### C2. 分批策略：基于 src_updated_at 的游标方式

#### 为什么选择游标而非 OFFSET？

**OFFSET 的问题**:
- 当数据量大时，`OFFSET N` 需要扫描前 N 条记录，性能随偏移量线性下降
- 如果 staging 表在 ETL 过程中有新数据插入，可能导致重复处理或遗漏

**游标的优势**:
- 基于 `src_updated_at` 时间戳，性能稳定
- 支持增量同步：只处理 `src_updated_at > watermark` 的数据
- 支持断点续跑：从上次的 `src_updated_at` 继续

#### 实现方式

```python
# 伪代码示例
def fetch_batch(db: Session, watermark: datetime, limit: int):
    """
    基于 watermark 游标查询下一批数据
    
    策略：
    1. 查询 src_updated_at > watermark 的记录
    2. 按 src_updated_at ASC 排序（保证顺序）
    3. LIMIT N 条
    4. 返回数据和本批次最大 src_updated_at
    """
    query = db.query(ProductStaging).filter(
        ProductStaging.src_updated_at > watermark
    ).order_by(
        ProductStaging.src_updated_at.asc()
    ).limit(limit)
    
    records = query.all()
    max_updated_at = max(r.src_updated_at for r in records) if records else watermark
    
    return records, max_updated_at
```

### C3. 断点续跑机制

#### watermark 表设计
```sql
CREATE TABLE etl_watermark (
    id INT PRIMARY KEY AUTO_INCREMENT,
    table_name VARCHAR(64) NOT NULL UNIQUE COMMENT '表名',
    last_processed_at DATETIME NOT NULL COMMENT '最后处理时间',
    last_processed_id BIGINT NULL COMMENT '最后处理记录ID（可选）',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

#### 工作流程
1. **首次运行**: `watermark = '1970-01-01 00:00:00'`（或表的最小 `src_updated_at`）
2. **处理一批**: 查询 `src_updated_at > watermark` 的记录
3. **更新 watermark**: 本批次处理完成后，更新为 `max(src_updated_at)`
4. **断点续跑**: 下次运行时从 `etl_watermark` 读取上次的 `last_processed_at`

### C4. 事务边界设计

#### 每批一个事务
```python
# 伪代码
for batch in batches:
    db.begin()
    try:
        # 1. 查询本批数据
        records = fetch_batch(db, watermark, limit)
        
        # 2. 处理每条记录
        for record in records:
            # 规范化、计算版本、upsert、写 change_log
            process_record(db, record)
        
        # 3. 更新 watermark
        update_watermark(db, max_updated_at)
        
        # 4. 提交事务
        db.commit()
    except Exception as e:
        db.rollback()
        raise
```

#### 为什么每批一个事务？
- ✅ **避免长事务**: 不会长时间锁定表
- ✅ **支持断点续跑**: 失败后可以从上次成功的位置继续
- ✅ **降低回滚成本**: 只回滚当前批次，不影响已处理的数据

### C5. 内存控制

#### 批次大小建议
- **默认**: `limit=1000`（可通过 `--limit` 调整）
- **小数据量**: `limit=500`（如果单条记录很大）
- **大数据量**: `limit=2000`（如果单条记录较小）

#### 内存估算
假设单条记录约 2KB：
- `limit=1000`: 约 2MB 内存
- `limit=2000`: 约 4MB 内存

### C6. 命令行参数设计

```python
# 示例命令行
python -m app.agents.workers.etl_product_worker \
    --limit 1000 \
    --resume \
    --dry-run  # 可选：仅验证不写入
```

- `--limit N`: 每批处理 N 条记录（默认 1000）
- `--resume`: 从 watermark 继续（默认开启）
- `--dry-run`: 仅验证数据，不写入数据库

---

## 下一步

完成 A/B 部分后，将开始实现：
1. 数据库模型（ProductStaging, ProductChangeLog, ETLWatermark）
2. Repository 层（分批查询）
3. Service 层（规范化、版本计算、upsert）
4. Worker 主流程

