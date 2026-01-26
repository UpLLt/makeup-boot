"""Token 管理：随机获取用户token，过期则重新登录."""
import random
from typing import Optional, Tuple
from sqlmodel import Session, select

from app.clients.makeup_api import MakeupApiClient
from app.models import User

client = MakeupApiClient()


def get_valid_token(session: Session) -> Tuple[Optional[str], Optional[int], list[str]]:
    """
    从数据库随机获取一个有效token。
    
    Returns:
        (token, user_id, warnings): token字符串、用户ID、警告列表
    """
    warnings: list[str] = []
    
    # 获取所有有token的用户
    all_users = session.exec(
        select(User)
        .where(User.token != None)
        .where(User.token != "")
    ).all()
    
    if not all_users:
        warnings.append("No users with token found in database")
        return None, None, warnings
    
    print(f"[Token] Found {len(all_users)} users with token")
    
    # 随机选择一个用户
    user = random.choice(all_users)
    print(f"[Token] Randomly selected user: user_id={user.id}")
    
    token = user.token
    
    if not token:
        warnings.append(f"User {user.id} has empty token")
        return None, user.id, warnings
    
    return token, user.id, warnings


def refresh_token(session: Session, user_id: int) -> Tuple[Optional[str], list[str]]:
    """
    刷新token：**不再调用 /auth/refresh 接口**，统一通过重新登录获取新 token。
    
    Returns:
        (token, warnings): 新token、警告列表
    """
    warnings: list[str] = []
    
    user = session.get(User, user_id)
    if not user:
        warnings.append(f"User {user_id} not found")
        return None, warnings
    
    # 直接通过登录刷新 token（不会再调用不存在的 refresh 接口）
    return _refresh_token_by_login(session, user, user_id, warnings)


def _refresh_token_by_login(session: Session, user: User, user_id: int, warnings: list[str]) -> Tuple[Optional[str], list[str]]:
    """
    通过重新登录获取新token（刷新接口失败时的fallback）。
    
    @param session - 数据库会话
    @param user - 用户对象
    @param user_id - 用户ID
    @param warnings - 警告列表
    @returns (token, warnings): 新token、警告列表
    """
    if not user.email or not user.password_plain:
        warnings.append(f"User {user_id} missing email or password")
        return None, warnings
    
    # 重新登录
    try:
        print(f"[Token] 通过重新登录获取用户 {user_id} 的新token...")
        login_resp = client.login({
            "email": user.email,
            "password": user.password_plain,
            "login_type": "email_password"
        })
        
        # 提取token
        token = None
        if isinstance(login_resp, dict):
            token = login_resp.get("token") or login_resp.get("access_token") or login_resp.get("data", {}).get("token")
            if not token and isinstance(login_resp.get("data"), dict):
                token = login_resp.get("data", {}).get("access_token")
        
        if token:
            # 更新数据库
            user.token = token
            session.add(user)
            session.commit()
            print(f"[Token] ✓ 通过重新登录成功刷新用户 {user_id} 的token")
            return token, warnings
        else:
            warnings.append(f"Login response missing token: {login_resp}")
            return None, warnings
    except Exception as exc:
        warnings.append(f"Login failed: {exc}")
        return None, warnings


def ensure_valid_token(session: Session, token: Optional[str], user_id: Optional[int]) -> Tuple[Optional[str], Optional[int], list[str]]:
    """
    确保token有效，如果无效则刷新。
    
    Returns:
        (token, user_id, warnings): 有效token、用户ID、警告列表
    """
    warnings: list[str] = []
    
    if not token or not user_id:
        # 如果没有token，先获取一个
        token, user_id, get_warnings = get_valid_token(session)
        warnings.extend(get_warnings)
        if not token:
            return None, None, warnings
    
    # 这里可以添加token有效性检查，如果后续API调用返回401/403，则调用refresh_token
    # 为了简化，我们假设token可能有效，如果后续调用失败再刷新
    
    return token, user_id, warnings

