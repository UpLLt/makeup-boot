"""测试配置加载"""
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print(f"项目根目录: {project_root}")
print(f".env 文件路径: {project_root / '.env'}")
print(f".env 文件是否存在: {(project_root / '.env').exists()}")

if (project_root / '.env').exists():
    print("\n.env 文件内容:")
    print("-" * 50)
    with open(project_root / '.env', 'r', encoding='utf-8') as f:
        lines = f.readlines()
        for i, line in enumerate(lines, 1):
            # 隐藏敏感信息
            if 'SECRET' in line or 'KEY' in line:
                parts = line.split('=')
                if len(parts) == 2:
                    print(f"{i}: {parts[0]}={'***' if parts[1].strip() else '(空)'}")
                else:
                    print(f"{i}: {line.strip()}")
            else:
                print(f"{i}: {line.strip()}")
    print("-" * 50)

print("\n尝试加载配置...")
try:
    from app.config import get_settings
    settings = get_settings()
    
    print("\n配置值:")
    print(f"CF_R2_ENDPOINT: {settings.cf_r2_endpoint[:50] if settings.cf_r2_endpoint else '(空)'}")
    print(f"CF_R2_BUCKET: {settings.cf_r2_bucket if settings.cf_r2_bucket else '(空)'}")
    print(f"CF_R2_ACCESS_KEY_ID: {settings.cf_r2_access_key_id[:20] + '...' if settings.cf_r2_access_key_id else '(空)'}")
    print(f"CF_R2_SECRET_ACCESS_KEY: {'***' + settings.cf_r2_secret_access_key[-4:] if settings.cf_r2_secret_access_key else '(空)'}")
    print(f"CF_R2_DOMAIN: {settings.cf_r2_domain}")
    
    # 检查是否完整
    missing = []
    if not settings.cf_r2_endpoint or settings.cf_r2_endpoint.strip() == "":
        missing.append("CF_R2_ENDPOINT")
    if not settings.cf_r2_bucket or settings.cf_r2_bucket.strip() == "":
        missing.append("CF_R2_BUCKET")
    if not settings.cf_r2_access_key_id or settings.cf_r2_access_key_id.strip() == "":
        missing.append("CF_R2_ACCESS_KEY_ID")
    if not settings.cf_r2_secret_access_key or settings.cf_r2_secret_access_key.strip() == "":
        missing.append("CF_R2_SECRET_ACCESS_KEY")
    
    if missing:
        print(f"\n❌ 缺少配置项: {', '.join(missing)}")
    else:
        print("\n✅ 所有配置项都已设置")
        
except Exception as e:
    print(f"\n❌ 加载配置失败: {e}")
    import traceback
    traceback.print_exc()


