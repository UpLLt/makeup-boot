-- 清理用户：按外键依赖顺序删除关联数据，最后清空 users 表
-- 执行前请备份数据库；执行后所有用户及关联的任务、日志、妆造、点赞记录等将被删除

-- 1. 删除任务执行日志（依赖 tasks.id）
DELETE FROM `task_logs`;

-- 2. 删除任务（依赖 users.id）
DELETE FROM `tasks`;

-- 3. 删除用户行为日志（依赖 users.id）
DELETE FROM `user_activity_log`;

-- 4. 删除妆造记录表 makeups（依赖 users.id）
DELETE FROM `makeups`;

-- 5. 删除用户点赞记录（依赖 users.id）
DELETE FROM `user_liked_posts`;

-- 6. 可选：清理点赞池中由“本库用户”发布的动态（like_pool.author_user_id 无外键，仅逻辑关联）
-- 若希望点赞池也清空或只保留“非本库用户”的数据，可取消下面注释：
-- DELETE FROM `like_pool` WHERE `author_user_id` IN (SELECT `id` FROM `users`);
-- 若点赞池 author_user_id 全是本库用户，可直接清空：
-- DELETE FROM `like_pool`;

-- 7. 清空用户表
DELETE FROM `users`;

-- 可选：重置自增 ID（下次插入从 1 开始）
-- ALTER TABLE `users` AUTO_INCREMENT = 1;
-- ALTER TABLE `tasks` AUTO_INCREMENT = 1;
-- ALTER TABLE `task_logs` AUTO_INCREMENT = 1;
-- ALTER TABLE `user_activity_log` AUTO_INCREMENT = 1;
-- ALTER TABLE `makeups` AUTO_INCREMENT = 1;
-- ALTER TABLE `user_liked_posts` AUTO_INCREMENT = 1;
