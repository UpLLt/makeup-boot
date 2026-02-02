-- 将 like_pool.published_at 均匀分布到四个时间桶（today / yesterday / week / month）
-- 与代码中 _get_bucket_time_range 的北京时间桶定义一致
-- 执行前请备份；执行时以应用库（DB_NAME）为当前库

-- 以北京时间为基准（若 MySQL 为 UTC，则 +8 小时得到北京日期）
SET @bj_now     = NOW() + INTERVAL 8 HOUR;
SET @today_0    = CONCAT(DATE(@bj_now), ' 00:00:00');
SET @yesterday_0 = CONCAT(DATE(@bj_now) - INTERVAL 1 DAY, ' 00:00:00');
SET @days7_0    = CONCAT(DATE(@bj_now) - INTERVAL 7 DAY, ' 00:00:00');
SET @days2_0    = CONCAT(DATE(@bj_now) - INTERVAL 2 DAY, ' 00:00:00');
SET @days8_0    = CONCAT(DATE(@bj_now) - INTERVAL 8 DAY, ' 00:00:00');
SET @days30_0   = CONCAT(DATE(@bj_now) - INTERVAL 30 DAY, ' 00:00:00');

-- 按 id 均匀分到 4 个桶：today / yesterday / week / month
UPDATE like_pool SET published_at = CASE
  WHEN id % 4 = 0 THEN
    -- today：今天 0 点～当前时刻之间随机（至少 1 小时内）
    @today_0 + INTERVAL GREATEST(1, FLOOR(RAND() * TIMESTAMPDIFF(HOUR, @today_0, @bj_now))) HOUR
        + INTERVAL FLOOR(RAND() * 60) MINUTE
  WHEN id % 4 = 1 THEN
    -- yesterday：昨天 0 点～24 点内随机
    @yesterday_0 + INTERVAL (8 + FLOOR(RAND() * 12)) HOUR + INTERVAL FLOOR(RAND() * 60) MINUTE
  WHEN id % 4 = 2 THEN
    -- week：2～7 天前，5 天范围内随机
    @days7_0 + INTERVAL FLOOR(RAND() * 5 * 24) HOUR + INTERVAL FLOOR(RAND() * 60) MINUTE
  WHEN id % 4 = 3 THEN
    -- month：8～30 天前，22 天范围内随机
    @days30_0 + INTERVAL FLOOR(RAND() * 22 * 24) HOUR + INTERVAL FLOOR(RAND() * 60) MINUTE
END
WHERE id > 0;

-- 校验：各桶数量（需在应用库执行，且与代码桶定义一致时才有参考意义）
-- SELECT 'today' AS bucket, COUNT(*) AS cnt FROM like_pool
--   WHERE published_at >= @today_0 AND published_at < @bj_now + INTERVAL 1 SECOND
-- UNION ALL SELECT 'yesterday', COUNT(*) FROM like_pool
--   WHERE published_at >= @yesterday_0 AND published_at < @today_0
-- UNION ALL SELECT 'week', COUNT(*) FROM like_pool
--   WHERE published_at >= @days7_0 AND published_at < @days2_0
-- UNION ALL SELECT 'month', COUNT(*) FROM like_pool
--   WHERE published_at >= @days30_0 AND published_at < @days8_0;
