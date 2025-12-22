# ETL 可行性与风险校验分析报告（P-ETL-1 修正版 V2）

**分析时间**: 2024-12-19  
**分析阶段**: P-ETL-1（修正版 V2｜品牌维度锁定）  
**分析范围**: 仓库结构扫描、数据库现状、基于品牌维度的风险识别  
**分析原则**: 不推倒重写、不修改 chihiro 表结构、不写 ETL 业务代码  

**源表范围锁定**:
- ✅ `chihiro.ezr_mall_prd_prod`（商品主表）
- ✅ `chihiro.tbl_commodity_style`（商品风格表）
- ✅ `chihiro.tbl_commodity_extend_prop`（商品扩展属性表）

**业务语义前置声明**:
- ⚠️ `itemNo` **不是全局唯一 SKU**
- ⚠️ 同一 `itemNo` 在多个 `brand_code` 下出现是**正常业务现象**
- ⚠️ 所有分析必须以 `(brand_code, itemNo)` 为最小业务粒度

---

## A. 仓库扫描结果

### A1. belle_ai.products 表 ORM / Repository

#### ORM 模型
- **文件路径**: `app/models/product.py`
- **表名**: `products`
- **数据库**: `belle_ai`
- **关键字段**:
  - `id`: BIGINT PRIMARY KEY AUTO_INCREMENT
  - `sku`: VARCHAR(64) NOT NULL UNIQUE（当前唯一约束）
  - `name`: VARCHAR(255) NOT NULL
  - `price`: DECIMAL(10,2) NOT NULL
  - `tags`: JSON NULL
  - `attributes`: JSON NULL
  - `description`: TEXT NULL
  - `image_url`: VARCHAR(512) NULL
  - `created_at`: DATETIME NOT NULL
  - `updated_at`: DATETIME NOT NULL

#### Repository 层
- **文件路径**: `app/repositories/product_repository.py`
- **现有方法**: 
  - `get_product_by_sku(db: Session, sku: str) -> Optional[Product]`
- **使用位置**: 
  - `app/api/v1/vector_search.py`（向量搜索 API）
  - `app/services/product_service.py`（商品分析服务）

#### 表结构定义
- **文件路径**: `sql/schema.sql`（第 6-18 行）
- **当前唯一约束**: `sku VARCHAR(64) NOT NULL UNIQUE`
- **索引**: `idx_products_sku (sku)`

#### 现状结论
- ✅ ORM 模型已存在，结构完整
- ✅ Repository 层已实现基础查询方法
- ⚠️ **关键问题**: 当前唯一约束仅基于 `sku`，未考虑 `brand_code` 维度
- ⚠️ **影响**: 如果源数据中同一 `itemNo` 对应多个 `brand_code`，需要设计新的唯一键策略

### A2. ETL 相关表检查

#### etl_watermark
- **状态**: ❌ **不存在**
- **搜索范围**: 全仓库代码、SQL 文件
- **结论**: 当前无 ETL 水位表，需要在 P-ETL-2 阶段新建
- **预期用途**: 记录 ETL 同步进度，支持增量同步

#### product_change_log
- **状态**: ❌ **不存在**
- **搜索范围**: 全仓库代码、SQL 文件
- **仅在文档提及**: `docs/prompt/data_handle.md`（第 12 行）
- **结论**: 当前无变更日志表，需要在 P-ETL-2 阶段新建
- **预期用途**: 作为"唯一可信的变更队列"，驱动向量与后续 AI 能力

### A3. 向量 Worker 依赖检查

#### 向量服务代码
- **文件路径**: `app/services/vector_store.py`
- **初始化脚本**: `app/db/init_vector_store.py`
- **API 端点**: `app/api/v1/vector_search.py`

#### 当前数据源
```python
# app/db/init_vector_store.py:32
products = db.query(Product).all()  # 全量查询 products 表
```

#### 依赖 change_log 情况
- **状态**: ❌ **不依赖**
- **当前实现**: 直接从 `belle_ai.products` 表全量加载
- **初始化方式**: 一次性全量构建向量索引
- **增量更新**: 当前无增量更新机制

#### 影响分析
- ✅ **兼容性**: 向量服务不依赖 change_log，后续引入 change_log 不会破坏现有功能
- ⚠️ **迁移路径**: 需要将向量初始化从全量改为基于 change_log 的增量更新
- ⚠️ **品牌维度影响**: 向量索引需要考虑 `(brand_code, itemNo)` 组合的唯一性

---

## B. 唯一键风险分析（基于 brand_code + itemNo 维度）

### B1. 业务语义说明

#### 关键认知
- **itemNo 不是全局唯一**: 同一 `itemNo` 在不同 `brand_code` 下可以存在
- **典型场景**: 综合品牌门店销售其他品牌商品
- **业务粒度**: `(brand_code, itemNo)` 才是唯一标识一个商品的最小业务单元

#### 对 ETL 设计的影响
- ❌ **错误设计**: 仅使用 `itemNo` 作为唯一键
- ✅ **正确设计**: 使用 `(brand_code, itemNo)` 作为唯一键，或生成组合 SKU（如 `{brand_code}_{itemNo}`）

### B2. 源表唯一性检测 SQL（不执行，仅分析）

#### 检测同一 (brand_code, itemNo) 是否存在多条记录
```sql
-- 检测：同一 brand_code + itemNo 是否存在多条记录
SELECT
  brand_code,
  itemNo,
  COUNT(*) AS rows_cnt,
  MIN(update_time) AS first_update,
  MAX(update_time) AS last_update,
  GROUP_CONCAT(DISTINCT id ORDER BY id) AS record_ids
FROM chihiro.ezr_mall_prd_prod
WHERE brand_code IS NOT NULL
  AND itemNo IS NOT NULL
GROUP BY brand_code, itemNo
HAVING COUNT(*) > 1
ORDER BY rows_cnt DESC
LIMIT 200;
```

#### 分析说明
- **是否可能出现**: 需要执行上述 SQL 确认
- **出现时的业务含义**:
  - 如果是 REPLACE 语义：同一商品被多次写入，取最新记录
  - 如果是脏数据：同一商品存在重复记录，需要去重策略
  - 如果是历史版本：需要明确保留策略（最新 / 全部）
- **对 ETL 唯一键设计的影响**:
  - 如果存在重复：ETL 需要实现去重逻辑（如按 `update_time` 取最新）
  - 如果不存在重复：可以直接使用 `(brand_code, itemNo)` 作为唯一键

### B3. 目标表唯一键设计建议

#### 方案 A：组合唯一索引
```sql
-- 在 belle_ai.products 表上创建组合唯一索引
ALTER TABLE belle_ai.products 
ADD UNIQUE INDEX idx_brand_item (brand_code, item_no);
```

#### 方案 B：生成组合 SKU
```sql
-- 在 ETL 时生成组合 SKU：{brand_code}_{itemNo}
-- 保持现有 sku 字段的唯一约束
-- 示例：brand_code='BELLE', itemNo='8WZ01CM5' -> sku='BELLE_8WZ01CM5'
```

#### 方案选择建议
- **推荐方案 B**: 保持现有 `sku` 字段唯一约束，通过组合生成确保唯一性
- **理由**: 
  - 不破坏现有代码（已有 `get_product_by_sku` 方法）
  - 向后兼容（现有 API 仍可使用 `sku` 查询）
  - 语义清晰（`sku` 字段明确表示唯一商品标识）

### B4. 风险结论

- ⚠️ **高风险**: 如果源表中同一 `(brand_code, itemNo)` 存在多条记录，ETL 需要实现去重逻辑
- ⚠️ **中风险**: 如果目标表不采用 `(brand_code, itemNo)` 维度，可能导致数据丢失或覆盖错误
- ✅ **缓解措施**: 
  - 执行 B2 节检测 SQL，确认源表数据情况
  - 在 ETL 实现中采用组合 SKU 策略
  - 实现去重逻辑（如按 `update_time` 取最新记录）

---

## C. REPLACE 抖动风险分析（品牌维度）

### C1. 为什么必须按品牌维度分析

#### 错误示例（仅按 itemNo）
```sql
-- ❌ 错误：只按 itemNo 分组，忽略了 brand_code
SELECT
  itemNo,
  COUNT(*) AS change_cnt
FROM chihiro.ezr_mall_prd_prod
GROUP BY itemNo
HAVING change_cnt > 1;
```

**问题**: 
- 同一 `itemNo` 在不同 `brand_code` 下的变更会被合并统计
- 无法识别具体哪个品牌的商品存在频繁变更
- 导致 ETL 误判变更频率，影响 watermark 和 change_log 的准确性

#### 正确示例（按 brand_code + itemNo）
```sql
-- ✅ 正确：按 (brand_code, itemNo) 分组
SELECT
  brand_code,
  itemNo,
  COUNT(*) AS change_cnt,
  MIN(update_time) AS first_update,
  MAX(update_time) AS last_update,
  TIMESTAMPDIFF(SECOND, MIN(update_time), MAX(update_time)) AS span_seconds
FROM chihiro.ezr_mall_prd_prod
WHERE brand_code IS NOT NULL
  AND itemNo IS NOT NULL
GROUP BY brand_code, itemNo
HAVING change_cnt > 1
ORDER BY change_cnt DESC, span_seconds ASC
LIMIT 200;
```

### C2. update_time 抖动检测 SQL（不执行，仅分析）

```sql
-- 检测同一 (brand_code, itemNo) 的 update_time 变化频率
SELECT
  brand_code,
  itemNo,
  COUNT(*) AS change_cnt,
  MIN(update_time) AS first_update,
  MAX(update_time) AS last_update,
  TIMESTAMPDIFF(SECOND, MIN(update_time), MAX(update_time)) AS span_seconds,
  CASE 
    WHEN TIMESTAMPDIFF(SECOND, MIN(update_time), MAX(update_time)) > 0 
    THEN COUNT(*) / TIMESTAMPDIFF(SECOND, MIN(update_time), MAX(update_time))
    ELSE 0 
  END AS changes_per_second
FROM chihiro.ezr_mall_prd_prod
WHERE brand_code IS NOT NULL
  AND itemNo IS NOT NULL
GROUP BY brand_code, itemNo
HAVING change_cnt > 1
ORDER BY change_cnt DESC, span_seconds ASC
LIMIT 200;
```

### C3. 抖动对 ETL 组件的影响

#### 对 watermark 的影响
- **问题**: 如果 `update_time` 频繁变化（即使业务数据未变更），会导致：
  - watermark 位置频繁前移
  - ETL 重复处理相同数据
  - 增加无效的数据库操作
- **缓解**: 在 ETL 层做数据对比（对比除 `update_time` 外的业务字段），仅在实际变更时更新

#### 对 change_log 的影响
- **问题**: 频繁的 `update_time` 变化会产生大量无效的 change_log 记录
- **影响**: 
  - change_log 表快速增长
  - 向量索引频繁重建
  - 下游 AI 能力被无效变更触发
- **缓解**: 
  - 在写入 change_log 前做数据哈希对比（MD5/SHA256）
  - 仅在实际业务字段变更时记录 change_log
  - 在 change_log 中记录变更类型（CREATE/UPDATE/DELETE）和变更字段列表

#### 对向量同步的影响
- **问题**: 无效变更触发向量索引更新，增加计算开销
- **影响**: 
  - 向量索引频繁重建
  - 嵌入模型调用次数增加
  - 系统资源浪费
- **缓解**: 
  - 基于 change_log 的变更类型判断，仅对实际变更的商品更新向量
  - 实现增量更新机制，避免全量重建

### C4. 风险结论

- ⚠️ **中高风险**: `update_time` 抖动可能导致大量无效变更记录
- ✅ **缓解措施**: 
  - 在 ETL 层实现数据对比机制（业务字段哈希）
  - 在 change_log 中记录变更类型和变更字段
  - 向量同步基于 change_log 的变更类型，而非 update_time

---

## D. 风险清单（≤6 条）

### D1. 唯一键设计风险 ⚠️ **高风险**

#### 风险描述
- **现状**: `belle_ai.products.sku` 有 UNIQUE 约束，但未考虑 `brand_code` 维度
- **问题**: 如果源数据中同一 `itemNo` 对应多个 `brand_code`，直接使用 `itemNo` 作为 `sku` 会违反唯一约束
- **影响**: ETL 过程会因唯一键冲突而失败，或导致数据覆盖错误

#### 缓解措施
- ✅ 使用组合 SKU 策略：`sku = CONCAT(brand_code, '_', itemNo)`
- ✅ 执行 B2 节检测 SQL，确认源表数据情况
- ✅ 在 ETL 实现中实现去重逻辑（如按 `update_time` 取最新记录）

#### 检测 SQL（不执行）
```sql
-- 见 B2 节：检测同一 (brand_code, itemNo) 是否存在多条记录
```

---

### D2. REPLACE + update_time 抖动风险 ⚠️ **中高风险**

#### 风险描述
- **REPLACE 语义**: 源数据采用 REPLACE 语义，同一 `(brand_code, itemNo)` 可能被多次覆盖
- **update_time 抖动**: 如果源表的 `update_time` 字段频繁变化（即使数据未实际变更），会导致：
  - ETL 误判为"数据变更"
  - 产生大量无效的 change_log 记录
  - 向量索引频繁重建

#### 缓解措施
- ✅ 在 ETL 层做数据对比（对比除 `update_time` 外的业务字段）
- ✅ 使用数据哈希（MD5/SHA256）判断是否真正变更
- ✅ 在 change_log 中记录变更类型（CREATE/UPDATE/DELETE）和变更字段列表

#### 检测 SQL（不执行）
```sql
-- 见 C2 节：检测 update_time 抖动情况
```

---

### D3. onSale 字段不统一风险 ⚠️ **中风险**

#### 风险描述
- **字段缺失**: 当前 `belle_ai.products` 表无 `onSale` 字段
- **业务含义**: `chihiro.ezr_mall_prd_prod` 源表可能有 `onSale` 字段表示商品上下架状态
- **品牌差异**: 不同品牌可能使用不同的字段名或取值表示上下架状态
- **影响**: 
  - 如果需要在 `belle_ai.products` 中体现上下架状态，需要新增字段
  - 如果不需要，需要在 ETL 时过滤掉已下架商品
  - 不同品牌可能需要不同的过滤条件

#### 缓解措施
- ✅ 确认业务需求：`belle_ai.products` 是否需要 `onSale` 字段
- ✅ 如果不同品牌字段名不同，建议在配置中支持字段映射（如 `SOURCE_ONSALE_FIELD`）
- ✅ 如果需要：在 `belle_ai.products` 表新增 `onSale` 字段（需要 migration）
- ✅ 如果不需要：在 ETL WHERE 条件中过滤 `onSale = 1` 的商品

#### 检测 SQL（不执行）
```sql
-- 检测 chihiro.ezr_mall_prd_prod 源表中 onSale 字段的分布（如果存在）
SELECT 
    brand_code,
    onSale,
    COUNT(*) as count,
    COUNT(*) * 100.0 / (SELECT COUNT(*) FROM chihiro.ezr_mall_prd_prod WHERE brand_code = t.brand_code) as percentage
FROM chihiro.ezr_mall_prd_prod t
WHERE onSale IS NOT NULL  -- 需要确认字段名
GROUP BY brand_code, onSale
ORDER BY brand_code, onSale;
```

---

### D4. extend_prop 脏数据风险 ⚠️ **中风险**

#### 风险描述
- **JSON 字段**: `chihiro.tbl_commodity_extend_prop` 表可能有 `value` 字段存储 JSON 扩展属性
- **脏数据风险**: 
  - JSON 格式不合法（无法解析）
  - JSON 结构不一致（有些是对象，有些是数组）
  - 包含特殊字符（如换行符、控制字符）导致 JSON 解析失败
  - 值为 "无 / 不适用 / 空 / --" 等无效值
  - 可能出现异常长文本（如超过字段长度限制）
- **影响**: ETL 过程可能因 JSON 解析错误而中断，或导致数据丢失

#### 缓解措施
- ✅ 在 ETL 层做 JSON 格式校验和清理
- ✅ 使用 `JSON_VALID()` 函数（MySQL 5.7+）验证 JSON 格式
- ✅ 对无效 JSON 进行容错处理（如：设为 NULL 或使用默认值）
- ✅ 对无效值（"无"、"不适用"等）进行过滤或标准化

#### 检测 SQL（不执行）
```sql
-- 检测 tbl_commodity_extend_prop.value 字段的 JSON 有效性
SELECT 
    COUNT(*) as total,
    SUM(CASE WHEN JSON_VALID(value) THEN 1 ELSE 0 END) as valid_json,
    SUM(CASE WHEN JSON_VALID(value) = 0 THEN 1 ELSE 0 END) as invalid_json,
    SUM(CASE WHEN value IS NULL THEN 1 ELSE 0 END) as null_count,
    SUM(CASE WHEN value IN ('无', '不适用', '空', '--', '') THEN 1 ELSE 0 END) as invalid_value_count
FROM chihiro.tbl_commodity_extend_prop;

-- 查看无效 JSON 的示例
SELECT 
    id,
    commodity_id,
    prop_key,
    value,
    LEFT(value, 100) as preview,
    LENGTH(value) as value_length
FROM chihiro.tbl_commodity_extend_prop
WHERE JSON_VALID(value) = 0
   OR value IN ('无', '不适用', '空', '--', '')
LIMIT 20;

-- 检测异常长文本
SELECT 
    COUNT(*) as long_text_count,
    MAX(LENGTH(value)) as max_length,
    AVG(LENGTH(value)) as avg_length
FROM chihiro.tbl_commodity_extend_prop
WHERE LENGTH(value) > 10000;  -- 假设超过 10000 字符为异常
```

---

### D5. 向量索引增量更新风险 ⚠️ **中风险**

#### 风险描述
- **现状**: 向量服务当前使用全量初始化（`db.query(Product).all()`）
- **问题**: 引入 change_log 后，需要改为增量更新机制
- **品牌维度影响**: 需要确保 `(brand_code, itemNo)` 组合的唯一性在向量索引中正确体现
- **影响**: 
  - 如果增量更新逻辑有误，可能导致向量索引与数据库不一致
  - 需要处理删除、更新、新增三种场景
  - 需要处理品牌维度下的商品变更

#### 缓解措施
- ✅ 设计增量更新策略：基于 change_log 的变更类型（CREATE/UPDATE/DELETE）
- ✅ 保留全量重建能力作为降级方案
- ✅ 在向量更新前后做数据一致性校验
- ✅ 确保向量索引中的商品标识包含 `brand_code` 信息

#### 兼容性分析
- ✅ **不破坏现有功能**: 向量服务不依赖 change_log，现有功能不受影响
- ⚠️ **需要新增功能**: 需要实现基于 change_log 的增量更新机制
- ⚠️ **迁移复杂度**: 需要处理 CREATE/UPDATE/DELETE 三种变更类型的向量索引更新

---

### D6. 字段映射不一致风险 ⚠️ **中风险**

#### 风险描述
- **字段名差异**: `chihiro.ezr_mall_prd_prod` 源表的字段名可能与 `belle_ai.products` 表字段名不一致
- **字段缺失**: 源表可能缺少某些目标表需要的字段，或目标表缺少源表存在的字段
- **数据类型差异**: 相同语义的字段在不同表中可能使用不同的数据类型（如 VARCHAR vs TEXT）
- **多表关联**: 需要从 `tbl_commodity_style` 和 `tbl_commodity_extend_prop` 关联获取完整商品信息
- **影响**: ETL 过程需要做字段映射和类型转换，映射错误会导致数据丢失或类型错误

#### 缓解措施
- ✅ 在 ETL 前先分析源表和目标表的字段对应关系，建立字段映射表
- ✅ 对缺失字段设置默认值或 NULL 处理策略
- ✅ 对数据类型不匹配的字段进行显式转换（如 CAST、CONVERT）
- ✅ 明确多表关联逻辑（JOIN 条件、关联字段）
- ✅ 记录字段映射日志，便于问题排查

#### 检测 SQL（不执行）
```sql
-- 步骤1: 查看 chihiro.ezr_mall_prd_prod 源表结构
DESCRIBE chihiro.ezr_mall_prd_prod;
-- 或
SHOW COLUMNS FROM chihiro.ezr_mall_prd_prod;

-- 步骤2: 查看关联表结构
DESCRIBE chihiro.tbl_commodity_style;
DESCRIBE chihiro.tbl_commodity_extend_prop;

-- 步骤3: 查看 belle_ai.products 表结构
DESCRIBE belle_ai.products;

-- 步骤4: 检测源表中是否有 NULL 值会影响目标表 NOT NULL 约束
SELECT 
    COUNT(*) as total,
    SUM(CASE WHEN brand_code IS NULL THEN 1 ELSE 0 END) as null_brand_code,
    SUM(CASE WHEN itemNo IS NULL THEN 1 ELSE 0 END) as null_itemNo,
    SUM(CASE WHEN name IS NULL OR name = '' THEN 1 ELSE 0 END) as null_name,
    SUM(CASE WHEN price IS NULL THEN 1 ELSE 0 END) as null_price
FROM chihiro.ezr_mall_prd_prod;

-- 步骤5: 检测关联表的数据完整性
SELECT 
    COUNT(DISTINCT commodity_id) as total_commodities,
    COUNT(*) as total_records
FROM chihiro.tbl_commodity_style;

SELECT 
    COUNT(DISTINCT commodity_id) as total_commodities,
    COUNT(*) as total_records
FROM chihiro.tbl_commodity_extend_prop;
```

---

## E. P-ETL-2 前置结论

### E1. 是否具备进入实现阶段的条件

#### ✅ 具备条件
- ✅ 源表范围已明确：`chihiro.ezr_mall_prd_prod`、`chihiro.tbl_commodity_style`、`chihiro.tbl_commodity_extend_prop`
- ✅ 业务语义已明确：`(brand_code, itemNo)` 为最小业务粒度
- ✅ 目标表结构已明确：`belle_ai.products` 表结构完整
- ✅ 风险已识别：6 条风险已分析并给出缓解措施

#### ⚠️ 待确认事项
- ⚠️ 需要执行 B2 节 SQL，确认源表中是否存在同一 `(brand_code, itemNo)` 的多条记录
- ⚠️ 需要执行 C2 节 SQL，确认 `update_time` 抖动情况
- ⚠️ 需要确认源表的实际字段名和数据类型（特别是 `onSale`、`update_time` 等字段）
- ⚠️ 需要确认多表关联的关联字段（如 `commodity_id` 与 `itemNo` 的对应关系）

### E2. 必须解决的前置问题列表

#### 高优先级（阻塞实施）
1. **唯一键策略确认**
   - 执行 B2 节检测 SQL，确认源表数据情况
   - 确定目标表的唯一键设计（组合 SKU 或组合唯一索引）
   - 如果存在重复记录，确定去重策略

2. **源表结构确认**
   - 执行 E 节检测 SQL，确认源表的实际字段名和数据类型
   - 确认多表关联的关联字段
   - 建立完整的字段映射表

#### 中优先级（建议解决）
3. **update_time 抖动评估**
   - 执行 C2 节检测 SQL，评估抖动程度
   - 确定数据对比机制（哈希算法选择）
   - 设计 change_log 的变更类型判断逻辑

4. **脏数据处理策略**
   - 执行 D4 节检测 SQL，评估脏数据比例
   - 确定 JSON 格式校验和容错策略
   - 确定无效值的处理规则

#### 低优先级（可选优化）
5. **onSale 字段处理**
   - 确认业务需求：是否需要 `onSale` 字段
   - 如果不同品牌字段名不同，设计字段映射配置

6. **向量索引迁移规划**
   - 设计增量更新机制（可在 ETL 稳定运行后实施）
   - 保留全量重建能力作为降级方案

### E3. 下一步行动建议

1. **数据验证阶段**（建议在 P-ETL-2 前完成）:
   - 执行本报告中的所有检测 SQL（B2、C2、D4、D6 节）
   - 收集源表实际数据样本，验证字段映射关系
   - 确认多表关联逻辑

2. **设计确认阶段**（P-ETL-2 开始前）:
   - 确认唯一键设计方案
   - 确认字段映射表
   - 确认脏数据处理策略

3. **实施阶段**（P-ETL-2）:
   - 创建 `etl_watermark` 和 `product_change_log` 表
   - 实现 ETL 逻辑（基于本报告的风险缓解措施）
   - 实现数据对比和 change_log 记录逻辑

---

**报告完成时间**: 2024-12-19  
**报告版本**: P-ETL-1 修正版 V2（品牌维度锁定）  
**报告状态**: ✅ 已完成，可作为 P-ETL-2 实施依据  
**下一步**: 执行数据验证 SQL，进入 P-ETL-2 实施阶段
