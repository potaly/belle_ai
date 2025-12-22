-- Migration: Add retry_count, last_error, updated_at to product_change_log
-- Purpose: Support vector sync retry mechanism and error tracking

-- Step 1: Check current table structure
SHOW COLUMNS FROM belle_ai.product_change_log;

-- Step 2: Add retry_count field (if not exists)
-- Note: Check if column exists before adding to avoid errors
SET @col_exists = (
    SELECT COUNT(*) 
    FROM information_schema.COLUMNS 
    WHERE TABLE_SCHEMA = 'belle_ai' 
      AND TABLE_NAME = 'product_change_log' 
      AND COLUMN_NAME = 'retry_count'
);

SET @sql = IF(@col_exists = 0,
    'ALTER TABLE belle_ai.product_change_log ADD COLUMN retry_count INT NOT NULL DEFAULT 0 COMMENT ''重试次数'' AFTER created_at',
    'SELECT ''Column retry_count already exists'' AS message'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Step 3: Add last_error field (if not exists)
SET @col_exists = (
    SELECT COUNT(*) 
    FROM information_schema.COLUMNS 
    WHERE TABLE_SCHEMA = 'belle_ai' 
      AND TABLE_NAME = 'product_change_log' 
      AND COLUMN_NAME = 'last_error'
);

SET @sql = IF(@col_exists = 0,
    'ALTER TABLE belle_ai.product_change_log ADD COLUMN last_error TEXT NULL COMMENT ''最后错误信息'' AFTER retry_count',
    'SELECT ''Column last_error already exists'' AS message'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Step 4: Add updated_at field (if not exists)
SET @col_exists = (
    SELECT COUNT(*) 
    FROM information_schema.COLUMNS 
    WHERE TABLE_SCHEMA = 'belle_ai' 
      AND TABLE_NAME = 'product_change_log' 
      AND COLUMN_NAME = 'updated_at'
);

SET @sql = IF(@col_exists = 0,
    'ALTER TABLE belle_ai.product_change_log ADD COLUMN updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT ''更新时间'' AFTER last_error',
    'SELECT ''Column updated_at already exists'' AS message'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Step 5: Verify table structure
SHOW COLUMNS FROM belle_ai.product_change_log;

-- Step 6: Verify existing data (sample)
SELECT 
    id, brand_code, sku, status, retry_count, 
    LEFT(last_error, 50) AS last_error_preview, 
    updated_at
FROM belle_ai.product_change_log
ORDER BY id DESC
LIMIT 10;

