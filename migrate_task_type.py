"""迁移脚本：更新 tasks 表的 type 字段 ENUM 类型"""
import pymysql
from app.config import get_settings

settings = get_settings()

# 连接数据库
connection = pymysql.connect(
    host=settings.db_host,
    port=settings.db_port,
    user=settings.db_user,
    password=settings.db_password,
    database=settings.db_name,
    charset='utf8mb4'
)

try:
    with connection.cursor() as cursor:
        # 修改 tasks 表的 type 字段 ENUM 类型
        sql = """
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
        """
        print("Updating tasks table type field ENUM type...")
        cursor.execute(sql)
        connection.commit()
        print("Success! tasks table type field has been updated")
except Exception as e:
    print(f"Migration failed: {e}")
    connection.rollback()
finally:
    connection.close()

