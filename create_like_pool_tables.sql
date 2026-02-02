-- 点赞池相关表创建脚本
-- 执行前请确保数据库连接正确

-- 1. 点赞池表：存储可被点赞/评论的社区动态
CREATE TABLE IF NOT EXISTS `like_pool` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `post_id` BIGINT UNSIGNED NOT NULL COMMENT '社区动态ID',
    `makeup_id` BIGINT UNSIGNED DEFAULT NULL COMMENT '妆造ID',
    `author_user_id` BIGINT UNSIGNED NOT NULL COMMENT '发布该动态的用户ID，消费时排除自己',
    `published_at` DATETIME NOT NULL COMMENT '动态发布时间，用于时间分桶',
    `like_count` INT NOT NULL DEFAULT 0 COMMENT '当前点赞数，非今天桶优先选已有点赞的帖',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '入库时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_post_id` (`post_id`),
    KEY `idx_author_user_id` (`author_user_id`),
    KEY `idx_published_at` (`published_at`),
    KEY `idx_like_count` (`like_count`),
    KEY `idx_makeup_id` (`makeup_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='点赞池表';

-- 2. 用户已点赞记录表：避免重复点赞
CREATE TABLE IF NOT EXISTS `user_liked_posts` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `user_id` BIGINT UNSIGNED NOT NULL COMMENT '点赞用户ID',
    `post_id` BIGINT UNSIGNED NOT NULL COMMENT '动态ID',
    `liked_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '点赞时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_user_post` (`user_id`, `post_id`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_post_id` (`post_id`),
    KEY `idx_liked_at` (`liked_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户已点赞记录表';
