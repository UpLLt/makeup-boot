"""单次用户创建流程：验证码注册->AI名/头像->改个人信息->改密->偏好."""
import sys
import io
import random
import string
from pathlib import Path
from typing import Dict, Optional, List, Any
import hashlib
from sqlmodel import Session

# 修复中文乱码：确保 stdout 使用 UTF-8 编码
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from app.clients.makeup_api import MakeupApiClient
from app.config import get_settings
from app.models import User
from app.services.ai_text import generate_text

settings = get_settings()
client = MakeupApiClient()


def _random_username() -> str:
    first = ["alex", "sophia", "liam", "emma", "olivia", "noah", "ava", "ethan", "mia"]
    last = ["smith", "johnson", "williams", "brown", "jones", "garcia", "miller", "davis"]
    return f"{random.choice(first)}.{random.choice(last)}{random.randint(10, 99)}"


def _generate_natural_username() -> str:
    """
    生成更自然的英文用户名，模拟真实用户起名习惯。
    避免AI生成的那种过于完美或描述性的名字。
    """
    # 常见英文名（女性）
    female_names = [
        "Amy", "Lisa", "Emma", "Lily", "Lucy", "Anna", "Eva", "Mia", "Zoe", "Ivy",
        "Sarah", "Emily", "Olivia", "Sophia", "Grace", "Chloe", "Isabella", "Ava",
        "Jessica", "Jennifer", "Michelle", "Nicole", "Rachel", "Hannah", "Amanda"
    ]
    
    # 常见英文名（男性）
    male_names = [
        "Tom", "Jack", "Mike", "John", "Alex", "Sam", "Ben", "Dan", "Leo", "Max",
        "David", "Chris", "Ryan", "Matt", "Nick", "Jake", "Luke", "Mark", "Paul",
        "James", "Robert", "Michael", "William", "Daniel", "Matthew"
    ]
    
    # 常见姓氏
    last_names = [
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
        "Wilson", "Moore", "Taylor", "Anderson", "Thomas", "Jackson", "White", "Harris",
        "Martin", "Thompson", "Martinez", "Robinson", "Clark", "Lewis", "Lee", "Walker"
    ]
    
    # 常见昵称/缩写
    nicknames = [
        "alex", "sam", "mike", "jake", "chris", "nick", "dave", "bob", "tom", "dan",
        "amy", "emma", "lily", "sara", "anna", "mia", "zoe", "lucy", "eva", "ivy"
    ]
    
    # 生成数字后缀的函数
    def _get_number_suffix() -> str:
        """生成随机数字后缀，模拟真实用户习惯"""
        patterns = [
            "", "", "", "", "", "", "", "", "", "",  # 50%概率返回空字符串
            str(random.randint(10, 99)),  # 2位数字
            str(random.randint(100, 999)),  # 3位数字
            str(random.randint(1000, 9999)),  # 4位数字
            str(random.randint(1990, 2010)),  # 出生年份风格
            str(random.randint(2000, 2024)),  # 现代年份
            "88", "99", "123", "456", "789",  # 简单数字组合
            "2024", "2023", "2025",  # 当前年份
        ]
        return random.choice(patterns)
    
    # 常见字母后缀
    letter_suffixes = [
        "", "", "", "", "", "", "", "", "", "", "", "", "", "", "",  # 75%概率不加字母
        "x", "xx", "o", "oo", "y", "yy", "a", "aa",  # 单/双字母
    ]
    
    # 生成策略：随机选择一种风格
    style = random.choice([
        "first_last",  # 名+姓
        "first_number",  # 名+数字
        "nickname_number",  # 昵称+数字
        "first_letter_number",  # 名+字母+数字
        "first_last_number",  # 名+姓+数字
        "nickname_letter",  # 昵称+字母
    ])
    
    all_names = female_names + male_names
    first_name = random.choice(all_names)
    last_name = random.choice(last_names)
    nickname = random.choice(nicknames)
    
    if style == "first_last":
        # 名+姓（最常见）
        base = f"{first_name}{last_name}"
    elif style == "first_number":
        # 名+数字
        base = f"{first_name}{_get_number_suffix()}"
    elif style == "nickname_number":
        # 昵称+数字
        base = f"{nickname}{_get_number_suffix()}"
    elif style == "first_letter_number":
        # 名+字母+数字
        letter = random.choice(letter_suffixes)
        number = _get_number_suffix() if random.random() < 0.7 else ""
        base = f"{first_name}{letter}{number}"
    elif style == "first_last_number":
        # 名+姓+数字
        number = _get_number_suffix() if random.random() < 0.6 else ""
        base = f"{first_name}{last_name}{number}"
    else:  # nickname_letter
        # 昵称+字母
        letter = random.choice(letter_suffixes)
        base = f"{nickname}{letter}"
    
    # 确保用户名不为空
    if not base or base.strip() == "":
        base = f"{first_name}{random.randint(10, 99)}"
    
    return base


def _random_email() -> str:
    name = _random_username().replace(".", "")
    domain_pool = ["gmail.com", "outlook.com", "yahoo.com", "proton.me", "icloud.com"]
    return f"{name}{random.randint(100, 999)}@{random.choice(domain_pool)}"


def _random_password(length: int = 12) -> str:
    """生成符合策略的密码：>=8，含大写/小写/数字/特殊字符."""
    upp = random.choice(string.ascii_uppercase)
    low = random.choice(string.ascii_lowercase)
    digit = random.choice(string.digits)
    special_chars = "!@#$%^&*?"
    special = random.choice(special_chars)
    pool = string.ascii_letters + string.digits + special_chars
    rest = "".join(random.choices(pool, k=max(length - 4, 4)))
    pwd = upp + low + digit + special + rest
    return "".join(random.sample(pwd, len(pwd)))


def _pick_image_url(session) -> str:
    """从数据库随机选择一张图片URL."""
    from sqlmodel import select
    from sqlalchemy import func
    from app.models import UserImage
    
    try:
        # 获取图片总数
        total = session.exec(select(func.count(UserImage.id))).one()
        if total == 0:
            # 如果数据库没有图片，回退到使用 image.txt
            path = Path(__file__).resolve().parent.parent / "image.txt"
            if path.exists():
                try:
                    lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
                    if lines:
                        return random.choice(lines)
                except Exception as read_exc:
                    print(f"[Warning] Failed to read image.txt: {read_exc}, using default URL")
            return settings.default_face_image_url
        
        # 随机选择一张图片
        offset = random.randint(0, total - 1)
        image = session.exec(
            select(UserImage).offset(offset).limit(1)
        ).first()
        
        if image:
            return image.url
        else:
            return settings.default_face_image_url
    except Exception as e:
        import traceback
        print(f"[Warning] Failed to get image from database: {e}")
        print(f"[Warning] Traceback: {traceback.format_exc()}")
        # 出错时回退到使用 image.txt
        try:
            path = Path(__file__).resolve().parent.parent / "image.txt"
            if path.exists():
                lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
                if lines:
                    return random.choice(lines)
        except Exception as read_exc:
            print(f"[Warning] Failed to read image.txt: {read_exc}, using default URL")
        return settings.default_face_image_url


def _extract_token(resp: Any) -> Optional[str]:
    """从接口响应中提取 token / temp_token / access_token."""
    if not isinstance(resp, dict):
        return None
    candidates = ["token", "access_token", "temp_token"]
    for key in candidates:
        val = resp.get(key)
        if val:
            return str(val)
    data = resp.get("data")
    if isinstance(data, dict):
        for key in candidates:
            val = data.get(key)
            if val:
                return str(val)
    user = resp.get("user")
    if isinstance(user, dict):
        for key in candidates:
            val = user.get(key)
            if val:
                return str(val)
    return None


def _check_code(resp: Any, step: str, warnings: List[str], success_codes: set[str]) -> tuple[bool, Optional[str]]:
    """检查响应 code，非成功则记录并返回 False，同时打印到控制台。"""
    code_val: Optional[str] = None
    if isinstance(resp, dict) and "code" in resp:
        code_val = str(resp.get("code"))
        if code_val not in success_codes:
            error_msg = f"[ERROR] {step} failed: code={code_val}, message={resp.get('message', 'N/A')}, resp={resp}"
            print(error_msg)
            warnings.append(f"{step} code not success: {code_val}, resp={resp}")
            return False, code_val
    return True, code_val


def create_single_user(session: Session) -> Dict[str, str]:
    """调用所列接口创建一个用户并落库，返回主要凭证。任何步骤 code 非成功立即终止。"""
    warnings: List[str] = []
    register_code: Optional[str] = None
    login_code: Optional[str] = None
    success_codes = {"0", "200", "success"}
    email = _random_email()
    username = _random_username()
    # 使用更强的固定密码（包含大小写/数字/多个符号，长度>14）
    password = "Aa1!@#xyzABC123$"

    # 1) 直接注册（无需先发验证码）
    print(f"[Signup] ====== 开始创建用户 ======")
    print(f"[Signup] 生成的邮箱: {email}")
    print(f"[Signup] 生成的用户名: {username}")
    register_payload = {
        "email": email,
        "password": password,
        "code": "666666",
        "register_type": "code",
        "bot_key": "QoF8a1hyBwx4JTnqmrKxb4vTHykwROap",
    }
    register_resp: Any = {}
    login_resp: Any = {}
    try:
        print(f"[Signup] 调用注册接口...")
        register_resp = client.register(register_payload)
        print(f"[Signup] 注册接口响应: {register_resp}")
    except Exception as exc:  # noqa: BLE001
        error_msg = f"register failed: {exc}"
        warnings.append(error_msg)
        print(f"[Signup] ✗ 注册失败: {error_msg}")
        import traceback
        print(f"[Signup] 异常堆栈: {traceback.format_exc()}")
        register_resp = {}
    ok, register_code = _check_code(register_resp, "register", warnings, success_codes)
    if not ok:
        return {
            "user_id": "",
            "email": email,
            "password": password,
            "new_password": password,
            "token": "",
            "warnings": warnings,
            "register_resp": register_resp,
            "login_resp": login_resp,
            "register_code": register_code,
            "login_code": login_code,
        }
    token = _extract_token(register_resp)
    # 某些情况下注册可能不直接返回 token，尝试登录获取
    if not token:
        print(f"[Signup] 注册未返回token，尝试登录获取...")
        login_payload = {"email": email, "password": password, "login_type": "email_password"}
        try:
            print(f"[Signup] 调用登录接口...")
            login_resp = client.login(login_payload)
            print(f"[Signup] 登录接口响应: {login_resp}")
            ok, login_code = _check_code(login_resp, "login", warnings, success_codes)
            if not ok:
                return {
                    "user_id": "",
                    "email": email,
                    "password": password,
                    "new_password": password,
                    "token": "",
                    "warnings": warnings,
                    "register_resp": register_resp,
                    "login_resp": login_resp,
                    "register_code": register_code,
                    "login_code": login_code,
                }
            token = _extract_token(login_resp) or token
            if not token:
                warnings.append(f"login resp missing token: {login_resp}")
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"login failed: {exc}")

    # 落库
    user = User(
        username=username,
        email=email,
        password_hash=hashlib.sha256(password.encode("utf-8")).hexdigest(),
        password_plain=password,
        token=token,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    # 如果登录后才获取 token，回写数据库
    if token and user.token != token:
        user.token = token
        session.add(user)
        session.commit()

    # 3) 生成自然用户名、头像（随机选择）
    ai_name = None
    try:
        # 使用自然用户名生成函数，避免AI生成的味道
        ai_name = _generate_natural_username()
        print(f"[Signup] Generated natural username: {ai_name}")
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"username generation failed: {exc}")
        # 如果生成失败，使用备用方案
        ai_name = _random_username()
    avatar_url: Optional[str] = None
    try:
        avatars = client.get_avatars(type_=0, page=1, size=100)
        print(f"[Signup] get_avatars response: {avatars}")
        if isinstance(avatars, dict):
            data = avatars.get("data") or avatars
            print(f"[Signup] avatars data: {data}")
            items = data.get("list") or data.get("items") or data.get("data") if isinstance(data, dict) else None
            print(f"[Signup] avatars items count: {len(items) if isinstance(items, list) else 0}")
            if isinstance(items, list) and items:
                # 显示所有头像的URL，用于调试
                all_urls = [item.get("url") or item.get("avatar") or item.get("img") for item in items]
                print(f"[Signup] All avatar URLs: {all_urls[:5]}... (showing first 5)")
                # 打乱列表后再随机选择，确保每次选择不同
                items_copy = items.copy()
                random.shuffle(items_copy)
                random_item = items_copy[0]
                print(f"[Signup] selected avatar item (from {len(items)} items): {random_item}")
                avatar_url = random_item.get("url") or random_item.get("avatar") or random_item.get("img")
                print(f"[Signup] extracted avatar_url: {avatar_url}")
            else:
                print(f"[Signup] No items found in avatars response")
                warnings.append("No items found in /auth/users/avatars response")
        else:
            print(f"[Signup] avatars response is not a dict: {type(avatars)}")
            warnings.append(f"avatars response is not a dict: {type(avatars)}")
        if not avatar_url:
            warnings.append("Failed to get avatar from /auth/users/avatars interface")
    except Exception as exc:  # noqa: BLE001
        print(f"[Signup] Exception getting avatars: {exc}")
        import traceback
        traceback.print_exc()
        warnings.append(f"avatars failed: {exc}")
    # 不再使用本地数据库头像库作为回退

    # 4) 修改个人信息
    print(f"[Signup] Generating signature...")
    signature = generate_text(
        "Generate a friendly makeup-style personal signature in English, within 20 words.",
        max_tokens=80,
    )
    if isinstance(signature, str):
        signature = signature.strip().strip('"').strip("'")
    print(f"[Signup] Generated signature: {signature}")
    if token:
        # 性别：90%概率为女(2)，10%概率为男(1)
        sex = 2 if random.random() < 0.9 else 1
        print(f"[Signup] Randomly assigned sex: {sex} ({'女' if sex == 2 else '男'})")
        
        # 准备用户名，如果用户名冲突则添加后缀重试
        current_username = ai_name or username
        max_retries = 5
        update_success = False
        
        for retry_count in range(max_retries):
            update_payload = {"username": current_username, "avatar": avatar_url, "signature": signature, "sex": sex}
            # 详细打印每个字段的内容
            print(f"[Signup] Updating user info (attempt {retry_count + 1}/{max_retries})")
            print(f"[Signup]   - username: {current_username}")
            print(f"[Signup]   - avatar: {avatar_url}")
            print(f"[Signup]   - signature: {signature}")
            print(f"[Signup]   - sex: {sex}")
            print(f"[Signup] Full payload: {update_payload}")
            sys.stdout.flush()  # 确保输出立即刷新
            try:
                update_info_resp = client.update_user_info(token, update_payload)
                print(f"[Signup] update_user_info response: {update_info_resp}")
                
                # 先检查是否是用户名已存在的错误（20217），如果是则直接重试，不添加警告
                if isinstance(update_info_resp, dict):
                    resp_code = update_info_resp.get("code")
                    # 检查错误码是否为 20217（用户名已存在）
                    if resp_code == 20217 or resp_code == "20217" or str(resp_code) == "20217":
                        # 用户名已存在，添加随机后缀重试
                        if retry_count < max_retries - 1:
                            suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
                            current_username = f"{current_username}_{suffix}"
                            print(f"[Signup] Username already exists (code=20217), retrying with new username: {current_username}")
                            continue  # 重试
                        else:
                            # 最后一次重试也失败，添加警告
                            warnings.append(f"update_user_info failed after {max_retries} retries: code=20217, resp={update_info_resp}")
                            break
                    # 检查是否是敏感词错误（20413）
                    elif resp_code == 20413 or resp_code == "20413" or str(resp_code) == "20413":
                        # 敏感词错误，打印详细字段内容
                        detail_msg = f"⚠️ Sensitive words detected (code=20413)! Field details - username: '{current_username}' (len={len(current_username) if current_username else 0}), signature: '{signature}' (len={len(signature) if signature else 0}), avatar: '{avatar_url}' (len={len(avatar_url) if avatar_url else 0})"
                        print(f"[Signup] {detail_msg}")
                        sys.stdout.flush()
                        warnings.append(f"update_user_info failed: code=20413 (sensitive words). {detail_msg}, resp={update_info_resp}")
                        break  # 敏感词错误不重试
                
                # 检查其他错误
                ok, update_info_code = _check_code(update_info_resp, "update_user_info", warnings, success_codes)
                
                if not ok:
                    # 如果不是20217或20413错误，记录警告但不重试
                    warnings.append(f"update_user_info failed: code={update_info_code}, resp={update_info_resp}")
                    break  # 其他错误不重试
                else:
                    print(f"[Signup] update_user_info success")
                    update_success = True
                    break  # 成功，退出循环
            except Exception as exc:  # noqa: BLE001
                print(f"[Signup] update_user_info exception: {exc}")
                if retry_count < max_retries - 1:
                    # 如果不是最后一次重试，添加后缀继续
                    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
                    current_username = f"{current_username}_{suffix}"
                    print(f"[Signup] Exception occurred, retrying with new username: {current_username}")
                    continue
                else:
                    warnings.append(f"update_user_info failed: {exc}")
        
        if not update_success:
            warnings.append(f"update_user_info failed after {max_retries} attempts")
    else:
        print(f"[Signup] No token, skipping update_user_info")
        warnings.append("no token: skip update_user_info")

    # 5) 按要求不再调用修改密码流程，保持原始密码
    new_password = password

    # 8) 更新偏好设置（每个用户随机生成不同的偏好）
    if token:
        # 定义可选偏好选项（根据API定义）
        # skin_tone: yellow_fair, fair_cool, deep
        skin_tones = ["yellow_fair", "fair_cool", "deep"]
        # skin_type: combination, dry, oily
        skin_types = ["combination", "dry", "oily"]
        # style_preferences: korean_daily(韩式日常), hong_kong_chic(港式时尚), minimalist_fresh(简约清新), western_glam(欧美魅力), anime_style(动漫风格)
        style_options = ["korean_daily", "hong_kong_chic", "minimalist_fresh", "western_glam", "anime_style"]
        # tone_preferences: warm_tone(暖色调), cool_tone(冷色调), neutral_tone(中性色调)
        tone_options = ["warm_tone", "cool_tone", "neutral_tone"]
        # special_preferences: emphasized_eyelashes(强调睫毛), defined_eyebrows(定义眉毛), nude_lips(裸色唇妆)
        special_options = ["emphasized_eyelashes", "defined_eyebrows", "nude_lips"]
        
        # 随机选择偏好
        pref_body = {
            "skin_tone": random.choice(skin_tones),
            "skin_type": random.choice(skin_types),
            "style_preferences": random.sample(style_options, k=random.randint(1, min(3, len(style_options)))),  # 随机选择1-3个风格偏好
            "tone_preferences": random.sample(tone_options, k=random.randint(1, min(2, len(tone_options)))),  # 随机选择1-2个色调偏好
            "special_preferences": random.sample(special_options, k=random.randint(1, min(3, len(special_options)))),  # 随机选择1-3个特殊偏好
            "makeup_intensity": random.randint(0, 100),  # 妆容浓度 0-100
            "join_regional_rankings": random.choice([True, False]),
            "discover_by_region": random.choice([True, False]),
            "makeup_challenges": random.choice([True, False]),
            # 地区偏好权重：每个都是0-100完全随机
            "east_asia_weight": random.randint(0, 100),      # 东亚偏好权重 0-100随机
            "southeast_asia_weight": random.randint(0, 100),  # 东南亚偏好权重 0-100随机
            "europe_america_weight": random.randint(0, 100),  # 欧美偏好权重 0-100随机
            "latin_america_weight": random.randint(0, 100),   # 拉美偏好权重 0-100随机
            "middle_east_weight": random.randint(0, 100),    # 中东偏好权重 0-100随机
        }
        try:
            print(f"[Signup] update_preferences request payload: {pref_body}")
            update_pref_resp = client.update_preferences(token, pref_body)
            print(f"[Signup] update_preferences response: {update_pref_resp}")
            ok, update_pref_code = _check_code(update_pref_resp, "update_preferences", warnings, success_codes)
            if not ok:
                print(f"[Signup] update_preferences failed: code={update_pref_code}, resp={update_pref_resp}")
                warnings.append(f"update_preferences failed: code={update_pref_code}, resp={update_pref_resp}")
        except Exception as exc:  # noqa: BLE001
            print(f"[Signup] update_preferences exception with payload: {pref_body}")
            print(f"[Signup] update_preferences error: {exc}")
            import traceback
            traceback.print_exc()
            warnings.append(f"update_preferences failed: {exc}")
    else:
        warnings.append("no token: skip update_preferences")

    return {
        "success": True,
        "user_id": str(user.id),
        "email": email,
        "password": password,
        "new_password": new_password,
        "token": token or "",
        "signature": signature,
        "warnings": warnings,
        "register_resp": register_resp,
        "login_resp": login_resp,
        "register_code": register_code,
        "login_code": login_code,
    }

