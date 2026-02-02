-- 用户已点赞评论表：记录点赞的评论及内容，便于后续引用（如回复该评论）
-- user_id 类型需与 users.id 一致（通常为 INT），否则外键会报 incompatible
CREATE TABLE IF NOT EXISTS `user_liked_comments` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `user_id` INT NOT NULL COMMENT '点赞用户ID，与 users.id 类型一致',
    `comment_id` BIGINT UNSIGNED NOT NULL COMMENT '评论ID',
    `post_id` BIGINT UNSIGNED NOT NULL COMMENT '所属动态ID',
    `comment_content` TEXT DEFAULT NULL COMMENT '评论内容，便于引用',
    `liked_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '点赞时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_user_comment` (`user_id`, `comment_id`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_comment_id` (`comment_id`),
    KEY `idx_post_id` (`post_id`),
    KEY `idx_liked_at` (`liked_at`),
    CONSTRAINT `fk_user_liked_comments_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户已点赞评论记录表';
