-- Create vision_feature_cache table for trace_id -> vision_features mapping (V6.0.0+)
-- This table is used as a fallback when Redis is not available

CREATE TABLE IF NOT EXISTS `vision_feature_cache` (
    `trace_id` VARCHAR(64) NOT NULL COMMENT '追踪ID（全局唯一）',
    `brand_code` VARCHAR(64) NOT NULL COMMENT '品牌编码',
    `scene` VARCHAR(32) NOT NULL DEFAULT 'guide_chat' COMMENT '使用场景',
    `vision_features_json` JSON NOT NULL COMMENT '视觉特征（JSON格式）',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `expires_at` DATETIME NOT NULL COMMENT '过期时间',
    PRIMARY KEY (`trace_id`),
    INDEX `idx_brand_code` (`brand_code`),
    INDEX `idx_expires_at` (`expires_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='视觉特征缓存表（trace_id映射）';

-- Cleanup expired records (optional, can be run periodically)
-- DELETE FROM vision_feature_cache WHERE expires_at < NOW();

