"""Token 管理：随机获取用户token，过期则重新登录."""
import random
from typing import Optional, Tuple
from sqlmodel import Session, select

from app.clients.makeup_api import MakeupApiClient
from app.models import User

client = MakeupApiClient()


def get_valid_token(session: Session, days: int = 7) -> Tuple[Optional[str], Optional[int], list[str]]:
    """
    从数据库获取一个有效token，优先选择最近几天创建的用户，如果过期则重新登录。
    
    Args:
        days: 优先选择最近N天创建的用户（默认7天）
    
    Returns:
        (token, user_id, warnings): token字符串、用户ID、警告列表
    """
    warnings: list[str] = []
    from datetime import datetime, timedelta
    
    # 计算最近N天的日期范围
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    from sqlalchemy import desc
    
    # 优先获取最近N天创建的用户（有token的）
    recent_users = session.exec(
        select(User)
        .where(User.token != None)
        .where(User.token != "")
        .where(User.created_at >= cutoff_date)
        .order_by(desc(User.created_at))
    ).all()
    
    # 如果最近N天没有用户，则获取所有有token的用户
    if not recent_users:
        all_users = session.exec(
            select(User)
            .where(User.token != None)
            .where(User.token != "")
            .order_by(desc(User.created_at))
        ).all()
        if not all_users:
            warnings.append("No users with token found in database")
            return None, None, warnings
        users = all_users
        print(f"[Token] No recent users (last {days} days), using all {len(users)} users")
    else:
        users = recent_users
        print(f"[Token] Found {len(users)} recent users (last {days} days)")
    
    # 从符合条件的用户中随机选择一个（优先选择最近创建的）
    # 70%概率选择前30%的用户（最近创建的），30%概率随机选择
    if len(users) > 3 and random.random() < 0.7:
        # 选择前30%的用户（最近创建的）
        top_count = max(1, int(len(users) * 0.3))
        user = random.choice(users[:top_count])
        print(f"[Token] Selected from top {top_count} recent users: user_id={user.id}")
    else:
        # 随机选择
        user = random.choice(users)
        print(f"[Token] Randomly selected user: user_id={user.id}")
    
    token = user.token
    
    if not token:
        warnings.append(f"User {user.id} has empty token")
        return None, user.id, warnings
    
    # 尝试使用token调用一个简单接口验证（这里先假设token有效，如果后续调用失败再刷新）
    # 实际验证可以在调用API时进行，如果返回401/403则重新登录
    
    return token, user.id, warnings


def refresh_token(session: Session, user_id: int) -> Tuple[Optional[str], list[str]]:
    """
    刷新token：优先使用通用token刷新接口，失败则重新登录。
    
    Returns:
        (token, warnings): 新token、警告列表
    """
    warnings: list[str] = []
    
    user = session.get(User, user_id)
    if not user:
        warnings.append(f"User {user_id} not found")
        return None, warnings
    
    if not user.token:
        warnings.append(f"User {user_id} has no token to refresh")
        # 如果没有token，直接尝试重新登录
        return _refresh_token_by_login(session, user, user_id, warnings)
    
    # 优先尝试使用通用token刷新接口
    try:
        print(f"[Token] 尝试使用通用token刷新接口刷新用户 {user_id} 的token...")
        refresh_resp = client.refresh_token(user.token)
        
        # 检查响应是否成功
        if isinstance(refresh_resp, dict):
            code = str(refresh_resp.get("code", ""))
            # 检查是否为成功响应
            if code in ("0", "200", "success") or refresh_resp.get("token") or refresh_resp.get("access_token"):
                # 提取新token
                token = None
                token = (
                    refresh_resp.get("token")
                    or refresh_resp.get("access_token")
                    or refresh_resp.get("data", {}).get("token")
                )
                if not token and isinstance(refresh_resp.get("data"), dict):
                    token = refresh_resp.get("data", {}).get("access_token")
                
                if token:
                    # 更新数据库
                    user.token = token
                    session.add(user)
                    session.commit()
                    print(f"[Token] ✓ 使用刷新接口成功刷新用户 {user_id} 的token")
                    return token, warnings
                else:
                    warnings.append(f"Refresh token response missing token: {refresh_resp}")
            else:
                # 刷新接口返回错误，记录警告但继续尝试登录
                message = refresh_resp.get("message", "Unknown error")
                warnings.append(f"Refresh token API failed (code={code}, message={message}), will try login")
                print(f"[Token] ⚠️ 刷新接口失败 (code={code}), 回退到重新登录...")
        else:
            warnings.append(f"Refresh token response format invalid: {refresh_resp}")
    except Exception as exc:
        warnings.append(f"Refresh token API call failed: {exc}, will try login")
        print(f"[Token] ⚠️ 刷新接口调用异常: {exc}, 回退到重新登录...")
    
    # 如果刷新接口失败，回退到重新登录
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

