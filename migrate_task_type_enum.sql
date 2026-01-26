-- 迁移脚本：更新 tasks 表的 type 字段 ENUM 类型，添加新的任务类型
-- 执行方法：mysql -u your_user -p your_database < migrate_task_type_enum.sql

-- 修改 tasks 表的 type 字段 ENUM 类型，添加新的枚举值
ALTER TABLE `tasks` 
MODIFY COLUMN `type` ENUM(
    'register',
    'login',
    'post',
    'makeup',
    'beauty_flow',
    'create_user',
    'checkin',
    'face_upload',
    'makeup_creation',
    'post_community',
    'like_collect',
    'like_comment',
    'follow_user',
    'collect_topic'
) NOT NULL;

