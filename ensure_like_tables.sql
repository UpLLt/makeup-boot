-- 确保点赞相关表存在（若已存在则跳过）
-- 在 makeup_boot 库执行：mysql -h 127.0.0.1 -P 3306 -u root -p makeup_boot < ensure_like_tables.sql

-- 1. 点赞池表（若无）
CREATE TABLE IF NOT EXISTS `like_pool` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `post_id` BIGINT UNSIGNED NOT NULL COMMENT '社区动态ID',
    `makeup_id` BIGINT UNSIGNED DEFAULT NULL COMMENT '妆造ID',
    `author_user_id` BIGINT UNSIGNED NOT NULL COMMENT '发布该动态的用户ID',
    `published_at` DATETIME NOT NULL COMMENT '动态发布时间',
    `like_count` INT NOT NULL DEFAULT 0 COMMENT '当前点赞数',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '入库时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_post_id` (`post_id`),
    KEY `idx_author_user_id` (`author_user_id`),
    KEY `idx_published_at` (`published_at`),
    KEY `idx_like_count` (`like_count`),
    KEY `idx_makeup_id` (`makeup_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='点赞池表';

-- 2. 用户已点赞记录表（若无）
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

-- 3. 用户已点赞评论表（若无）
CREATE TABLE IF NOT EXISTS `user_liked_comments` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `user_id` INT NOT NULL COMMENT '点赞用户ID',
    `comment_id` BIGINT UNSIGNED NOT NULL COMMENT '评论ID',
    `post_id` BIGINT UNSIGNED NOT NULL COMMENT '所属动态ID',
    `comment_content` TEXT DEFAULT NULL COMMENT '评论内容',
    `liked_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '点赞时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_user_comment` (`user_id`, `comment_id`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_comment_id` (`comment_id`),
    KEY `idx_post_id` (`post_id`),
    KEY `idx_liked_at` (`liked_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户已点赞评论记录表';
