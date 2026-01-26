-- 删除未使用的表：makeup_presets 和 posts
-- 执行前请确保已备份数据库

-- 禁用外键检查，允许删除有外键依赖的表
SET FOREIGN_KEY_CHECKS = 0;

-- 1. 删除 posts 表（如果存在）
DROP TABLE IF EXISTS `posts`;

-- 2. 删除 makeup_presets 表相关的外键和字段
-- 先尝试删除外键（如果存在，MySQL不支持 IF EXISTS，所以需要先查询）
-- 查询 users 表中的外键名称
SET @fk_name = (
    SELECT CONSTRAINT_NAME 
    FROM information_schema.KEY_COLUMN_USAGE 
    WHERE TABLE_SCHEMA = DATABASE() 
    AND TABLE_NAME = 'users' 
    AND COLUMN_NAME = 'makeup_preset_id' 
    AND REFERENCED_TABLE_NAME = 'makeup_presets'
    LIMIT 1
);

-- 如果找到外键，则删除它
SET @sql = IF(@fk_name IS NOT NULL, 
    CONCAT('ALTER TABLE `users` DROP FOREIGN KEY `', @fk_name, '`'), 
    'SELECT "No foreign key found" AS message'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 删除 makeup_preset_id 字段（如果存在）
SET @col_exists = (
    SELECT COUNT(*) 
    FROM information_schema.COLUMNS 
    WHERE TABLE_SCHEMA = DATABASE() 
    AND TABLE_NAME = 'users' 
    AND COLUMN_NAME = 'makeup_preset_id'
);

SET @sql = IF(@col_exists > 0, 
    'ALTER TABLE `users` DROP COLUMN `makeup_preset_id`', 
    'SELECT "Column does not exist" AS message'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 删除 makeup_presets 表
DROP TABLE IF EXISTS `makeup_presets`;

-- 恢复外键检查
SET FOREIGN_KEY_CHECKS = 1;

-- 验证删除结果
SHOW TABLES LIKE 'posts';
SHOW TABLES LIKE 'makeup_presets';
