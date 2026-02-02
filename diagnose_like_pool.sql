-- 诊断「点赞池无可用帖子」问题
-- 在【应用库】（.env 里 DB_NAME 对应的库，有 like_pool / user_liked_posts / users）执行
-- 把下面 10664 换成你当前报错里的 user_id

SET @uid = 10664;

-- 1. like_pool 总条数、作者分布
SELECT 'like_pool 总条数' AS item, COUNT(*) AS val FROM like_pool
UNION ALL
SELECT '不同作者数', COUNT(DISTINCT author_user_id) FROM like_pool
UNION ALL
SELECT '作者=当前用户的条数(会被排除)', COUNT(*) FROM like_pool WHERE author_user_id = @uid
UNION ALL
SELECT '作者≠当前用户的条数', COUNT(*) FROM like_pool WHERE author_user_id != @uid;

-- 2. 当前用户已点赞的 post 数
SELECT 'user_liked_posts 中该用户已点赞数' AS item, COUNT(*) AS val FROM user_liked_posts WHERE user_id = @uid;

-- 3. 排除「自己的帖子」且排除「已点赞」后，剩余可选条数
SELECT '排除自己+已点赞后可选条数' AS item, COUNT(*) AS val
FROM like_pool lp
WHERE lp.author_user_id != @uid
  AND lp.post_id NOT IN (SELECT post_id FROM user_liked_posts WHERE user_id = @uid);

-- 4. published_at 范围（看是否落在今天/昨天/本周/30天桶内）
SELECT
  MIN(published_at) AS min_published_at,
  MAX(published_at) AS max_published_at,
  COUNT(*) AS total
FROM like_pool
WHERE author_user_id != @uid
  AND post_id NOT IN (SELECT post_id FROM user_liked_posts WHERE user_id = @uid);

-- 5. 按「时间桶」看可选数量（与代码里桶定义一致：今天/昨天/本周2~7天/30天8~30天）
-- 今天 0 点至今
SELECT 'today 桶可选数' AS bucket, COUNT(*) AS cnt FROM like_pool lp
WHERE lp.author_user_id != @uid AND lp.post_id NOT IN (SELECT post_id FROM user_liked_posts WHERE user_id = @uid)
  AND lp.published_at >= DATE_FORMAT(NOW(), '%Y-%m-%d 00:00:00')
  AND lp.published_at < NOW() + INTERVAL 1 SECOND
UNION ALL
-- 昨天 0 点～今天 0 点
SELECT 'yesterday', COUNT(*) FROM like_pool lp
WHERE lp.author_user_id != @uid AND lp.post_id NOT IN (SELECT post_id FROM user_liked_posts WHERE user_id = @uid)
  AND lp.published_at >= DATE_FORMAT(NOW() - INTERVAL 1 DAY, '%Y-%m-%d 00:00:00')
  AND lp.published_at < DATE_FORMAT(NOW(), '%Y-%m-%d 00:00:00')
UNION ALL
-- 本周：7天前 0 点～2天前 0 点
SELECT 'week', COUNT(*) FROM like_pool lp
WHERE lp.author_user_id != @uid AND lp.post_id NOT IN (SELECT post_id FROM user_liked_posts WHERE user_id = @uid)
  AND lp.published_at >= DATE_FORMAT(NOW() - INTERVAL 7 DAY, '%Y-%m-%d 00:00:00')
  AND lp.published_at < DATE_FORMAT(NOW() - INTERVAL 2 DAY, '%Y-%m-%d 00:00:00')
UNION ALL
-- 30天：30天前 0 点～8天前 0 点
SELECT 'month', COUNT(*) FROM like_pool lp
WHERE lp.author_user_id != @uid AND lp.post_id NOT IN (SELECT post_id FROM user_liked_posts WHERE user_id = @uid)
  AND lp.published_at >= DATE_FORMAT(NOW() - INTERVAL 30 DAY, '%Y-%m-%d 00:00:00')
  AND lp.published_at < DATE_FORMAT(NOW() - INTERVAL 8 DAY, '%Y-%m-%d 00:00:00');
