-- ============================================
-- Products Table Unique Constraint Migration
-- ============================================
-- 说明：此脚本由 DBA 执行，修改 products 表唯一约束
-- 执行前必须：
-- 1. 执行 SHOW INDEX FROM belle_ai.products WHERE Key_name != 'PRIMARY';
-- 2. 根据实际输出确定需要删除的索引名称
-- 3. 确认 brand_code 字段已存在
-- ============================================

-- 步骤1: 检查当前索引（必须执行，不能写死索引名）
-- SHOW INDEX FROM belle_ai.products WHERE Key_name != 'PRIMARY';
-- 
-- 预期输出示例：
-- | Table   | Non_unique | Key_name        | Seq_in_index | Column_name |
-- | products| 0          | sku             | 1            | sku         |  <- 唯一索引
-- | products| 1          | idx_products_sku | 1            | sku         |  <- 普通索引
-- 
-- ⚠️ 关键：必须根据实际输出确定需要删除的唯一索引名称（可能是 'sku' 或其他名称）

-- 步骤2: 检查 brand_code 字段是否存在
-- SHOW CREATE TABLE belle_ai.products;
-- 确认输出中包含 brand_code 字段定义

-- 步骤3: 检查数据冲突（可选，建议执行）
-- SELECT 
--     sku,
--     COUNT(DISTINCT brand_code) as brand_code_count,
--     GROUP_CONCAT(DISTINCT brand_code ORDER BY brand_code) as brand_codes,
--     COUNT(*) as total_records
-- FROM belle_ai.products
-- WHERE brand_code IS NOT NULL
-- GROUP BY sku
-- HAVING COUNT(DISTINCT brand_code) > 1
-- ORDER BY brand_code_count DESC, sku
-- LIMIT 100;

-- 步骤4: 如果存在 brand_code 为 NULL 的记录，需要先填充默认值
-- UPDATE belle_ai.products 
-- SET brand_code = 'DEFAULT' 
-- WHERE brand_code IS NULL;

-- 步骤5: 删除旧的唯一索引（索引名必须从步骤1的实际输出中获取）
-- ⚠️ 不能写死为 'sku'，必须先执行 SHOW INDEX 识别真实索引名
-- ALTER TABLE belle_ai.products DROP INDEX <真实索引名>;

-- 步骤6: 添加新的组合唯一索引
ALTER TABLE belle_ai.products 
ADD UNIQUE INDEX idx_products_brand_sku (brand_code, sku);

-- 步骤7: 添加 sku 的普通索引（用于查询性能，如果不存在则创建）
-- 如果 idx_products_sku 已存在，可跳过此步骤
ALTER TABLE belle_ai.products 
ADD INDEX idx_products_sku (sku);

-- 步骤8: 验证索引创建
-- SHOW INDEX FROM belle_ai.products WHERE Key_name = 'idx_products_brand_sku';
-- 预期输出应包含两行：
-- | products | 0 | idx_products_brand_sku | 1 | brand_code |
-- | products | 0 | idx_products_brand_sku | 2 | sku        |

