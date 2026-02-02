"""认证服务：管理员登录和token验证."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel import Session, select, create_engine

from app.db import get_session, engine
from app.models import AdminSession

# 硬编码的管理员账号密码
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD_HASH = hashlib.sha256("]+iDZ?1B^53b~".encode("utf-8")).hexdigest()  # 管理员登录密码

security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """
    对密码进行哈希处理。
    @param password - 原始密码
    @returns 哈希后的密码
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    """
    验证密码是否正确。
    @param password - 输入的密码
    @param password_hash - 存储的密码哈希
    @returns 密码是否正确
    """
    return hash_password(password) == password_hash


def generate_token() -> str:
    """
    生成随机token。
    @returns 32字节的URL安全随机字符串
    """
    return secrets.token_urlsafe(32)


def create_session(session: Session, expires_hours: int = 24) -> str:
    """
    创建新的session并存储到数据库。
    @param session - 数据库会话
    @param expires_hours - token过期时间（小时），默认24小时
    @returns 生成的token
    """
    token = generate_token()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=expires_hours)
    
    admin_session = AdminSession(
        token=token,
        created_at=now,
        expires_at=expires_at,
    )
    session.add(admin_session)
    session.commit()
    session.refresh(admin_session)
    
    return token


def verify_token(session: Session, token: str) -> bool:
    """
    验证token是否有效。
    @param session - 数据库会话
    @param token - 要验证的token
    @returns token是否有效
    """
    if not token:
        print("[DEBUG] verify_token - No token provided")
        return False
    
    try:
        print(f"[DEBUG] verify_token - Looking for token: {token[:30]}...")
        admin_session = session.exec(
            select(AdminSession).where(AdminSession.token == token)
        ).first()
        
        if not admin_session:
            # 列出数据库中所有的token（用于调试）
            all_sessions = session.exec(select(AdminSession)).all()
            print(f"[DEBUG] verify_token - Session not found. Total sessions in DB: {len(all_sessions)}")
            if all_sessions:
                print(f"[DEBUG] verify_token - First session token: {all_sessions[0].token[:30]}...")
            print(f"[DEBUG] verify_token - Looking for: {token}")
            return False
        
        # 检查是否过期
        now = datetime.now(timezone.utc)
        if admin_session.expires_at:
            # 确保 expires_at 是 timezone-aware（如果从数据库读取的是 naive，则添加 UTC 时区）
            expires_at = admin_session.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            
            if expires_at < now:
                # 删除过期的session
                print(f"[DEBUG] verify_token - Token expired. Expires: {expires_at}, Now: {now}")
                session.delete(admin_session)
                session.commit()
                return False
        
        print(f"[DEBUG] verify_token - Token valid! ID: {admin_session.id}, Expires: {admin_session.expires_at}")
        return True
    except Exception as e:
        import traceback
        print(f"[DEBUG] verify_token - Error: {e}\n{traceback.format_exc()}")
        return False


def get_current_admin(
    request: Request,
    authorization: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_token: Optional[str] = Header(None),
) -> AdminSession:
    """
    FastAPI依赖函数，用于验证token。
    支持三种方式获取token：
    1. Authorization: Bearer <token>
    2. X-Token: <token>
    3. Cookie: admin_token (用于页面访问)
    
    @param session - 数据库会话
    @param authorization - HTTP Bearer认证
    @param x_token - X-Token header
    @param request - FastAPI请求对象（用于获取cookie）
    @returns AdminSession对象
    @raises HTTPException - 如果token无效
    """
    token = None
    
    # 优先从Authorization header获取
    if authorization and authorization.credentials:
        token = authorization.credentials
    # 其次从X-Token header获取
    elif x_token:
        token = x_token
    # 最后从Cookie获取（用于页面访问）
    else:
        token = request.cookies.get("admin_token")
    
    if not token:
        raise HTTPException(status_code=401, detail="未提供认证token")
    
    # 直接创建session，不使用依赖注入
    session = Session(engine)
    try:
        if not verify_token(session, token):
            raise HTTPException(status_code=401, detail="无效或过期的token")
        
        admin_session = session.exec(
            select(AdminSession).where(AdminSession.token == token)
        ).first()
        
        if not admin_session:
            raise HTTPException(status_code=401, detail="Session不存在")
        
        return admin_session
    finally:
        session.close()

