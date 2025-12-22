# brand_code 字段修复计划（P-ETL-2 最小改动版）

**修复目标**: 在现有代码基础上添加 `brand_code` 支持，确保 ETL 写入与查询键为 `(brand_code, sku)`

**修复原则**: 
- ✅ 不推倒重写
- ✅ 不修改 chihiro
- ✅ 仅改 belle_ai 项目代码
- ✅ 最小改动，保持向后兼容
- ✅ 数据库变更以 Alembic（或现有迁移机制）为准，不直接执行 SQL

**前提条件**:
- ✅ 用户已手动在 `belle_ai.products` 添加 `brand_code` 字段
- ✅ 当前 `products` 表只有约 100 条测试数据，允许清空重建
- ✅ DBA 已准备好 `belle_ai.products_staging` 表（结构化原料）

**P-ETL-2 强约束**:
- ✅ **只读 `belle_ai.products_staging`**，不得访问 `chihiro` 库任何表
- ✅ ETL 消费 `products_staging`，写入 `products` / `product_change_log` / `etl_watermark`

---

## A. 现状检查与风险点

### A1. 数据库现状检查（执行前必须运行）

#### 检查 1：表结构现状
```sql
-- 检查 brand_code 字段是否存在及类型
SHOW CREATE TABLE belle_ai.products;

-- 预期输出应包含：
-- `brand_code` VARCHAR(64) 或类似定义
-- 如果不存在，需要先添加字段（不在本轮范围，用户已手动添加）
```

#### 检查 2：索引与唯一约束现状（必须执行）
```sql
-- 识别当前所有索引和唯一约束
SHOW INDEX FROM belle_ai.products WHERE Key_name != 'PRIMARY';

-- 预期输出示例：
-- | Table   | Non_unique | Key_name        | Seq_in_index | Column_name |
-- | products| 0          | sku             | 1            | sku         |  <- 唯一索引
-- | products| 1          | idx_products_sku| 1            | sku         |  <- 普通索引
-- 
-- ⚠️ 关键：必须根据实际输出确定需要删除的唯一索引名称（可能是 'sku' 或其他名称）
```

#### 检查 3：数据冲突检测（可选，建议执行）
```sql
-- 检测是否存在同一 sku 对应多个 brand_code 的情况
SELECT 
    sku,
    COUNT(DISTINCT brand_code) as brand_code_count,
    GROUP_CONCAT(DISTINCT brand_code ORDER BY brand_code) as brand_codes,
    COUNT(*) as total_records
FROM belle_ai.products
WHERE brand_code IS NOT NULL
GROUP BY sku
HAVING COUNT(DISTINCT brand_code) > 1
ORDER BY brand_code_count DESC, sku
LIMIT 100;

-- 检测是否存在 brand_code 为 NULL 的记录
SELECT 
    COUNT(*) as null_brand_code_count
FROM belle_ai.products
WHERE brand_code IS NULL;
```

### A2. 代码现状检查

#### 核心模型文件
- **`app/models/product.py`** - Product ORM 模型
  - 当前状态：缺少 `brand_code` 字段定义（用户已手动在数据库添加）
  - 唯一约束：`sku UNIQUE`（需要升级为 `UNIQUE(brand_code, sku)`）

#### Repository 层文件
- **`app/repositories/product_repository.py`** - Product 查询方法
  - 当前方法：`get_product_by_sku(db, sku)` - 仅按 sku 查询
  - 缺少：`get_product_by_brand_and_sku(db, brand_code, sku)` 方法
  - 缺少：基于 `(brand_code, sku)` 的 upsert 方法（使用 `INSERT ... ON DUPLICATE KEY UPDATE`）

#### Service 层文件
- **`app/services/data_version_calculator.py`** - 不存在，需要新建
  - 需要：data_version 计算白名单包含 `brand_code`
  - 需要：JSON 稳定序列化（key 排序、list 去重排序、price 用 Decimal/str 禁 float）

#### ETL 相关模型文件（需要新建）
- **`app/models/etl_watermark.py`** - 不存在，需要新建
  - 需要：支持"同秒不漏"设计
  - 字段：`table_name`, `last_processed_at`, `last_processed_key`
  - `last_processed_key` = `style_brand_no#style_no`

- **`app/models/product_change_log.py`** - 不存在，需要新建
  - 需要：记录变更日志，支持幂等
  - 唯一约束：`UNIQUE(brand_code, sku, data_version)`

#### ETL 数据源约束
- **`belle_ai.products_staging`** - ETL 数据源（**只读，不得访问 chihiro**）
  - 字段映射：`brand_code = style_brand_no`, `sku = style_no`
  - 排序字段：`src_updated_at`, `style_brand_no`, `style_no`

### A3. 风险点识别

#### 风险 1：唯一约束冲突（数据库层）
- **现状**: 当前唯一约束只有 `sku UNIQUE`
- **问题**: ETL 写入时使用 `(brand_code, sku)` 作为业务主键，但数据库约束只有 `sku UNIQUE`，会导致唯一键冲突
- **影响**: ETL 写入失败

#### 风险 2：查询逻辑错误（Repository 层）
- **现状**: `get_product_by_sku` 只按 `sku` 查询
- **问题**: 如果数据库中同一 `sku` 在不同 `brand_code` 下存在多条记录，`first()` 会返回不确定的记录
- **影响**: ETL 查询可能返回错误的品牌商品

#### 风险 3：data_version 计算不包含 brand_code
- **现状**: data_version 计算逻辑不存在或未包含 `brand_code`
- **问题**: 无法正确识别同一 `(brand_code, sku)` 的数据变更
- **影响**: ETL 可能误判数据变更，导致重复写入或遗漏变更

---

## B. 修改清单（精确到文件）

### B1. 必须修改的文件（P-ETL-2 范围，4 个）

#### 1. **`app/models/product.py`** ⚠️ **核心修改**
   - **修改内容**:
     - 添加 `brand_code: Mapped[str]` 字段定义（兼容用户已手动添加的字段）
     - 修改唯一约束：从 `sku UNIQUE` 到 `UNIQUE(brand_code, sku)`
     - 修改 `__table_args__` 中的索引定义
     - 更新 `__repr__` 方法包含 `brand_code`
   - **修改类型**: 修改现有文件

#### 2. **`app/repositories/product_repository.py`** ⚠️ **核心修改**
   - **修改内容**:
     - 新增 `get_product_by_brand_and_sku(db, brand_code, sku)` 方法
     - 新增 `upsert_product_by_brand_and_sku(db, product_data)` 方法（基于 `(brand_code, sku)` upsert）
     - 保留 `get_product_by_sku`（向后兼容，但标记警告）
   - **修改类型**: 修改现有文件

#### 3. **`app/services/data_version_calculator.py`** ⚠️ **新建文件**
   - **修改内容**:
     - 新建 `DataVersionCalculator` 类
     - 实现 `calculate_data_version(product_data)` 方法
     - 白名单字段：`brand_code`, `sku`, `name`, `price`, `image_url`, `on_sale`, `tags`, `attributes`
     - 确保 JSON 稳定序列化：key 排序、list 去重排序、price 用 Decimal/str 禁 float
   - **修改类型**: 新建文件

#### 4. **`app/repositories/__init__.py`** - 导出新方法（如需要）
   - **修改内容**: 导出 `get_product_by_brand_and_sku` 和 `upsert_product_by_brand_and_sku`
   - **修改类型**: 修改现有文件（如需要）

### B2. ETL Worker 相关文件（P-ETL-2 范围，新建）

#### 5. **`app/repositories/product_staging_repository.py`** ⚠️ **新建文件**
   - **修改内容**:
     - 新建 `ProductStagingRepository` 类
     - 实现分批查询方法：`fetch_batch_by_watermark(db, watermark, limit)`
     - **关键设计**：支持"同秒不漏"
       - watermark 保存：`last_processed_at` + `last_processed_key`（key = `style_brand_no#style_no`）
       - 拉取条件：`src_updated_at > last_at OR (src_updated_at = last_at AND key > last_key)`
       - 排序：`ORDER BY src_updated_at, style_brand_no, style_no`
     - 支持 `--limit` 和 `--resume` 参数
   - **修改类型**: 新建文件

#### 6. **`app/services/product_normalizer.py`** ⚠️ **新建文件**
   - **修改内容**:
     - 新建 `ProductNormalizer` 类
     - 实现 JSON 规范化逻辑（colors, tags, attributes）
   - **修改类型**: 新建文件

#### 7. **`app/services/product_upsert_service.py`** ⚠️ **新建文件**
   - **修改内容**:
     - 新建 `ProductUpsertService` 类
     - 实现基于 `(brand_code, sku)` 的 upsert 逻辑
     - **upsert 实现方式锁死**：
       - 使用 MySQL `INSERT ... ON DUPLICATE KEY UPDATE`（或等价方式）
       - **禁止** `DELETE + INSERT` 方式
       - **禁止** 覆盖 `id` / `created_at` 字段
     - 集成 data_version 计算和 change_log 写入
   - **修改类型**: 新建文件

#### 8. **`app/agents/workers/etl_product_worker.py`** ⚠️ **新建文件**
   - **修改内容**:
     - 新建 ETL Worker 主流程
     - 实现分批消费 `products_staging`（**只读 `belle_ai.products_staging`，不得访问 chihiro**）
     - 支持 `--limit` 和 `--resume` 参数
     - 实现 watermark 更新逻辑（`last_processed_at` + `last_processed_key`）
   - **修改类型**: 新建文件

### B3. 数据库迁移相关（可选，仅提供建议）

#### 9. **Alembic Migration 文件**（或现有迁移机制）
   - **修改内容**:
     - 创建迁移文件：修改唯一约束从 `sku UNIQUE` 到 `UNIQUE(brand_code, sku)`
     - 迁移前必须执行 A1 节的现状检查 SQL
     - 根据 `SHOW INDEX` 结果确定需要删除的索引名称
   - **修改类型**: 新建迁移文件（如使用 Alembic）
   - **状态**: 可选，根据项目迁移机制决定

#### 10. **`app/models/etl_watermark.py`** ⚠️ **新建文件**
   - **修改内容**:
     - 新建 `ETLWatermark` 模型
     - 字段：`table_name`, `last_processed_at`, `last_processed_key`
     - **关键设计**：支持"同秒不漏"
       - `last_processed_key` = `style_brand_no#style_no`（组合键字符串）
       - 用于同秒内多条记录的精确定位
   - **修改类型**: 新建文件

#### 11. **`app/models/product_change_log.py`** ⚠️ **新建文件**
   - **修改内容**:
     - 新建 `ProductChangeLog` 模型
     - 字段：`brand_code`, `sku`, `data_version`, `status`, `change_type`, `created_at`
     - 唯一约束：`UNIQUE(brand_code, sku, data_version)`（保证幂等）
   - **修改类型**: 新建文件

#### 12. **`sql/schema.sql`** - 可选更新（仅供参考）
   - **修改内容**: 更新表结构定义以反映最新状态（仅作参考，不执行）
   - **修改类型**: 可选修改
   - **状态**: 仅作参考，不作为必做项

### B4. 测试文件（P-ETL-2 范围，测试收敛）

#### 13. **ETL 核心测试文件**（新建，本轮必做 2 个）
   - **修改内容**:
     - `tests/test_data_version_calculator.py` - **必做**：data_version 稳定性测试
       - 验证：相同数据多次计算得到相同 data_version
       - 验证：JSON 稳定序列化（key 排序、list 去重排序、price 用 Decimal/str 禁 float）
       - 验证：brand_code 包含在白名单中
     - `tests/test_etl_product_worker.py` - **必做**：ETL 幂等/重复跑不增量测试
       - 验证：重复运行 ETL 不会产生重复的 change_log 记录
       - 验证：watermark 正确更新，支持断点续跑
       - 验证：同秒内多条记录不遗漏
   - **修改类型**: 新建测试文件（2 个必做）
   - **说明**: 测试数据必须包含 `brand_code` 字段

#### 14. **其他测试文件**（后续待办）
   - `tests/test_product_normalizer.py` - ProductNormalizer 测试（后续待办）
   - `tests/test_product_upsert_service.py` - ProductUpsertService 测试（后续待办）
   - **状态**: 不在本轮范围，移到后续待办

### B5. 文件统计

- **必须修改**: 4 个现有文件
- **必须新建**: 8 个新文件
  - Service 层：3 个（ProductNormalizer, DataVersionCalculator, ProductUpsertService）
  - Repository 层：1 个（ProductStagingRepository）
  - Model 层：2 个（ETLWatermark, ProductChangeLog）
  - Worker 层：1 个（ETLProductWorker）
  - Repository 扩展：1 个（product_repository.py 新增方法）
- **测试文件**: 2 个新建测试文件（本轮必做）
- **可选**: 1 个迁移文件
- **总计**: 15 个文件（14 个必做 + 1 个可选）

---

## C. 执行步骤/验证点

### C1. 数据库现状检查（执行前必须）

#### 步骤 1：检查表结构
```sql
SHOW CREATE TABLE belle_ai.products;
```
- **验证点**: 确认 `brand_code` 字段存在
- **如果不存在**: 需要先添加字段（不在本轮范围，用户已手动添加）

#### 步骤 2：检查索引现状
```sql
SHOW INDEX FROM belle_ai.products WHERE Key_name != 'PRIMARY';
```
- **验证点**: 记录所有索引名称，特别是唯一索引名称
- **输出**: 用于后续迁移 SQL 中的索引删除操作

#### 步骤 3：数据冲突检测（可选）
```sql
-- 见 A1 节检查 3
```
- **验证点**: 确认是否存在数据冲突
- **如果存在冲突**: 需要先处理冲突数据

### C2. 数据库迁移（可选，根据现状检查结果）

#### 方案 A：测试环境快速方案（推荐，当前约 100 条测试数据）

如果当前仅测试数据且允许清空：
```sql
-- 步骤1: 清空测试数据（谨慎！仅限测试环境）
TRUNCATE TABLE belle_ai.products;

-- 步骤2: 删除旧的唯一索引（索引名必须从步骤 2 的实际输出中获取）
-- ⚠️ 不能写死，必须先执行 SHOW INDEX 识别真实索引名
ALTER TABLE belle_ai.products DROP INDEX <真实索引名>;

-- 步骤3: 添加新的组合唯一索引
ALTER TABLE belle_ai.products 
ADD UNIQUE INDEX idx_products_brand_sku (brand_code, sku);

-- 步骤4: 添加 sku 的普通索引（用于查询性能）
ALTER TABLE belle_ai.products 
ADD INDEX idx_products_sku (sku);
```

#### 方案 B：使用 Alembic 迁移（生产环境推荐）

如果项目已使用 Alembic：
```bash
# 生成迁移文件
alembic revision -m "add_brand_code_unique_constraint"

# 在生成的迁移文件中编写：
# 1. 检查 brand_code 字段是否存在（用户已手动添加）
# 2. 填充 brand_code 默认值（如果存在 NULL，根据业务需求）
# 3. 删除旧的唯一索引（使用 SHOW INDEX 识别的真实索引名）
# 4. 添加新的组合唯一索引 UNIQUE(brand_code, sku)
# 5. 添加 sku 的普通索引（用于查询性能）

# 执行迁移
alembic upgrade head
```

#### 方案 C：生产环境手动迁移（必须根据 SHOW INDEX 结果调整）

```sql
-- ⚠️ 警告：以下 SQL 中的索引名是示例，必须根据 C1 步骤 2 的实际输出替换

-- 步骤1: 如果存在 brand_code 为 NULL 的记录，需要先填充默认值
UPDATE belle_ai.products 
SET brand_code = 'DEFAULT' 
WHERE brand_code IS NULL;

-- 步骤2: 删除旧的唯一索引（索引名必须从 SHOW INDEX 结果中获取）
-- ⚠️ 不能写死为 'sku'，必须先执行 SHOW INDEX 识别真实索引名
ALTER TABLE belle_ai.products DROP INDEX <真实索引名>;

-- 步骤3: 添加新的组合唯一索引
ALTER TABLE belle_ai.products 
ADD UNIQUE INDEX idx_products_brand_sku (brand_code, sku);

-- 步骤4: 添加 sku 的普通索引（用于查询性能，如果不存在则创建）
ALTER TABLE belle_ai.products 
ADD INDEX idx_products_sku (sku);
```

### C3. 代码修改步骤

#### 步骤 1：修改 Product 模型
- 文件：`app/models/product.py`
- 验证点：
  - `brand_code` 字段定义正确
  - 唯一约束为 `UNIQUE(brand_code, sku)`
  - `__table_args__` 中的索引定义正确

#### 步骤 2：扩展 Repository 层
- 文件：`app/repositories/product_repository.py`
- 验证点：
  - `get_product_by_brand_and_sku` 方法可用
  - `upsert_product_by_brand_and_sku` 方法可用
  - 保留 `get_product_by_sku`（向后兼容）

#### 步骤 3：实现 data_version 计算
- 文件：`app/services/data_version_calculator.py`（新建）
- 验证点：
  - 白名单包含 `brand_code`
  - JSON 稳定序列化（key 排序、list 去重排序、price 用 Decimal/str 禁 float）

#### 步骤 4：实现 ETL Worker
- 文件：`app/agents/workers/etl_product_worker.py`（新建）
- 验证点：
  - 支持 `--limit` 参数
  - 支持 `--resume` 断点续跑
  - 正确使用 `get_product_by_brand_and_sku` 和 `upsert_product_by_brand_and_sku`
  - **只读 `belle_ai.products_staging`，不得访问 chihiro**
  - watermark 支持"同秒不漏"：保存 `last_processed_at` + `last_processed_key`
  - 拉取条件：`src_updated_at > last_at OR (src_updated_at = last_at AND key > last_key)`
  - 排序：`ORDER BY src_updated_at, style_brand_no, style_no`

### C4. 验证清单

- ✅ 数据库唯一约束为 `UNIQUE(brand_code, sku)`
- ✅ Product 模型包含 `brand_code` 字段
- ✅ Repository 有 `get_product_by_brand_and_sku` 方法
- ✅ Repository 有 `upsert_product_by_brand_and_sku` 方法（使用 `INSERT ... ON DUPLICATE KEY UPDATE`）
- ✅ upsert 不覆盖 `id` / `created_at` 字段
- ✅ data_version 计算包含 `brand_code`
- ✅ data_version 计算使用稳定 JSON 序列化（key 排序、list 去重排序、price 用 Decimal/str 禁 float）
- ✅ ETL Worker 使用 `(brand_code, sku)` 作为业务主键
- ✅ ETL Worker 支持 `--limit` 和 `--resume`
- ✅ ETL Worker **只读 `belle_ai.products_staging`，不得访问 chihiro**
- ✅ watermark 支持"同秒不漏"：保存 `last_processed_at` + `last_processed_key`
- ✅ 拉取条件：`src_updated_at > last_at OR (src_updated_at = last_at AND key > last_key)`
- ✅ 排序：`ORDER BY src_updated_at, style_brand_no, style_no`
- ✅ 测试：data_version 稳定性测试通过
- ✅ 测试：ETL 幂等/重复跑不增量测试通过

---

## D. 后续待办（不在 P-ETL-2 范围）

### D1. 向量索引/RAG/API 的 brand_code 贯穿改造

以下改造不影响 ETL 写入与查询键的正确性，可在后续阶段逐步实施：

#### 1. **向量索引构建改造**
   - 文件：`app/db/init_vector_store.py`
   - 任务：向量索引构建时需要考虑 `brand_code`
   - 当前：只使用 `sku` 作为商品标识
   - 影响：不同品牌的相同 `sku` 会混淆

#### 2. **RAG SKU 过滤改造**
   - 文件：`app/services/rag_service.py`
   - 任务：`_filter_by_sku_ownership` 方法需要检查 `brand_code`
   - 当前：只检查 `sku`
   - 影响：可能导致跨品牌串货

#### 3. **API 层查询改造**
   - 文件：`app/api/v1/vector_search.py` 等
   - 任务：API 查询需要支持 `brand_code`
   - 当前：使用 `get_product_by_sku`
   - 影响：可能返回错误品牌的商品

#### 4. **其他 Service/Agent 层逐步升级**
   - `app/api/v1/copy.py` - 文案生成 API
   - `app/api/v1/followup.py` - 跟进建议 API
   - `app/api/v1/product.py` - 商品分析 API
   - `app/services/copy_service.py` - 文案生成服务
   - `app/agents/tools/product_tool.py` - Agent 工具

### D2. 其他测试文件更新（后续待办）

- `tests/test_product_normalizer.py` - ProductNormalizer 测试（后续待办）
- `tests/test_product_upsert_service.py` - ProductUpsertService 测试（后续待办）
- 所有其他 `tests/test_*.py` 中使用 Product 的测试文件
- 需要：在测试数据中添加 `brand_code` 字段
- 需要：更新测试断言

### D3. 文档更新

- 更新 API 文档，说明 `brand_code` 字段
- 更新开发文档，说明 `(brand_code, sku)` 业务主键

---

## E. 总结

### P-ETL-2 核心任务（本轮必须完成）

1. ✅ **数据库现状检查**：执行 A1 节检查 SQL，确认字段和索引状态
2. ✅ **数据库迁移**：根据现状检查结果，选择合适方案（推荐方案 A：TRUNCATE + 重建）
3. ✅ **Product 模型修改**：添加 `brand_code` 字段，修改唯一约束
4. ✅ **Repository 层升级**：新增基于 `(brand_code, sku)` 的查询和 upsert 方法
   - upsert 使用 `INSERT ... ON DUPLICATE KEY UPDATE`，不覆盖 `id` / `created_at`
5. ✅ **data_version 计算**：新建服务，包含 `brand_code`，确保 JSON 稳定序列化
6. ✅ **ETL Worker 实现**：新建 Worker，支持分批消费和断点续跑
   - **只读 `belle_ai.products_staging`，不得访问 chihiro**
   - watermark 支持"同秒不漏"：`last_processed_at` + `last_processed_key`
7. ✅ **ETL 核心测试**：2 个必做测试（data_version 稳定性、ETL 幂等/重复跑不增量）

### 文件统计

- **必须修改**: 4 个现有文件
- **必须新建**: 8 个新文件（Service 3 + Repository 1 + Model 2 + Worker 1 + Repository 扩展 1）
- **测试文件**: 2 个新建测试文件（本轮必做）
- **可选**: 1 个迁移文件
- **总计**: 15 个文件（14 个必做 + 1 个可选）

### 关键约束

- ✅ 数据库变更以 Alembic（或现有迁移机制）为准
- ✅ 索引删除前必须先 `SHOW INDEX` 识别真实索引名
- ✅ 优先使用 TRUNCATE + 重建的简化路径（测试环境）
- ✅ **只读 `belle_ai.products_staging`，不得访问 chihiro**
- ✅ upsert 使用 `INSERT ... ON DUPLICATE KEY UPDATE`，不覆盖 `id` / `created_at`
- ✅ watermark 支持"同秒不漏"：`last_processed_at` + `last_processed_key`
- ✅ 拉取条件：`src_updated_at > last_at OR (src_updated_at = last_at AND key > last_key)`
- ✅ 排序：`ORDER BY src_updated_at, style_brand_no, style_no`
- ✅ 测试收敛：本轮必做 2 个测试（data_version 稳定性、ETL 幂等/重复跑不增量）
- ✅ 向量索引/RAG/API 改造不在本轮范围，作为后续待办

---

**下一步**: 开始实现代码修改（按 A/B/C/D/E/F 顺序输出代码）
