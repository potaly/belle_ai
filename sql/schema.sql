-- ============================================
-- AI Smart Guide Service V1 - Database Schema
-- ============================================

-- 1. 商品表 (products)
CREATE TABLE products (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '商品主键ID',
    sku VARCHAR(64) NOT NULL UNIQUE COMMENT '商品SKU编码，唯一标识',
    name VARCHAR(255) NOT NULL COMMENT '商品名称',
    price DECIMAL(10,2) NOT NULL COMMENT '商品价格（元）',
    tags JSON NULL COMMENT '商品标签数组，如：["百搭","舒适","时尚"]',
    attributes JSON NULL COMMENT '商品属性JSON，包含color/material/scene/season等',
    description TEXT NULL COMMENT '商品详细描述',
    image_url VARCHAR(512) NULL COMMENT '商品主图URL',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL COMMENT '更新时间',
    INDEX idx_products_sku (sku) COMMENT 'SKU索引，用于快速查询'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='商品信息表';

-- 2. 用户行为日志表 (user_behavior_logs)
CREATE TABLE user_behavior_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '日志主键ID',
    user_id VARCHAR(64) NOT NULL COMMENT '用户ID',
    guide_id VARCHAR(64) NOT NULL COMMENT '导购ID',
    sku VARCHAR(64) NOT NULL COMMENT '商品SKU',
    event_type VARCHAR(32) NOT NULL COMMENT '事件类型：browse-浏览, enter_buy_page-进入购买页, click_size_chart-点击尺码表, favorite-收藏, share-分享',
    stay_seconds INT NOT NULL DEFAULT 0 COMMENT '停留时长（秒）',
    occurred_at DATETIME NOT NULL COMMENT '事件发生时间',
    INDEX idx_ubl_user_sku (user_id, sku, occurred_at) COMMENT '用户-商品-时间复合索引',
    INDEX idx_ubl_event_time (event_type, occurred_at) COMMENT '事件类型-时间索引'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户行为日志表';

-- 3. AI任务日志表 (ai_task_log)
CREATE TABLE ai_task_log (
    task_id VARCHAR(64) PRIMARY KEY COMMENT '任务ID，唯一标识',
    guide_id VARCHAR(64) NULL COMMENT '导购ID',
    scene_type VARCHAR(32) NOT NULL COMMENT '场景类型：copy-文案生成, product_analyze-商品分析, intent-意图分析',
    input_data TEXT NOT NULL COMMENT '输入数据（JSON格式）',
    output_result TEXT NULL COMMENT '输出结果（JSON格式）',
    model_name VARCHAR(64) NULL COMMENT '使用的模型名称',
    latency_ms INT NULL COMMENT '请求耗时（毫秒）',
    is_adopted TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否被采用：0-未采用, 1-已采用',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_ai_log_scene_time (scene_type, created_at) COMMENT '场景类型-时间索引'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='AI调用任务日志表';

-- 4. 导购表 (guides)
CREATE TABLE guides (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '导购主键ID',
    guide_id VARCHAR(64) NOT NULL UNIQUE COMMENT '导购唯一标识ID',
    name VARCHAR(64) NOT NULL COMMENT '导购姓名',
    shop_name VARCHAR(128) NULL COMMENT '所属门店名称',
    level VARCHAR(32) NULL COMMENT '导购等级：junior-初级, senior-高级, expert-专家',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='导购信息表';

