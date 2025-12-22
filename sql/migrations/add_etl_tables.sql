-- ============================================
-- ETL Tables Migration Script
-- ============================================
-- 说明：此脚本由 DBA 执行，创建 ETL 相关表
-- 执行前请确认：
-- 1. products 表已存在 brand_code 字段
-- 2. products 表已存在 UNIQUE(brand_code, sku) 约束
-- ============================================

-- 1. ETL 水位表 (etl_watermark)
CREATE TABLE IF NOT EXISTS etl_watermark (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    table_name VARCHAR(64) NOT NULL UNIQUE COMMENT '表名，如 products_staging',
    last_processed_at DATETIME NOT NULL COMMENT '最后处理时间（src_updated_at）',
    last_processed_key VARCHAR(128) NOT NULL COMMENT '最后处理的组合键（style_brand_no#style_no），用于同秒不漏',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uq_etl_watermark_table_name (table_name),
    INDEX idx_watermark_table (table_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='ETL 水位表，记录处理进度';

-- 2. 商品变更日志表 (product_change_log)
CREATE TABLE IF NOT EXISTS product_change_log (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    brand_code VARCHAR(64) NOT NULL COMMENT '品牌代码',
    sku VARCHAR(64) NOT NULL COMMENT '商品SKU',
    data_version VARCHAR(64) NOT NULL COMMENT '数据版本哈希值',
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING' COMMENT '状态：PENDING/PROCESSED/FAILED',
    change_type VARCHAR(32) NOT NULL COMMENT '变更类型：CREATE/UPDATE/DELETE',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    UNIQUE KEY uq_change_log_brand_sku_version (brand_code, sku, data_version),
    INDEX idx_change_log_brand_sku (brand_code, sku),
    INDEX idx_change_log_status (status),
    INDEX idx_change_log_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='商品变更日志表，记录数据版本变更';

-- 验证表创建
SELECT 'etl_watermark' as table_name, COUNT(*) as record_count FROM etl_watermark
UNION ALL
SELECT 'product_change_log' as table_name, COUNT(*) as record_count FROM product_change_log;

