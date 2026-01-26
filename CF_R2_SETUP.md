# Cloudflare R2 配置指南

## 获取 Cloudflare R2 配置信息

### 1. 登录 Cloudflare Dashboard
访问 https://dash.cloudflare.com/ 并登录你的账号

### 2. 进入 R2 管理页面
- 在左侧菜单中找到 "R2"
- 如果没有看到，可能需要先开通 R2 服务

### 3. 创建 API Token
1. 点击 "Manage R2 API Tokens"
2. 点击 "Create API token"
3. 配置：
   - Token name: 自定义名称（如：makeup-boot-upload）
   - Permissions: 选择 "Object Read & Write" 或 "Admin Read & Write"
   - TTL: 根据需要设置过期时间（或留空表示永不过期）
4. 创建后会显示 **Access Key ID** 和 **Secret Access Key**，请妥善保存

### 4. 创建 Bucket（如果还没有）
1. 在 R2 页面点击 "Create bucket"
2. 输入 Bucket 名称（如：makeup）
3. 选择位置（Location）
4. 创建完成

### 5. 获取 Endpoint URL
- Endpoint URL 格式：`https://<account-id>.r2.cloudflarestorage.com`
- 你可以在 R2 设置或 API Token 页面找到 Account ID
- 完整的 Endpoint 应该是：`https://86dca7860141f20c8270afa4704733b4.r2.cloudflarestorage.com`（替换为你的 Account ID）

### 6. 配置自定义域名（可选）
如果你想使用自定义域名访问图片：
1. 在 R2 Bucket 设置中找到 "Public access"
2. 配置自定义域名（如：img.mindsecho.com）
3. 在 Cloudflare DNS 中添加 CNAME 记录指向 R2

## 配置 .env 文件

在项目根目录的 `.env` 文件中添加以下配置：

```env
# Cloudflare R2 配置
CF_R2_ENDPOINT=https://86dca7860141f20c8270afa4704733b4.r2.cloudflarestorage.com
CF_R2_BUCKET=makeup
CF_R2_ACCESS_KEY_ID=your-access-key-id-here
CF_R2_SECRET_ACCESS_KEY=your-secret-access-key-here
CF_R2_DOMAIN=img.mindsecho.com
```

### 配置说明

- **CF_R2_ENDPOINT**: R2 的 API 端点 URL
  - 格式：`https://<account-id>.r2.cloudflarestorage.com`
  - 从 Cloudflare Dashboard 获取

- **CF_R2_BUCKET**: Bucket 名称
  - 你创建的 R2 Bucket 的名称

- **CF_R2_ACCESS_KEY_ID**: API Token 的 Access Key ID
  - 创建 API Token 时获得

- **CF_R2_SECRET_ACCESS_KEY**: API Token 的 Secret Access Key
  - 创建 API Token 时获得（只显示一次，请妥善保存）

- **CF_R2_DOMAIN**: 自定义域名（可选）
  - 如果配置了自定义域名，使用自定义域名
  - 如果没有，可以使用 R2 的默认公共 URL

## 测试配置

配置完成后，重启应用，然后尝试上传图片。如果配置正确，图片应该能够成功上传到 Cloudflare R2。

## 参考信息

根据 `test123/server.go` 中的配置示例：
- Endpoint: `https://86dca7860141f20c8270afa4704733b4.r2.cloudflarestorage.com`
- Bucket: `makeup`
- Domain: `img.mindsecho.com`

如果你的账号不同，请替换为你的实际配置值。


