"""Token 管理：随机获取用户token，过期则重新登录."""
import random
from typing import Iterable, Optional, Tuple
from sqlmodel import Session, select

from app.clients.makeup_api import MakeupApiClient
from app.models import User

client = MakeupApiClient()


def get_valid_token(
    session: Session,
    exclude_user_ids: Optional[Iterable[int]] = None,
) -> Tuple[Optional[str], Optional[int], list[str]]:
    """
    从数据库随机获取一个有效token。
    
    Args:
        session: 数据库会话
        exclude_user_ids: 要排除的用户ID（用于“换用户重试”，如 20211 User not found 时换人）
    
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
    
    exclude = set(exclude_user_ids) if exclude_user_ids is not None else set()
    if exclude:
        all_users = [u for u in all_users if u.id not in exclude]
    
    if not all_users:
        warnings.append(
            "No users with token found in database"
            if not exclude
            else "No more users to try (all tried users returned 20211 User not found or failed)"
        )
        return None, None, warnings
    
    print(f"[Token] Found {len(all_users)} users with token" + (f" (excluded {len(exclude)})" if exclude else ""))
    
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
        
        # 提取token（login_resp 可能为 None，或 data 为 null，避免对 None 调用 .get）
        token = None
        if login_resp is None:
            warnings.append("Login response is None")
        elif isinstance(login_resp, dict):
            token = (
                login_resp.get("token")
                or login_resp.get("access_token")
                or (login_resp.get("data") or {}).get("token")
            )
            if not token:
                data = login_resp.get("data")
                if isinstance(data, dict):
                    token = data.get("access_token")
        
        if token:
            # 更新数据库
            user.token = token
            session.add(user)
            session.commit()
            print(f"[Token] ✓ 通过重新登录成功刷新用户 {user_id} 的token")
            return token, warnings
        else:
            # 明确提示：可能是接口返回 10104/请先登录 或 data 为空，需检查账号或接口
            if login_resp is None:
                pass  # 已在上方添加 "Login response is None"
            elif isinstance(login_resp, dict):
                code = login_resp.get("code")
                msg = login_resp.get("message", "")
                if code == 10104 or "请先登录" in str(msg):
                    warnings.append(
                        f"Login API returned code={code}, message={msg!r}; check user email/password or API."
                    )
                else:
                    warnings.append(f"Login response missing token: {login_resp}")
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

