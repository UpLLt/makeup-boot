"""任务执行器。"""
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import random
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

from sqlmodel import Session, select

from app.clients.makeup_api import MakeupApiClient
from app.config import get_settings
from app.services.ai_text import generate_text
from app.services.user_signup_flow import _generate_natural_username
from app.models import Post, Task, TaskLog, TaskStatus, TaskType, User, UserActivityLog


client = MakeupApiClient()
settings = get_settings()
_IMAGE_URLS: List[str] = []


def _fetch_all_topics(token: str) -> List[dict]:
    """
    分页获取所有话题。
    先获取第一页（size=100），如果total超过100，则分页获取所有数据。
    注意：API不支持 size > 100，所以所有请求都使用 size=100。
    
    @param token - 用户token
    @returns 所有话题的列表
    """
    all_items = []
    page_size = 100  # API最大支持100，固定使用100
    
    try:
        # 先获取第一页，使用 size=100（API最大支持）
        first_page = client.topics(token, params={"page": 1, "size": page_size})
        
        if isinstance(first_page, dict):
            data = first_page.get("data") or first_page
            total_count = data.get("total", 0) if isinstance(data, dict) else 0
            first_page_items = data.get("list") or data.get("items") if isinstance(data, dict) else []
            
            if isinstance(first_page_items, list):
                all_items.extend(first_page_items)
            
            # 如果总数超过100，需要分页获取（每页都使用 size=100）
            if total_count > page_size:
                total_pages = (total_count + page_size - 1) // page_size  # 向上取整
                
                # 从第2页开始获取（第1页已经获取了）
                for page in range(2, total_pages + 1):
                    try:
                        page_data = client.topics(token, params={"page": page, "size": page_size})
                        if isinstance(page_data, dict):
                            page_data_obj = page_data.get("data") or page_data
                            page_items = page_data_obj.get("list") or page_data_obj.get("items") if isinstance(page_data_obj, dict) else []
                            if isinstance(page_items, list):
                                all_items.extend(page_items)
                    except Exception:
                        pass  # 忽略单页错误，继续获取其他页
    except Exception:
        pass  # 忽略错误，返回已获取的数据
    
    return all_items


def _load_image_urls() -> List[str]:
    """加载头像/人脸 URL 列表（兼容旧代码，从文件读取）。"""
    global _IMAGE_URLS  # noqa: PLW0603
    if _IMAGE_URLS:
        return _IMAGE_URLS
    path = Path(__file__).resolve().parent.parent / "image.txt"
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
        _IMAGE_URLS = [ln.strip() for ln in lines if ln.strip()]
    return _IMAGE_URLS


def _pick_image_url(session=None) -> str:
    """随机选择头像/人脸 URL。优先使用接口返回，不再读取本地数据库头像。"""
    try:
        avatars = client.get_avatars(type_=0, page=1, size=100)
        if isinstance(avatars, dict):
            data = avatars.get("data") or avatars
            items = data.get("list") or data.get("items") or data.get("data") if isinstance(data, dict) else None
            if isinstance(items, list) and items:
                # 打乱列表后再随机选择，确保每次选择不同
                items_copy = items.copy()
                random.shuffle(items_copy)
                random_item = items_copy[0]
                url = random_item.get("url") or random_item.get("avatar") or random_item.get("img")
                if url:
                    return url
    except Exception as e:  # noqa: BLE001
        print(f"[Warning] Failed to get image from /auth/users/avatars: {e}, falling back to file/default")

    # 回退到文件或默认
    urls = _load_image_urls()
    if urls:
        return random.choice(urls)
    return settings.default_face_image_url


def _generate_face_name() -> str:
    """生成正式的人脸名称（英文），模拟真实用户可能起的名字."""
    face_name_templates = [
        "My Face",
        "Profile Photo",
        "Main Avatar",
        "Default Face",
        "Selfie",
        "Profile Picture",
        "My Photo",
        "Avatar",
        "Face Model",
        "My Look",
        "Personal Photo",
        "Profile Image",
        "Main Photo",
        "Default Avatar",
        "My Picture",
        "Face Photo",
        "Profile Selfie",
        "Main Face",
        "Personal Avatar",
        "My Avatar",
        "Profile Face",
        "Selfie Photo",
        "Face 1",
        "Photo 1",
        "Avatar 1",
        "My Profile",
        "Main Selfie",
        "Default Photo",
        "Personal Photo 1",
        "Face Model 1",
    ]
    return random.choice(face_name_templates)


def _format_error_message(result: dict) -> str:
    """格式化错误消息，避免消息过长超过数据库字段限制。"""
    error_msg_parts = []
    
    # 提取警告信息
    if result.get("warnings"):
        warnings = result.get("warnings", [])
        if isinstance(warnings, list) and warnings:
            # 只取前3个警告，避免消息过长
            warning_strs = [str(w)[:80] for w in warnings[:3]]  # 每个警告最多80字符
            error_msg_parts.append("Warnings: " + "; ".join(warning_strs))
    
    # 提取API响应中的关键信息
    if result.get("result"):
        result_data = result.get("result")
        if isinstance(result_data, dict):
            code = result_data.get("code")
            msg = result_data.get("message", "")
            if code:
                error_msg_parts.append(f"Code: {code}")
            if msg:
                # 截断 message，最多100字符
                msg_str = str(msg)[:100]
                error_msg_parts.append(f"Msg: {msg_str}")
    
    # 如果没有任何错误信息，使用默认消息
    if not error_msg_parts:
        error_msg_parts.append("Task execution failed")
    
    # 组合错误消息，确保总长度不超过200字符
    error_msg = " | ".join(error_msg_parts)
    if len(error_msg) > 200:
        error_msg = error_msg[:197] + "..."
    
    return error_msg


def _log(session: Session, task: Task, status: TaskStatus, message: Optional[str] = None) -> None:
    """记录任务日志与更新时间。"""
    log = TaskLog(task_id=task.id, status=status, message=message, started_at=datetime.utcnow(), ended_at=datetime.utcnow())
    session.add(log)
    task.status = status
    task.updated_at = datetime.utcnow()
    if status == TaskStatus.failed:
        # 截断错误信息，避免超过数据库字段长度限制（MySQL VARCHAR 默认255，这里限制为200字符以确保安全）
        if message:
            max_length = 200  # 使用更小的值以确保不会超过数据库字段限制
            truncated_suffix = "... (truncated)"
            if len(message) > max_length:
                # 确保截断后的总长度不超过 max_length
                available_length = max_length - len(truncated_suffix)
                if available_length > 0:
                    task.last_error = message[:available_length] + truncated_suffix
                else:
                    task.last_error = message[:max_length]
            else:
                task.last_error = message
        else:
            task.last_error = None
    session.add(task)
    session.commit()


def _find_user_by_email(session: Session, email: str) -> Optional[User]:
    """查找用户."""
    return session.exec(select(User).where(User.email == email)).first()


def _attach_user_to_task(session: Session, task: Task, user_id: Optional[int]) -> None:
    """将任务关联的用户ID写回 tasks 表，便于后续追踪。"""
    if not user_id:
        return
    if task.user_id == user_id:
        return
    task.user_id = user_id
    session.add(task)
    session.commit()


class TaskTimeoutError(Exception):
    """任务执行超时异常。"""
    pass


def _execute_task_internal(session: Session, task: Task) -> None:
    """
    内部任务执行函数，在单独线程中运行。
    
    Args:
        session: 数据库会话
        task: 要执行的任务
    """
    if task.type == TaskType.register:
        _handle_register(session, task)
    elif task.type == TaskType.login:
        _handle_login(session, task)
    elif task.type == TaskType.post:
        _handle_post(session, task)
    elif task.type == TaskType.makeup:
        # 向后兼容：处理旧的 payload.module 格式
        _handle_admin_module_task(session, task)
    elif task.type in (
        TaskType.create_user,
        TaskType.checkin,
        TaskType.face_upload,
        TaskType.makeup_creation,
        TaskType.post_community,
        TaskType.like_collect,
        TaskType.like_comment,
        TaskType.follow_user,
        TaskType.collect_topic,
    ):
        # 直接使用 type 字段作为模块名
        _handle_module_task_by_type(session, task)
    elif task.type == TaskType.beauty_flow:
        _handle_beauty_flow(session, task)
    else:
        raise ValueError(f"Unsupported task type: {task.type}")


def run_task(session: Session, task: Task) -> None:
    """执行单个任务，带20秒超时限制。"""
    print(f"[TaskRunner] ====== run_task START ======")
    print(f"[TaskRunner] Task ID: {task.id}, Type: {task.type}, Status: {task.status}, Attempts: {task.attempts}, Scheduled: {task.scheduled_at}")
    task.status = TaskStatus.running
    task.attempts += 1
    task.updated_at = datetime.utcnow()
    session.add(task)
    session.commit()
    print(f"[TaskRunner] Task status updated to RUNNING, attempts={task.attempts}")

    try:
        # 使用线程池和超时机制执行任务（最多20秒）
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_execute_task_internal, session, task)
            try:
                future.result(timeout=20)  # 20秒超时
                print(f"[TaskRunner] Task {task.id} completed successfully, marking as SUCCESS")
                _log(session, task, TaskStatus.success, "ok")
                print(f"[TaskRunner] Task {task.id} status updated to SUCCESS in database")
                print(f"[TaskRunner] ====== run_task END (SUCCESS) ======")
            except FutureTimeoutError:
                print(f"[TaskRunner] Task {task.id} TIMEOUT after 20 seconds")
                error_msg = "Task execution timeout after 20 seconds"
                _log(session, task, TaskStatus.failed, error_msg)
                print(f"[TaskRunner] ====== run_task END (TIMEOUT) ======")
                # 注意：线程可能仍在运行，但我们已经标记任务为失败
    except Exception as exc:  # noqa: BLE001
        print(f"[TaskRunner] Task {task.id} FAILED with exception: {exc}")
        print(f"[TaskRunner] Exception type: {type(exc).__name__}")
        import traceback
        print(f"[TaskRunner] Exception traceback:\n{traceback.format_exc()}")
        _log(session, task, TaskStatus.failed, str(exc))
        print(f"[TaskRunner] ====== run_task END (FAILED) ======")


def _handle_module_task_by_type(session: Session, task: Task) -> None:
    """执行模块任务（由 task.type 指定）。"""
    print(f"[TaskRunner] ====== _handle_module_task_by_type START ======")
    print(f"[TaskRunner] Task ID: {task.id}, Type: {task.type}, Status: {task.status}, Attempts: {task.attempts}")
    # 延迟导入，避免循环依赖
    from app.services.user_signup_flow import create_single_user
    from app.services import module_handlers as mh

    module_map = {
        TaskType.create_user: create_single_user,
        TaskType.checkin: mh.handle_checkin,
        TaskType.face_upload: mh.handle_face_upload,
        TaskType.makeup_creation: mh.handle_makeup_creation,
        TaskType.post_community: mh.handle_post_to_community,
        TaskType.like_collect: mh.handle_like_collect,
        TaskType.like_comment: mh.handle_like_comment,
        TaskType.follow_user: mh.handle_follow_user,
        TaskType.collect_topic: mh.handle_collect_topic,
    }
    fn = module_map.get(task.type)
    if fn is None:
        raise ValueError(f"Unknown task type: {task.type}")

    print(f"[TaskRunner] Calling handler function for task type: {task.type}")
    result = fn(session)
    print(f"[TaskRunner] Handler function returned: success={result.get('success') if isinstance(result, dict) else 'N/A'}")
    print(f"[TaskRunner] Result details: {result}")
    
    if isinstance(result, dict):
        _attach_user_to_task(session, task, result.get("user_id"))
    
    # 检查任务是否成功
    if isinstance(result, dict) and result.get("success") is False:
        # 任务执行失败，抛出错误让任务标记为 failed
        # 使用格式化函数避免错误消息过长
        error_msg = _format_error_message(result)
        print(f"[TaskRunner] Task failed (success=False), raising error: {error_msg}")
        print(f"[TaskRunner] Full result: {result}")
        raise ValueError(error_msg)
    elif isinstance(result, dict) and result.get("success") is True:
        print(f"[TaskRunner] Task succeeded (success=True), will mark as success")
    else:
        print(f"[TaskRunner] WARNING: Result is not a dict or missing success field: {result}")
    
    print(f"[TaskRunner] ====== _handle_module_task_by_type END (SUCCESS) ======")


def _handle_admin_module_task(session: Session, task: Task) -> None:
    """执行后台模块任务（向后兼容：由 payload.module 指定）。"""
    payload = task.payload or {}
    module = payload.get("module")
    if not module:
        raise ValueError("Missing payload.module for makeup task")

    # 延迟导入，避免循环依赖
    from app.services.user_signup_flow import create_single_user
    from app.services import module_handlers as mh

    module_map = {
        "create_user": create_single_user,
        "checkin": mh.handle_checkin,
        "face_upload": mh.handle_face_upload,
        "makeup_creation": mh.handle_makeup_creation,
        "post_community": mh.handle_post_to_community,
        "like_collect": mh.handle_like_collect,
        "like_comment": mh.handle_like_comment,
        "follow_user": mh.handle_follow_user,
        "collect_topic": mh.handle_collect_topic,
    }
    fn = module_map.get(module)
    if fn is None:
        raise ValueError(f"Unknown module: {module}")

    result = fn(session)
    if isinstance(result, dict):
        _attach_user_to_task(session, task, result.get("user_id"))
    if isinstance(result, dict) and result.get("success") is False:
        # 任务执行失败，抛出错误让任务标记为 failed
        # 使用格式化函数避免错误消息过长
        error_msg = _format_error_message(result)
        raise ValueError(error_msg)


def _handle_register(session: Session, task: Task) -> None:
    """处理注册。"""
    payload = task.payload or {}
    email = payload.get("email")
    password = payload.get("password")
    # 1. 直接注册（不再发送验证码）
    register_body = {
        "email": email,
        "password": password,
        "code": payload.get("code", "666666"),
        "register_type": payload.get("register_type", "code"),
        "bot_key": payload.get("bot_key", "QoF8a1hyBwx4JTnqmrKxb4vTHykwROap"),
    }
    resp = client.register(register_body)
    token = resp.get("token")
    user = _find_user_by_email(session, email) if email else None
    if user is None:
        user = User(
            username=payload.get("username", email),
            email=email,
            password_hash=payload.get("password_hash", ""),
            password_plain=password,
            token=token,
            created_at=datetime.utcnow(),
        )
    else:
        user.token = token
        user.password_plain = password
    session.add(user)
    session.commit()
    session.add(
        UserActivityLog(
            user_id=user.id,
            action="register",
            api_endpoint="/register",
            scheduled_at=task.scheduled_at,
            executed_at=datetime.utcnow(),
            status="success",
            message=str(resp),
        )
    )
    session.commit()
    task.user_id = user.id
    session.add(task)
    session.commit()

    # 3. 生成自然用户名 & 头像（随机选择）
    name = None
    try:
        # 使用自然用户名生成函数，避免AI生成的味道
        name = _generate_natural_username()
    except Exception:  # noqa: BLE001
        pass
    
    avatar_url = None
    try:
        avatars = client.get_avatars(type_=0, page=1, size=100)
        print(f"[Register] get_avatars response: {avatars}")
        if isinstance(avatars, dict):
            data = avatars.get("data") or avatars
            print(f"[Register] avatars data: {data}")
            items = data.get("list") or data.get("items") or data.get("data") if isinstance(data, dict) else None
            print(f"[Register] avatars items count: {len(items) if isinstance(items, list) else 0}")
            if isinstance(items, list) and items:
                # 显示所有头像的URL，用于调试
                all_urls = [item.get("url") or item.get("avatar") or item.get("img") for item in items]
                print(f"[Register] All avatar URLs: {all_urls[:5]}... (showing first 5)")
                # 打乱列表后再随机选择，确保每次选择不同
                items_copy = items.copy()
                random.shuffle(items_copy)
                random_item = items_copy[0]
                print(f"[Register] selected avatar item (from {len(items)} items): {random_item}")
                avatar_url = random_item.get("url") or random_item.get("avatar") or random_item.get("img")
                print(f"[Register] extracted avatar_url: {avatar_url}")
            else:
                print(f"[Register] No items found in avatars response")
        else:
            print(f"[Register] avatars response is not a dict: {type(avatars)}")
    except Exception as e:  # noqa: BLE001
        print(f"[Register] Exception getting avatars: {e}")
        import traceback
        traceback.print_exc()

    if token:
        signature = generate_text(
            "Generate a short makeup-style personal signature in English, natural tone, within 20 words."
        )
        if isinstance(signature, str):
            signature = signature.strip().strip('"').strip("'")
        # 性别：90%概率为女(2)，10%概率为男(1)
        sex = 2 if random.random() < 0.9 else 1
        print(f"[Register] Randomly assigned sex: {sex} ({'女' if sex == 2 else '男'})")
        # 只使用从接口获取的头像，不使用 payload 中的本地头像
        update_info_body = {
            "username": name or payload.get("username", email),
            "avatar": avatar_url,  # 只使用接口获取的头像，如果为空则不设置
            "signature": signature,
            "sex": sex,
        }
        # 如果 avatar_url 为空，从 body 中移除 avatar 字段
        if not avatar_url:
            update_info_body.pop("avatar", None)
        client.update_user_info(token, update_info_body)
        session.add(
            UserActivityLog(
                user_id=user.id,
                action="update_info",
                api_endpoint="/api/users/info",
                scheduled_at=task.scheduled_at,
                executed_at=datetime.utcnow(),
                status="success",
                message=str(update_info_body),
            )
        )
        session.commit()

        # 4. 修改密码流程：发送验证码 -> 验证 -> 修改
        try:
            client.send_change_password_code(token, method="email")
            verify_resp = client.change_password_verify(
                token,
                {"verify_method": "code", "method": "email", "code": "666666"},
            )
            change_token = None
            if isinstance(verify_resp, dict):
                change_token = verify_resp.get("change_password_token") or verify_resp.get("token")
            new_password = payload.get("new_password", f"{password}#1")
            if change_token:
                client.change_password(
                    token,
                    {
                        "change_password_token": change_token,
                        "new_password": new_password,
                        "confirm_password": new_password,
                    },
                )
                user.password_plain = new_password
                session.add(user)
                session.commit()
                session.add(
                    UserActivityLog(
                        user_id=user.id,
                        action="change_password",
                        api_endpoint="/api/users/password",
                        scheduled_at=task.scheduled_at,
                        executed_at=datetime.utcnow(),
                        status="success",
                        message="password updated",
                    )
                )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            session.add(
                UserActivityLog(
                    user_id=user.id,
                    action="change_password",
                    api_endpoint="/api/users/password",
                    scheduled_at=task.scheduled_at,
                    executed_at=datetime.utcnow(),
                    status="failed",
                    message=str(exc),
                )
            )
            session.commit()

        # 5. 偏好设置（每个用户随机生成不同的偏好）
        try:
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
            resp = client.update_preferences(token, pref_body)
            print(f"[Register] update_preferences request payload: {pref_body}")
            print(f"[Register] update_preferences response: {resp}")
            session.add(
                UserActivityLog(
                    user_id=user.id,
                    action="update_preferences",
                    api_endpoint="/api/users/preferences",
                    scheduled_at=task.scheduled_at,
                    executed_at=datetime.utcnow(),
                    status="success",
                    message=str(pref_body),
                )
            )
            session.commit()
        except Exception as exc:  # noqa: BLE001
            print(f"[Register] update_preferences failed with payload: {pref_body}")
            print(f"[Register] update_preferences error: {exc}")
            import traceback
            traceback.print_exc()
            session.add(
                UserActivityLog(
                    user_id=user.id,
                    action="update_preferences",
                    api_endpoint="/api/users/preferences",
                    scheduled_at=task.scheduled_at,
                    executed_at=datetime.utcnow(),
                    status="failed",
                    message=str(exc),
                )
            )
            session.commit()


def _handle_login(session: Session, task: Task) -> None:
    """处理登录。"""
    payload = task.payload or {}
    email = payload.get("email")
    user = _find_user_by_email(session, email)
    login_body = payload
    if user and user.password_plain and not payload.get("password"):
        login_body = {"email": email, "password": user.password_plain}
    resp = client.login(login_body)
    token = resp.get("token")
    if not user:
        raise ValueError("User not found for login")
    user.token = token or user.token
    user.last_login_at = datetime.utcnow()
    session.add(user)
    session.commit()
    _attach_user_to_task(session, task, user.id)
    session.add(
        UserActivityLog(
            user_id=user.id,
            action="login",
            api_endpoint="/login",
            scheduled_at=task.scheduled_at,
            executed_at=datetime.utcnow(),
            status="success",
            message=str(resp),
        )
    )
    session.commit()


def _handle_post(session: Session, task: Task) -> None:
    """处理发布动态。"""
    payload = task.payload or {}
    # get user by id or email from payload
    user: Optional[User] = None
    if task.user_id:
        user = session.get(User, task.user_id)
    if user is None and "email" in payload:
        user = _find_user_by_email(session, payload["email"])
    if user is None:
        raise ValueError("User not found for post")
    if not user.token:
        raise ValueError("User missing token for post")
    _attach_user_to_task(session, task, user.id)
    resp = client.post_content(user.token, payload)
    post = Post(
        user_id=user.id,
        content=payload.get("content", ""),
        media_ref=payload.get("media_ref"),
        status="sent",
        sent_at=datetime.utcnow(),
        api_resp=resp,
    )
    session.add(post)
    session.add(
        UserActivityLog(
            user_id=user.id,
            action="post",
            api_endpoint="/posts",
            scheduled_at=task.scheduled_at,
            executed_at=datetime.utcnow(),
            status="success",
            message=str(resp),
        )
    )
    session.commit()


def _handle_beauty_flow(session: Session, task: Task) -> None:
    """执行签到/人脸/妆造/社区/互动/关注等组合流程."""
    payload = task.payload or {}
    user = None
    if task.user_id:
        user = session.get(User, task.user_id)
    if user is None and "email" in payload:
        user = _find_user_by_email(session, payload["email"])
    if user is None:
        raise ValueError("User not found for beauty flow")
    if not user.token:
        raise ValueError("User missing token for beauty flow")
    _attach_user_to_task(session, task, user.id)
    token = user.token

    # 1) 签到
    try:
        client.checkin_today(token, {"description": f"auto checkin {user.email}", "timezone": "Asia/Shanghai"})
        session.add(
            UserActivityLog(
                user_id=user.id,
                action="checkin",
                api_endpoint="/api/beauty/checkin",
                scheduled_at=task.scheduled_at,
                executed_at=datetime.utcnow(),
                status="success",
                message="checkin done",
            )
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.add(
            UserActivityLog(
                user_id=user.id,
                action="checkin",
                api_endpoint="/api/beauty/checkin",
                scheduled_at=task.scheduled_at,
                executed_at=datetime.utcnow(),
                status="failed",
                message=str(exc),
            )
        )
        session.commit()
        return

    # 2) 人脸列表或保存
    face_id = None
    try:
        faces = client.face_list(token)
        items = faces.get("data") or faces.get("list") or faces.get("items") if isinstance(faces, dict) else None
        if isinstance(items, list) and items:
            first = items[0]
            face_id = first.get("id") or first.get("face_model_id")
        if face_id is None:
            save_resp = client.face_save(
                token,
                {
                    "face_name": _generate_face_name(),
                    "image_url": _pick_image_url(session),
                    "set_as_default": True,
                },
            )
            if isinstance(save_resp, dict):
                data = save_resp.get("data") or save_resp
                face_id = data.get("face_model_id") or data.get("id")
    except Exception as exc:  # noqa: BLE001
        session.add(
            UserActivityLog(
                user_id=user.id,
                action="face_save",
                api_endpoint="/api/beauty/face/save",
                scheduled_at=task.scheduled_at,
                executed_at=datetime.utcnow(),
                status="failed",
                message=str(exc),
            )
        )
        session.commit()
        return

    # 3) 创建会话
    session_code = None
    try:
        sess_resp = client.editor_session(token, {"face_model_id": face_id})
        data = sess_resp.get("data") if isinstance(sess_resp, dict) else None
        session_code = data.get("session_code") if isinstance(data, dict) else None
    except Exception as exc:  # noqa: BLE001
        session.add(
            UserActivityLog(
                user_id=user.id,
                action="editor_session",
                api_endpoint="/api/beauty/editor/session",
                scheduled_at=task.scheduled_at,
                executed_at=datetime.utcnow(),
                status="failed",
                message=str(exc),
            )
        )
        session.commit()
        return

    # 4) 单步编辑（最小参数）
    try:
        if session_code:
            # 应用单步修改（至少需要一个妆容参数，这里使用简单的底妆参数）
            step_payload = {
                "session_code": session_code,
                "foundation": {
                    "target_color": [255, 220, 190],  # 暖色调肤色 RGB
                    "color_intensity": 0.5,  # 中等强度
                    "smoothing_intensity": 50  # 中等磨皮
                }
            }
            client.editor_step(token, step_payload)
        session.add(
            UserActivityLog(
                user_id=user.id,
                action="editor_step",
                api_endpoint="/api/beauty/editor/step",
                scheduled_at=task.scheduled_at,
                executed_at=datetime.utcnow(),
                status="success",
                message="step applied",
            )
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.add(
            UserActivityLog(
                user_id=user.id,
                action="editor_step",
                api_endpoint="/api/beauty/editor/step",
                scheduled_at=task.scheduled_at,
                executed_at=datetime.utcnow(),
                status="failed",
                message=str(exc),
            )
        )
        session.commit()

    # 5) 保存为妆造
    makeup_id = None
    try:
        if session_code:
            save_resp = client.editor_save(
                token,
                {"name": f"auto_makeup_{user.id}", "session_code": session_code, "status": 1, "is_private": 0},
            )
            data = save_resp.get("data") if isinstance(save_resp, dict) else None
            makeup_id = data.get("makeup_id") if isinstance(data, dict) else None
            session.add(
                UserActivityLog(
                    user_id=user.id,
                    action="editor_save",
                    api_endpoint="/api/beauty/editor/save",
                    scheduled_at=task.scheduled_at,
                    executed_at=datetime.utcnow(),
                    status="success",
                    message=str(save_resp),
                )
            )
            session.commit()
    except Exception as exc:  # noqa: BLE001
        session.add(
            UserActivityLog(
                user_id=user.id,
                action="editor_save",
                api_endpoint="/api/beauty/editor/save",
                scheduled_at=task.scheduled_at,
                executed_at=datetime.utcnow(),
                status="failed",
                message=str(exc),
            )
        )
        session.commit()

    # 6) 获取我的妆造列表以备后续使用
    try:
        my_list = client.my_makeups(token, params={"page": 1, "size": 10})
        if isinstance(my_list, dict):
            data = my_list.get("data") or my_list
            items = data.get("list") or data.get("items") if isinstance(data, dict) else None
            if isinstance(items, list) and items and makeup_id is None:
                first = items[0]
                makeup_id = first.get("makeup_id") or first.get("id")
    except Exception:
        pass

    # 7) 准备标签/话题
    tags = []
    topics = []
    try:
        tag_resp = client.makeup_tags(token)
        data = tag_resp.get("data") if isinstance(tag_resp, dict) else None
        tags = data.get("list") if isinstance(data, dict) else []
    except Exception:
        tags = []
    try:
        topics = _fetch_all_topics(token)
    except Exception:
        topics = []

    # 8) 生成文案 & 发动态
    post_id = None
    try:
        gen_body = {
            "makeup_id": makeup_id,
            "style": "short",
            "tone": "friendly",
            "length": 80,
        }
        gen_resp = client.generate_post_content(token, gen_body)
        content = ""
        if isinstance(gen_resp, dict):
            data = gen_resp.get("data") or gen_resp
            content = data.get("content") or data.get("text") or "Auto post"
        tag_ids = []
        if tags:
            tag = tags[0]
            tag_ids = [tag.get("tag_id") or tag.get("id")] if isinstance(tag, dict) else []
        topic_id = None
        if topics:
            topic = topics[0]
            topic_id = topic.get("topic_id") or topic.get("id")
        post_body = {
            "content": content or "Auto generated content",
            "makeup_id": makeup_id,
            "tags": tag_ids,
            "topic_id": topic_id,
        }
        post_resp = client.create_post(token, post_body)
        if isinstance(post_resp, dict):
            data = post_resp.get("data") or post_resp
            post_id = data.get("post_id") or data.get("id")
        session.add(
            UserActivityLog(
                user_id=user.id,
                action="community_post",
                api_endpoint="/api/beauty/community/post",
                scheduled_at=task.scheduled_at,
                executed_at=datetime.utcnow(),
                status="success",
                message=str(post_resp),
            )
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.add(
            UserActivityLog(
                user_id=user.id,
                action="community_post",
                api_endpoint="/api/beauty/community/post",
                scheduled_at=task.scheduled_at,
                executed_at=datetime.utcnow(),
                status="failed",
                message=str(exc),
            )
        )
        session.commit()

    # 9) 点赞/评论/收藏
    try:
        all_makeups = client.makeups_list(token, params={"page": 1, "size": 10})
        target_makeup = None
        if isinstance(all_makeups, dict):
            data = all_makeups.get("data") or all_makeups
            items = data.get("list") or data.get("items") if isinstance(data, dict) else None
            if isinstance(items, list) and items:
                target_makeup = items[0]
        target_post_id = post_id
        client.like_post(token, {"post_id": target_post_id or (target_makeup or {}).get("post_id")})
        comment_context = ""
        if target_makeup and isinstance(target_makeup, dict):
            comment_context = target_makeup.get("description") or target_makeup.get("name") or ""
        if post_body.get("content"):
            comment_context = post_body["content"]
        comment_text = generate_text(
            f"围绕主题内容写一句友善的中文评论，40字内，避免重复，主题：{comment_context or '妆造'}",
            max_tokens=80,
        )
        client.comment(token, {"post_id": target_post_id, "content": comment_text})
        comments = client.comments(token, params={"post_id": target_post_id, "page": 1, "size": 5})
        first_comment_id = None
        if isinstance(comments, dict):
            data = comments.get("data") or comments
            items = data.get("list") or data.get("items") if isinstance(data, dict) else None
            if isinstance(items, list) and items:
                first_comment_id = items[0].get("comment_id") or items[0].get("id")
        if first_comment_id:
            client.like_comment(token, {"comment_id": first_comment_id})
        if target_makeup:
            makeup_id_like = target_makeup.get("makeup_id") or target_makeup.get("id")
            record_id = target_makeup.get("record_id") or makeup_id_like
            if record_id:
                try:
                    collect_resp = client.collect_try_record(token, {"record_id": record_id})
                    # 检查是否已经收藏过
                    if isinstance(collect_resp, dict):
                        msg = str(collect_resp.get("message", "")).lower()
                        if any(keyword in msg for keyword in ["already", "exist", "已收藏", "已存在", "重复"]):
                            print(f"[BeautyFlow] Record {record_id} already collected, skipping")
                except Exception as e:
                    print(f"[BeautyFlow] Collect try record failed: {e}")
    except Exception:
        pass

    # 10) 关注用户 & 收藏话题
    try:
        if tags:
            tag = tags[0]
            topic_collect_id = topic_id or (topics[0].get("topic_id") if topics else None)
            if topic_collect_id:
                try:
                    collect_topic_resp = client.topic_collect(token, {"topic_id": topic_collect_id})
                    # 检查是否已经收藏过
                    if isinstance(collect_topic_resp, dict):
                        msg = str(collect_topic_resp.get("message", "")).lower()
                        if any(keyword in msg for keyword in ["already", "exist", "已收藏", "已存在", "重复"]):
                            print(f"[BeautyFlow] Topic {topic_collect_id} already collected, skipping")
                except Exception as e:
                    print(f"[BeautyFlow] Collect topic failed: {e}")
        # follow by makeup owner if available
        target_user_id = None
        if target_makeup and isinstance(target_makeup, dict):
            target_user_id = target_makeup.get("user_id")
        if target_user_id:
            try:
                follow_resp = client.follow_user(token, {"target_user_id": target_user_id})
                # 检查是否已经关注过
                if isinstance(follow_resp, dict):
                    msg = str(follow_resp.get("message", "")).lower()
                    if any(keyword in msg for keyword in ["already", "exist", "已关注"]):
                        print(f"[BeautyFlow] User {target_user_id} already followed, skipping")
            except Exception as e:
                print(f"[BeautyFlow] Follow user failed: {e}")
    except Exception:
        pass


