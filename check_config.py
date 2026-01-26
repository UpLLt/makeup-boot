"""检查 Cloudflare R2 配置脚本"""
from app.config import get_settings

settings = get_settings()

print("=" * 50)
print("Cloudflare R2 配置检查")
print("=" * 50)
print(f"CF_R2_ENDPOINT: {'已配置' if settings.cf_r2_endpoint else '❌ 未配置'}")
print(f"  - 值: {settings.cf_r2_endpoint[:50] + '...' if len(settings.cf_r2_endpoint) > 50 else settings.cf_r2_endpoint}")
print(f"CF_R2_BUCKET: {'已配置' if settings.cf_r2_bucket else '❌ 未配置'}")
print(f"  - 值: {settings.cf_r2_bucket}")
print(f"CF_R2_ACCESS_KEY_ID: {'已配置' if settings.cf_r2_access_key_id else '❌ 未配置'}")
print(f"  - 值: {settings.cf_r2_access_key_id[:20] + '...' if len(settings.cf_r2_access_key_id) > 20 else settings.cf_r2_access_key_id}")
print(f"CF_R2_SECRET_ACCESS_KEY: {'已配置' if settings.cf_r2_secret_access_key else '❌ 未配置'}")
print(f"  - 值: {'***' + settings.cf_r2_secret_access_key[-4:] if len(settings.cf_r2_secret_access_key) > 4 else '***'}")
print(f"CF_R2_DOMAIN: {settings.cf_r2_domain}")
print("=" * 50)

# 检查配置是否完整
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
    print(f"\n❌ 配置不完整，缺少以下配置项：")
    for item in missing:
        print(f"  - {item}")
    print("\n请在 .env 文件中添加这些配置项，然后重启应用。")
    print("\n示例配置（请替换为你的实际值）：")
    print("CF_R2_ENDPOINT=https://your-account-id.r2.cloudflarestorage.com")
    print("CF_R2_BUCKET=your-bucket-name")
    print("CF_R2_ACCESS_KEY_ID=your-access-key-id")
    print("CF_R2_SECRET_ACCESS_KEY=your-secret-access-key")
    print("CF_R2_DOMAIN=img.mindsecho.com")
else:
    print("\n✅ 所有配置项都已设置！")
    try:
        from app.clients.cf_r2 import get_r2_client
        client = get_r2_client()
        print("✅ R2 客户端初始化成功！")
    except Exception as e:
        print(f"\n❌ R2 客户端初始化失败: {e}")


