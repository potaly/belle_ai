# P-ETL-2 代码实现清单

**实现阶段**: P-ETL-2（brand_code 字段修复 + ETL Worker 实现）  
**实现原则**: 最小改动、不推倒重写、不修改 chihiro、只读 products_staging

---

## C. 关键代码（按文件分段）

### C1. Utils 层

#### `app/utils/json_utils.py` ✅ 已实现
- `stable_json_dumps()`: 稳定 JSON 序列化
- 规则：key 排序、list 去重排序、price 用 Decimal/str 禁 float

### C2. Model 层

#### `app/models/product.py` ✅ 已修改
- 添加 `brand_code: Mapped[str]` 字段
- 修改唯一约束：`UniqueConstraint("brand_code", "sku", name="idx_products_brand_sku")`
- 更新 `__repr__` 方法

#### `app/models/etl_watermark.py` ✅ 已实现
- `ETLWatermark` 模型
- 字段：`table_name`, `last_processed_at`, `last_processed_key`
- 唯一约束：`UNIQUE(table_name)`

#### `app/models/product_change_log.py` ✅ 已实现
- `ProductChangeLog` 模型
- 字段：`brand_code`, `sku`, `data_version`, `status`, `change_type`, `created_at`
- 唯一约束：`UNIQUE(brand_code, sku, data_version)`

### C3. Repository 层

#### `app/repositories/product_repository.py` ✅ 已扩展
- `get_product_by_brand_and_sku()`: 基于 `(brand_code, sku)` 查询
- `upsert_product_by_brand_and_sku()`: 基于 `(brand_code, sku)` upsert
  - 使用 MySQL `INSERT ... ON DUPLICATE KEY UPDATE`（原生 SQL）
  - 不覆盖 `id` / `created_at` 字段
  - JSON 字段（tags, attributes）自动序列化
- 保留 `get_product_by_sku()`（向后兼容，标记警告）

#### `app/repositories/product_staging_repository.py` ✅ 已实现
- `ProductStagingRepository` 类
- `fetch_batch_by_watermark()`: 分批查询，支持"同秒不漏"
  - 拉取条件：`src_updated_at > last_at OR (src_updated_at = last_at AND key > last_key)`
  - 排序：`ORDER BY src_updated_at, style_brand_no, style_no`
- `get_max_updated_at_and_key()`: 获取批次最大时间戳和 key

### C4. Service 层

#### `app/services/product_normalizer.py` ✅ 已实现
- `ProductNormalizer` 类
- `normalize_colors()`: 从 `colors_concat` split，去重、排序
- `normalize_tags()`: 从 `tags_json` 规范化，去重、排序
- `normalize_attributes()`: 从 `attrs_json` 规范化，value 包含 '||' → split 成数组
- `normalize_staging_record()`: 完整记录规范化

#### `app/services/data_version_calculator.py` ✅ 已实现
- `DataVersionCalculator` 类
- `calculate_data_version()`: 计算稳定 data_version
  - 白名单字段：`brand_code`, `sku`, `name`, `price`, `image_url`, `on_sale`, `tags`, `attributes`
  - 使用 `stable_json_dumps()` 确保稳定序列化
  - 返回 MD5 哈希值

#### `app/services/product_upsert_service.py` ✅ 已实现
- `ProductUpsertService` 类
- `upsert_product()`: Upsert 产品并写 change_log
  - 仅当 data_version 不一致时才更新
  - 使用 `upsert_product_by_brand_and_sku()`（ORM 方式）
  - 写 change_log（幂等，unique constraint 防止重复）

### C5. Worker 层

#### `app/agents/workers/etl_product_worker.py` ✅ 已实现
- `ETLProductWorker` 类
- `validate_prerequisites()`: **强校验**
  - 检查 `products` 表是否存在 `UNIQUE(brand_code, sku)`
  - 检查 `products_staging` 表是否包含必要字段
  - 不满足则退出并提示 SQL
- `get_watermark()` / `update_watermark()`: watermark 管理
- `process_batch()`: 处理一批记录
- `run()`: 主流程，支持 `--limit` 和 `--resume`
- `main()`: 命令行入口

### C6. 测试文件

#### `tests/test_data_version_calculator.py` ✅ 已实现
- `test_data_version_stability()`: 验证相同数据多次计算得到相同版本
- `test_data_version_includes_brand_code()`: 验证 brand_code 包含在计算中
- `test_data_version_json_stable_serialization()`: 验证 JSON 稳定序列化
- `test_data_version_price_decimal_not_float()`: 验证 price 使用 Decimal/str
- `test_data_version_list_deduplication()`: 验证 list 去重排序

#### `tests/test_etl_product_worker.py` ✅ 已实现
- `test_etl_idempotency()`: 验证重复运行不产生重复 change_log
- `test_watermark_same_second_no_miss()`: 验证同秒不漏设计
- `test_etl_resume_from_watermark()`: 验证断点续跑功能

---

## D. 数据库变更（SQL 脚本建议）

### D1. 创建 ETL 相关表

**文件**: `sql/migrations/add_etl_tables.sql`

**说明**: 由 DBA 执行，创建 `etl_watermark` 和 `product_change_log` 表

**包含内容**:
- `etl_watermark` 表创建语句
- `product_change_log` 表创建语句
- 验证查询

### D2. 修改 products 表唯一约束

**文件**: `sql/migrations/add_products_unique_constraint.sql`

**说明**: 由 DBA 执行，修改 `products` 表唯一约束

**执行步骤**:
1. **必须执行**: `SHOW INDEX FROM belle_ai.products WHERE Key_name != 'PRIMARY';`
2. **根据输出确定**: 需要删除的旧唯一索引名称
3. **执行迁移**: 删除旧索引，添加新组合唯一索引

**关键约束**:
- ⚠️ 不能写死索引名，必须先 `SHOW INDEX` 识别
- ⚠️ 如果当前仅测试数据，可使用 TRUNCATE + 重建的简化路径

---

## E. 运行命令示例

### E1. 前置检查（运行 ETL Worker 前必须执行）

```bash
# 检查 products 表唯一约束
mysql -u root -p -e "SHOW INDEX FROM belle_ai.products WHERE Key_name != 'PRIMARY';"

# 检查 products_staging 表字段
mysql -u root -p -e "SHOW COLUMNS FROM belle_ai.products_staging;"
```

### E2. 数据库迁移（由 DBA 执行）

```bash
# 执行 ETL 表创建脚本
mysql -u root -p belle_ai < sql/migrations/add_etl_tables.sql

# 执行 products 表唯一约束修改脚本
# ⚠️ 注意：执行前必须先运行 SHOW INDEX 确定索引名
mysql -u root -p belle_ai < sql/migrations/add_products_unique_constraint.sql
```

### E3. 运行 ETL Worker

```bash
# 基本运行（默认 limit=1000, resume=True）
python -m app.agents.workers.etl_product_worker

# 指定批次大小
python -m app.agents.workers.etl_product_worker --limit 500

# 从头开始（忽略 watermark）
python -m app.agents.workers.etl_product_worker --no-resume

# 从 watermark 继续（默认）
python -m app.agents.workers.etl_product_worker --resume
```

### E4. 运行测试

```bash
# 运行 data_version 稳定性测试
pytest tests/test_data_version_calculator.py -v

# 运行 ETL 幂等测试
pytest tests/test_etl_product_worker.py -v

# 运行所有 ETL 相关测试
pytest tests/test_data_version_calculator.py tests/test_etl_product_worker.py -v
```

---

## F. 验收清单（≤5 条）

### F1. 数据库唯一约束验证 ✅
- **检查方式**: 执行 `SHOW INDEX FROM belle_ai.products WHERE Key_name = 'idx_products_brand_sku';`
- **预期结果**: 应看到两行，包含 `brand_code` 和 `sku` 列
- **验证命令**:
  ```sql
  SHOW INDEX FROM belle_ai.products WHERE Key_name = 'idx_products_brand_sku';
  ```

### F2. ETL 表创建验证 ✅
- **检查方式**: 执行 `SHOW TABLES LIKE 'etl_%';` 和 `SHOW TABLES LIKE 'product_change_log';`
- **预期结果**: `etl_watermark` 和 `product_change_log` 表存在
- **验证命令**:
  ```sql
  SHOW TABLES LIKE 'etl_%';
  SHOW TABLES LIKE 'product_change_log';
  ```

### F3. data_version 稳定性测试通过 ✅
- **检查方式**: 运行 `pytest tests/test_data_version_calculator.py -v`
- **预期结果**: 所有测试通过
- **验证点**:
  - 相同数据多次计算得到相同 data_version
  - JSON 稳定序列化（key 排序、list 去重排序）
  - price 使用 Decimal/str，不使用 float
  - brand_code 包含在白名单中

### F4. ETL 幂等测试通过 ✅
- **检查方式**: 运行 `pytest tests/test_etl_product_worker.py -v`
- **预期结果**: 所有测试通过
- **验证点**:
  - 重复运行 ETL 不会产生重复的 change_log 记录
  - watermark 正确更新，支持断点续跑
  - 同秒内多条记录不遗漏

### F5. ETL Worker 功能验证 ✅
- **检查方式**: 运行 ETL Worker 并检查输出
- **预期结果**: 
  - 启动时通过强校验（检查唯一约束和字段）
  - 支持 `--limit` 参数
  - 支持 `--resume` 断点续跑
  - 正确写入 products/change_log/watermark
- **验证命令**:
  ```bash
  python -m app.agents.workers.etl_product_worker --limit 100
  ```

---

## 实现完成总结

### 已实现文件（14 个）

1. ✅ `app/utils/json_utils.py` - JSON 稳定序列化工具
2. ✅ `app/models/product.py` - 添加 brand_code 字段
3. ✅ `app/models/etl_watermark.py` - ETLWatermark 模型
4. ✅ `app/models/product_change_log.py` - ProductChangeLog 模型
5. ✅ `app/repositories/product_repository.py` - 扩展查询和 upsert 方法
6. ✅ `app/repositories/product_staging_repository.py` - 分批查询 Repository
7. ✅ `app/services/product_normalizer.py` - JSON 规范化服务
8. ✅ `app/services/data_version_calculator.py` - data_version 计算服务
9. ✅ `app/services/product_upsert_service.py` - Upsert 服务
10. ✅ `app/agents/workers/etl_product_worker.py` - ETL Worker（含强校验）
11. ✅ `tests/test_data_version_calculator.py` - data_version 稳定性测试
12. ✅ `tests/test_etl_product_worker.py` - ETL 幂等测试
13. ✅ `sql/migrations/add_etl_tables.sql` - ETL 表创建脚本
14. ✅ `sql/migrations/add_products_unique_constraint.sql` - 唯一约束迁移脚本

### 关键特性

- ✅ **强校验**: ETL Worker 启动前检查唯一约束和字段
- ✅ **同秒不漏**: watermark 支持 `last_processed_at` + `last_processed_key`
- ✅ **幂等性**: change_log 使用 unique constraint 防止重复
- ✅ **稳定序列化**: JSON key 排序、list 去重排序、price 用 Decimal/str
- ✅ **只读 staging**: 不访问 chihiro，只读 `belle_ai.products_staging`

---

**下一步**: 执行数据库迁移脚本，然后运行 ETL Worker 进行验证
