-- 修复表字段类型不匹配问题
-- 确保所有外键字段类型与引用字段类型一致

SET FOREIGN_KEY_CHECKS = 0;

-- 1. 检查并修复 users 表的 id 字段类型
-- 先查看当前类型
SELECT COLUMN_NAME, DATA_TYPE, COLUMN_TYPE 
FROM information_schema.COLUMNS 
WHERE TABLE_SCHEMA = DATABASE() 
AND TABLE_NAME = 'users' 
AND COLUMN_NAME = 'id';

-- 确保 users.id 是 BIGINT UNSIGNED（MySQL 推荐的主键类型）
ALTER TABLE `users` MODIFY COLUMN `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT;

-- 2. 修复 tasks 表的 user_id 字段类型，使其与 users.id 匹配
-- 先删除现有的外键约束
SET @fk_name = (
    SELECT CONSTRAINT_NAME 
    FROM information_schema.KEY_COLUMN_USAGE 
    WHERE TABLE_SCHEMA = DATABASE() 
    AND TABLE_NAME = 'tasks' 
    AND COLUMN_NAME = 'user_id' 
    AND REFERENCED_TABLE_NAME = 'users'
    LIMIT 1
);

SET @sql = IF(@fk_name IS NOT NULL, 
    CONCAT('ALTER TABLE `tasks` DROP FOREIGN KEY `', @fk_name, '`'), 
    'SELECT "No foreign key found" AS message'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 修改 tasks.user_id 类型为 BIGINT UNSIGNED
ALTER TABLE `tasks` MODIFY COLUMN `user_id` BIGINT UNSIGNED NULL;

-- 重新创建外键约束
ALTER TABLE `tasks` 
ADD CONSTRAINT `tasks_ibfk_1` 
FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) 
ON DELETE SET NULL ON UPDATE CASCADE;

-- 3. 修复其他表的外键字段类型
-- task_logs.task_id
SET @fk_name = (
    SELECT CONSTRAINT_NAME 
    FROM information_schema.KEY_COLUMN_USAGE 
    WHERE TABLE_SCHEMA = DATABASE() 
    AND TABLE_NAME = 'task_logs' 
    AND COLUMN_NAME = 'task_id' 
    AND REFERENCED_TABLE_NAME = 'tasks'
    LIMIT 1
);

SET @sql = IF(@fk_name IS NOT NULL, 
    CONCAT('ALTER TABLE `task_logs` DROP FOREIGN KEY `', @fk_name, '`'), 
    'SELECT "No foreign key found" AS message'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

ALTER TABLE `task_logs` MODIFY COLUMN `task_id` BIGINT UNSIGNED NOT NULL;
ALTER TABLE `tasks` MODIFY COLUMN `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT;

ALTER TABLE `task_logs` 
ADD CONSTRAINT `task_logs_ibfk_1` 
FOREIGN KEY (`task_id`) REFERENCES `tasks` (`id`) 
ON DELETE CASCADE ON UPDATE CASCADE;

-- user_activity_log.user_id
SET @fk_name = (
    SELECT CONSTRAINT_NAME 
    FROM information_schema.KEY_COLUMN_USAGE 
    WHERE TABLE_SCHEMA = DATABASE() 
    AND TABLE_NAME = 'user_activity_log' 
    AND COLUMN_NAME = 'user_id' 
    AND REFERENCED_TABLE_NAME = 'users'
    LIMIT 1
);

SET @sql = IF(@fk_name IS NOT NULL, 
    CONCAT('ALTER TABLE `user_activity_log` DROP FOREIGN KEY `', @fk_name, '`'), 
    'SELECT "No foreign key found" AS message'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

ALTER TABLE `user_activity_log` MODIFY COLUMN `user_id` BIGINT UNSIGNED NOT NULL;

ALTER TABLE `user_activity_log` 
ADD CONSTRAINT `user_activity_log_ibfk_1` 
FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) 
ON DELETE CASCADE ON UPDATE CASCADE;

-- makeups.user_id
SET @fk_name = (
    SELECT CONSTRAINT_NAME 
    FROM information_schema.KEY_COLUMN_USAGE 
    WHERE TABLE_SCHEMA = DATABASE() 
    AND TABLE_NAME = 'makeups' 
    AND COLUMN_NAME = 'user_id' 
    AND REFERENCED_TABLE_NAME = 'users'
    LIMIT 1
);

SET @sql = IF(@fk_name IS NOT NULL, 
    CONCAT('ALTER TABLE `makeups` DROP FOREIGN KEY `', @fk_name, '`'), 
    'SELECT "No foreign key found" AS message'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

ALTER TABLE `makeups` MODIFY COLUMN `user_id` BIGINT UNSIGNED NOT NULL;

ALTER TABLE `makeups` 
ADD CONSTRAINT `makeups_ibfk_1` 
FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) 
ON DELETE CASCADE ON UPDATE CASCADE;

-- 恢复外键检查
SET FOREIGN_KEY_CHECKS = 1;

-- 验证修复结果
SELECT 
    TABLE_NAME,
    COLUMN_NAME,
    DATA_TYPE,
    COLUMN_TYPE,
    IS_NULLABLE
FROM information_schema.COLUMNS 
WHERE TABLE_SCHEMA = DATABASE() 
AND COLUMN_NAME IN ('id', 'user_id', 'task_id')
ORDER BY TABLE_NAME, COLUMN_NAME;
