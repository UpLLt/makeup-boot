-- 从 makeup.community 表初始化点赞池
-- 注意：like_pool 在 makeup_boot 库，community 在 makeup 库，需跨库查询
-- 按时间桶分别初始化，确保各桶都有数据
-- 每个桶内优先选已有点赞的数据（ORDER BY likes DESC）
-- 执行前请确保 like_pool 表已创建

-- 字段映射：
--   makeup.community.id           → like_pool.post_id
--   makeup.community.makeup_user_id → like_pool.makeup_id
--   makeup.community.user_id       → like_pool.author_user_id
--   makeup.community.created_at    → like_pool.published_at
--   makeup.community.likes         → like_pool.like_count

-- =====================================================
-- 按时间桶分别初始化，确保每个桶都有数据
-- =====================================================

-- 桶1: 今日（最多 50 条）
INSERT IGNORE INTO like_pool (post_id, makeup_id, author_user_id, published_at, like_count, created_at)
SELECT 
    c.id, c.makeup_user_id, c.user_id, c.created_at, COALESCE(c.likes, 0), NOW()
FROM makeup.community c
WHERE c.status = 1 AND c.deleted_at IS NULL AND c.makeup_user_id > 0
  AND c.created_at >= CURDATE()
ORDER BY c.likes DESC, c.created_at DESC
LIMIT 50;

-- 桶2: 昨日（最多 100 条）
INSERT IGNORE INTO like_pool (post_id, makeup_id, author_user_id, published_at, like_count, created_at)
SELECT 
    c.id, c.makeup_user_id, c.user_id, c.created_at, COALESCE(c.likes, 0), NOW()
FROM makeup.community c
WHERE c.status = 1 AND c.deleted_at IS NULL AND c.makeup_user_id > 0
  AND c.created_at >= DATE_SUB(CURDATE(), INTERVAL 1 DAY)
  AND c.created_at < CURDATE()
ORDER BY c.likes DESC, c.created_at DESC
LIMIT 100;

-- 桶3: 本周 2-7天前（最多 200 条）
INSERT IGNORE INTO like_pool (post_id, makeup_id, author_user_id, published_at, like_count, created_at)
SELECT 
    c.id, c.makeup_user_id, c.user_id, c.created_at, COALESCE(c.likes, 0), NOW()
FROM makeup.community c
WHERE c.status = 1 AND c.deleted_at IS NULL AND c.makeup_user_id > 0
  AND c.created_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
  AND c.created_at < DATE_SUB(CURDATE(), INTERVAL 2 DAY)
ORDER BY c.likes DESC, c.created_at DESC
LIMIT 200;

-- 桶4: 本月 8-30天前（最多 300 条）
INSERT IGNORE INTO like_pool (post_id, makeup_id, author_user_id, published_at, like_count, created_at)
SELECT 
    c.id, c.makeup_user_id, c.user_id, c.created_at, COALESCE(c.likes, 0), NOW()
FROM makeup.community c
WHERE c.status = 1 AND c.deleted_at IS NULL AND c.makeup_user_id > 0
  AND c.created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
  AND c.created_at < DATE_SUB(CURDATE(), INTERVAL 8 DAY)
ORDER BY c.likes DESC, c.created_at DESC
LIMIT 300;

-- 桶5: 30天以上（最多 350 条）
INSERT IGNORE INTO like_pool (post_id, makeup_id, author_user_id, published_at, like_count, created_at)
SELECT 
    c.id, c.makeup_user_id, c.user_id, c.created_at, COALESCE(c.likes, 0), NOW()
FROM makeup.community c
WHERE c.status = 1 AND c.deleted_at IS NULL AND c.makeup_user_id > 0
  AND c.created_at < DATE_SUB(CURDATE(), INTERVAL 30 DAY)
ORDER BY c.likes DESC, c.created_at DESC
LIMIT 350;

-- =====================================================
-- 用 makeup_likes 实际条数回填 like_pool.like_count
-- 注意：动态本身没有点赞表，点赞是针对妆造的（makeup_likes）
-- 统计该动态关联的妆造（makeup_id）被点赞的次数
-- =====================================================
UPDATE like_pool lp
SET lp.like_count = COALESCE((
    SELECT COUNT(*)
    FROM makeup.makeup_likes ml
    WHERE ml.makeup_id = lp.makeup_id
      AND ml.makeup_type = 'user_makeup'
), 0)
WHERE lp.makeup_id IS NOT NULL;

-- =====================================================
-- 查看 like_pool 导入结果（按时间桶统计）
-- =====================================================
SELECT 
    CASE 
        WHEN published_at >= CURDATE() THEN '今日'
        WHEN published_at >= DATE_SUB(CURDATE(), INTERVAL 1 DAY) THEN '昨日'
        WHEN published_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY) THEN '本周(2-7天)'
        WHEN published_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY) THEN '本月(8-30天)'
        ELSE '30天以上'
    END AS bucket,
    COUNT(*) AS count,
    SUM(CASE WHEN like_count > 0 THEN 1 ELSE 0 END) AS with_likes,
    SUM(CASE WHEN like_count = 0 THEN 1 ELSE 0 END) AS without_likes
FROM like_pool
GROUP BY 
    CASE 
        WHEN published_at >= CURDATE() THEN '今日'
        WHEN published_at >= DATE_SUB(CURDATE(), INTERVAL 1 DAY) THEN '昨日'
        WHEN published_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY) THEN '本周(2-7天)'
        WHEN published_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY) THEN '本月(8-30天)'
        ELSE '30天以上'
    END
ORDER BY 
    FIELD(bucket, '今日', '昨日', '本周(2-7天)', '本月(8-30天)', '30天以上');


-- =====================================================
-- 初始化 user_liked_posts 表
-- 注意：动态本身没有点赞表，点赞是针对妆造的（makeup_likes）
-- 这里通过妆造点赞记录，关联到动态（post_id）
-- 只导入：makeup_id 在 like_pool 中 且 user_id 在 makeup_boot.users 中（满足 FK）
-- =====================================================

-- 字段映射：
--   makeup.makeup_likes.user_id    → user_liked_posts.user_id
--   like_pool.post_id              → user_liked_posts.post_id（通过 makeup_id 关联）
--   makeup.makeup_likes.created_at → user_liked_posts.liked_at

-- 通过妆造点赞记录，关联到动态（post_id）
INSERT IGNORE INTO user_liked_posts (user_id, post_id, liked_at)
SELECT 
    ml.user_id,
    lp.post_id,
    ml.created_at AS liked_at
FROM makeup.makeup_likes ml
INNER JOIN like_pool lp ON ml.makeup_id = lp.makeup_id
WHERE ml.makeup_type = 'user_makeup'
  AND ml.user_id IS NOT NULL
  AND lp.post_id IS NOT NULL
  AND EXISTS (
      SELECT 1 FROM users u WHERE u.id = ml.user_id
  );

-- 查看 user_liked_posts 导入结果
SELECT 
    COUNT(*) AS total_liked_records,
    COUNT(DISTINCT user_id) AS unique_users,
    COUNT(DISTINCT post_id) AS unique_posts
FROM user_liked_posts;


-- =====================================================
-- 初始化 user_liked_comments 表（从 makeup.community_comment_like）
-- 只导入：comment_id 存在 且 user_id 在 makeup_boot.users 中（满足 FK）
-- =====================================================

-- 字段映射：
--   makeup.community_comment_like.user_id    → user_liked_comments.user_id
--   makeup.community_comment_like.comment_id → user_liked_comments.comment_id
--   makeup.community_comment.post_id         → user_liked_comments.post_id
--   makeup.community_comment.content         → user_liked_comments.comment_content
--   makeup.community_comment_like.created_at → user_liked_comments.liked_at

INSERT IGNORE INTO user_liked_comments (user_id, comment_id, post_id, comment_content, liked_at)
SELECT 
    ccl.user_id,
    ccl.comment_id,
    cc.post_id AS post_id,
    cc.content AS comment_content,
    COALESCE(ccl.created_at, NOW()) AS liked_at
FROM makeup.community_comment_like ccl
INNER JOIN makeup.community_comment cc ON ccl.comment_id = cc.id
WHERE ccl.user_id IS NOT NULL
  AND ccl.comment_id IS NOT NULL
  AND cc.post_id IS NOT NULL
  AND cc.status = 1  -- 只导入正常状态的评论
  AND cc.deleted_at IS NULL  -- 排除已删除的评论
  AND EXISTS (
      SELECT 1 FROM users u WHERE u.id = ccl.user_id
  );

-- 查看 user_liked_comments 导入结果
SELECT 
    COUNT(*) AS total_liked_comment_records,
    COUNT(DISTINCT user_id) AS unique_users,
    COUNT(DISTINCT comment_id) AS unique_comments,
    COUNT(DISTINCT post_id) AS unique_posts
FROM user_liked_comments;
