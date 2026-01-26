"""Cloudflare R2 OSS client."""
import hashlib
import os
import time
from pathlib import Path
from typing import Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config import get_settings

settings = get_settings()


class CloudflareR2Client:
    """Cloudflare R2 OSS client."""

    def __init__(self):
        """Initialize the R2 client."""
        # 检查配置是否完整
        missing_configs = []
        if not settings.cf_r2_endpoint or settings.cf_r2_endpoint.strip() == "":
            missing_configs.append("CF_R2_ENDPOINT")
        if not settings.cf_r2_bucket or settings.cf_r2_bucket.strip() == "":
            missing_configs.append("CF_R2_BUCKET")
        if not settings.cf_r2_access_key_id or settings.cf_r2_access_key_id.strip() == "":
            missing_configs.append("CF_R2_ACCESS_KEY_ID")
        if not settings.cf_r2_secret_access_key or settings.cf_r2_secret_access_key.strip() == "":
            missing_configs.append("CF_R2_SECRET_ACCESS_KEY")
        
        if missing_configs:
            raise ValueError(
                f"Cloudflare R2 配置不完整，请在 .env 文件中配置以下项：\n"
                f"{', '.join(missing_configs)}\n"
                f"配置后请重启应用。"
            )

        # 创建 S3 兼容客户端
        self.s3_client = boto3.client(
            's3',
            endpoint_url=settings.cf_r2_endpoint,
            aws_access_key_id=settings.cf_r2_access_key_id,
            aws_secret_access_key=settings.cf_r2_secret_access_key,
            config=Config(signature_version='s3v4'),
            region_name='auto'
        )
        self.bucket = settings.cf_r2_bucket
        self.domain = settings.cf_r2_domain

    def upload_file(
        self,
        file_path: str | Path,
        remote_path: Optional[str] = None,
        content_type: Optional[str] = None
    ) -> str:
        """
        上传文件到 Cloudflare R2
        
        Args:
            file_path: 本地文件路径
            remote_path: 远程路径（可选，如果不提供会自动生成）
            content_type: 内容类型（可选，如果不提供会根据文件扩展名推断）
        
        Returns:
            上传后的完整URL
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # 生成远程路径
        if remote_path is None:
            today = time.strftime("%Y-%m-%d")
            file_name = file_path.name
            ext = file_path.suffix
            
            # 生成 MD5 哈希
            file_stat = file_path.stat()
            hash_input = f"{file_stat.st_mtime_ns}{file_name}"
            hash_bytes = hashlib.md5(hash_input.encode()).digest()
            hash_str = hash_bytes.hex()[:16]
            
            # 清理文件名
            name_without_ext = file_name[:file_name.rfind(ext)] if ext else file_name
            clean_name = name_without_ext.replace(" ", "").replace("_", "").replace("-", "")
            
            # 构建新文件名
            new_file_name = f"{hash_str}{clean_name}{ext}"
            remote_path = f"uploads/{today}/{new_file_name}"
        
        # 获取内容类型
        if content_type is None:
            content_type = self._get_content_type(file_path.suffix)
        
        # 上传文件
        try:
            with open(file_path, 'rb') as file_data:
                self.s3_client.put_object(
                    Bucket=self.bucket,
                    Key=remote_path,
                    Body=file_data,
                    ContentType=content_type
                )
        except ClientError as e:
            raise Exception(f"Failed to upload file: {e}")

        # 返回完整URL
        return f"https://{self.domain}/{remote_path}"

    def upload_file_obj(
        self,
        file_obj: bytes,
        filename: str,
        content_type: Optional[str] = None
    ) -> str:
        """
        上传文件对象（字节流）到 Cloudflare R2
        
        Args:
            file_obj: 文件字节流
            filename: 原始文件名
            content_type: 内容类型（可选）
        
        Returns:
            上传后的完整URL
        """
        # 生成远程路径
        today = time.strftime("%Y-%m-%d")
        ext = Path(filename).suffix
        
        # 生成 MD5 哈希
        hash_input = f"{time.time_ns()}{filename}"
        hash_bytes = hashlib.md5(hash_input.encode()).digest()
        hash_str = hash_bytes.hex()[:16]
        
        # 清理文件名
        name_without_ext = filename[:filename.rfind(ext)] if ext else filename
        clean_name = name_without_ext.replace(" ", "").replace("_", "").replace("-", "")
        
        # 构建新文件名
        new_file_name = f"{hash_str}{clean_name}{ext}"
        remote_path = f"uploads/{today}/{new_file_name}"
        
        # 获取内容类型
        if content_type is None:
            content_type = self._get_content_type(ext)
        
        # 上传文件
        try:
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=remote_path,
                Body=file_obj,
                ContentType=content_type
            )
        except ClientError as e:
            raise Exception(f"Failed to upload file: {e}")

        # 返回完整URL
        return f"https://{self.domain}/{remote_path}"

    def delete_file(self, url: str) -> bool:
        """
        删除文件
        
        Args:
            url: 文件的完整URL
        
        Returns:
            是否删除成功
        """
        # 从URL中提取key
        # 格式: https://domain/path -> path
        try:
            key = url.replace(f"https://{self.domain}/", "")
            self.s3_client.delete_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as e:
            print(f"Failed to delete file: {e}")
            return False

    @staticmethod
    def _get_content_type(suffix: str) -> str:
        """根据文件扩展名获取 Content-Type."""
        suffix_lower = suffix.lower().lstrip('.')
        content_types = {
            'webp': 'image/webp',
            'svg': 'image/svg+xml',
            'jpeg': 'image/jpeg',
            'jpg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'bmp': 'image/bmp',
            'pdf': 'application/pdf',
            'mp4': 'video/mp4',
            'html': 'text/html',
            'htm': 'text/html',
            'json': 'application/json',
            'txt': 'text/plain',
        }
        return content_types.get(suffix_lower, 'application/octet-stream')


# 全局客户端实例（延迟初始化）
_r2_client: Optional[CloudflareR2Client] = None


def get_r2_client() -> CloudflareR2Client:
    """获取 R2 客户端实例（单例模式）."""
    global _r2_client
    if _r2_client is None:
        _r2_client = CloudflareR2Client()
    return _r2_client

