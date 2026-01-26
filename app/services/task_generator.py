"""任务生成器：每日注册与任务分布。"""
import random
import string
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import hashlib
from sqlmodel import Session

from app.config import get_settings
from app.models import Task, TaskStatus, TaskType

settings = get_settings()

EMAIL_DOMAINS = ["gmail.com", "outlook.com", "yahoo.com", "proton.me", "icloud.com"]
FIRST_NAMES = ["alex", "sophia", "liam", "emma", "olivia", "noah", "ava", "ethan", "mia"]
LAST_NAMES = ["smith", "johnson", "williams", "brown", "jones", "garcia", "miller", "davis"]


def _random_username() -> str:
    """Generate realistic username."""
    return f"{random.choice(FIRST_NAMES)}.{random.choice(LAST_NAMES)}{random.randint(10, 99)}"


def _random_email() -> str:
    """Generate realistic email with mainstream domains."""
    name = _random_username().replace(".", "")
    domain = random.choice(EMAIL_DOMAINS)
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=3))
    return f"{name}{suffix}@{domain}"


def _random_password(length: int = 12) -> str:
    """Generate strong password: >=8, include upper/lower/digit/special."""
    upp = random.choice(string.ascii_uppercase)
    low = random.choice(string.ascii_lowercase)
    digit = random.choice(string.digits)
    special_chars = "!@#$%^&*?"
    special = random.choice(special_chars)
    pool = string.ascii_letters + string.digits + special_chars
    rest = "".join(random.choices(pool, k=max(length - 4, 4)))
    pwd = upp + low + digit + special + rest
    return "".join(random.sample(pwd, len(pwd)))


def _random_time_within_day() -> datetime:
    """Pick a random time within next 24h."""
    now = datetime.utcnow()
    delta_seconds = random.randint(0, 24 * 60 * 60 - 1)
    return now + timedelta(seconds=delta_seconds)


def create_daily_tasks(session: Session) -> List[Task]:
    """Create register/login/post tasks for a day."""
    tasks: List[Task] = []
    for _ in range(settings.daily_user_count):
        username = _random_username()
        email = _random_email()
        password = _random_password()
        password_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()

        register_payload = {
            "username": username,
            "email": email,
            "password": password,
            "password_hash": password_hash,
            "code": "666666",
            "register_type": "code",
        }
        login_payload = {"email": email, "password": password}
        post_payload = {"content": "Hello from auto bot"}

        # register
        tasks.append(
            Task(
                type=TaskType.register,
                payload=register_payload,
                scheduled_at=_random_time_within_day(),
                status=TaskStatus.pending,
            )
        )
        # login
        tasks.append(
            Task(
                type=TaskType.login,
                payload=login_payload,
                scheduled_at=_random_time_within_day(),
                status=TaskStatus.pending,
            )
        )
        # post
        tasks.append(
            Task(
                type=TaskType.post,
                payload=post_payload,
                scheduled_at=_random_time_within_day(),
                status=TaskStatus.pending,
            )
        )
        # beauty flow
        tasks.append(
            Task(
                type=TaskType.beauty_flow,
                payload={"email": email},
                scheduled_at=_random_time_within_day(),
                status=TaskStatus.pending,
            )
        )

    for task in tasks:
        session.add(task)
    session.commit()
    session.refresh(tasks[0])
    return tasks


def _end_of_today_utc_by_beijing() -> datetime:
    """按北京时间计算"今天结束"对应的 UTC 时间（naive UTC datetime）。"""
    now_utc = datetime.utcnow()
    now_bj = now_utc + timedelta(hours=8)
    start_bj = now_bj.replace(hour=0, minute=0, second=0, microsecond=0)
    end_bj = start_bj + timedelta(days=1) - timedelta(seconds=1)
    return end_bj - timedelta(hours=8)


def _get_date_range_utc_by_beijing(target_date: Optional[datetime] = None) -> tuple[datetime, datetime]:
    """
    按北京时间计算指定日期的开始和结束时间对应的 UTC 时间（naive UTC datetime）。
    
    Args:
        target_date: 目标日期（datetime 对象，如果为 None 则使用今天）
    
    Returns:
        (start_utc, end_utc): 指定日期的开始和结束时间（UTC）
    """
    if target_date is None:
        target_date = datetime.utcnow() + timedelta(hours=8)
    else:
        # 如果传入的是日期对象，确保有时间部分
        if isinstance(target_date, datetime):
            target_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(hours=8)
        else:
            # 如果是 date 对象，转换为 datetime
            from datetime import date as date_type
            if isinstance(target_date, date_type):
                target_date = datetime.combine(target_date, datetime.min.time()) + timedelta(hours=8)
    
    # 计算指定日期的开始和结束（北京时间）
    start_bj = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_bj = start_bj + timedelta(days=1) - timedelta(seconds=1)
    
    # 转换为 UTC
    start_utc = start_bj - timedelta(hours=8)
    end_utc = end_bj - timedelta(hours=8)
    
    return start_utc, end_utc


def _random_time_between(start: datetime, end: datetime) -> datetime:
    """在 [start, end] 内取随机时间（start/end 均为 naive UTC datetime）。"""
    if end <= start:
        return start
    delta = end - start
    seconds = int(delta.total_seconds())
    if seconds <= 0:
        return start
    return start + timedelta(seconds=random.randint(0, seconds))


def create_configured_tasks(
    session: Session,
    plan: Dict[str, int],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    start_time: str = "00:00",
    end_time: str = "23:59",
) -> List[Task]:
    """
    按配置生成指定日期范围和时间范围的任务（写入 tasks 表）。
    
    Args:
        session: 数据库会话
        plan: 任务配置字典，包含各模块的执行次数
        start_date: 开始日期（格式：YYYY-MM-DD 字符串，默认为今天）
        end_date: 结束日期（格式：YYYY-MM-DD 字符串，默认为开始日期）
        start_time: 开始时间（格式：HH:MM 字符串，默认 "00:00"）
        end_time: 结束时间（格式：HH:MM 字符串，默认 "23:59"）
    
    Returns:
        创建的任务列表
    """
    # 解析开始日期
    now_bj = datetime.utcnow() + timedelta(hours=8)
    today = now_bj.replace(hour=0, minute=0, second=0, microsecond=0)
    
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"无效的开始日期格式: {start_date}，请使用 YYYY-MM-DD 格式")
    else:
        start_date_obj = today
    
    # 解析结束日期
    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"无效的结束日期格式: {end_date}，请使用 YYYY-MM-DD 格式")
    else:
        end_date_obj = start_date_obj
    
    # 确保结束日期不早于开始日期
    if end_date_obj < start_date_obj:
        raise ValueError(f"结束日期 ({end_date}) 不能早于开始日期 ({start_date})")
    
    # 解析开始和结束时间
    try:
        start_hour, start_minute = map(int, start_time.split(":"))
        if not (0 <= start_hour <= 23 and 0 <= start_minute <= 59):
            raise ValueError("开始时间超出有效范围")
    except (ValueError, AttributeError):
        raise ValueError(f"无效的开始时间格式: {start_time}，请使用 HH:MM 格式（如 09:00）")
    
    try:
        end_hour, end_minute = map(int, end_time.split(":"))
        if not (0 <= end_hour <= 23 and 0 <= end_minute <= 59):
            raise ValueError("结束时间超出有效范围")
    except (ValueError, AttributeError):
        raise ValueError(f"无效的结束时间格式: {end_time}，请使用 HH:MM 格式（如 18:00）")
    
    # 计算时间范围的开始和结束（北京时间）
    # 开始：开始日期的开始时间
    start_datetime_bj = start_date_obj.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
    # 结束：结束日期的结束时间（包含当天，所以到结束日期的23:59:59）
    end_datetime_bj = end_date_obj.replace(hour=end_hour, minute=end_minute, second=59, microsecond=999999)
    
    # 转换为 UTC（数据库存储的是 naive UTC datetime）
    start_utc = start_datetime_bj - timedelta(hours=8)
    end_utc = end_datetime_bj - timedelta(hours=8)
    
    now_utc = datetime.utcnow()
    # 获取开始日期的午夜时间（北京时间），用于判断用户选择的日期是否是今天或未来
    start_date_midnight_bj = start_date_obj.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # 如果用户选择的开始日期是今天或未来（从北京时间角度），使用开始时间作为最早执行时间
    # 如果用户选择的开始日期是过去，使用当前时间（但不能早于开始时间）
    if start_date_midnight_bj >= today:
        # 用户选择的是今天或未来的日期，始终使用开始时间作为最早执行时间
        earliest_time = start_utc
    else:
        # 用户选择的是过去的日期，使用当前时间，但不能早于开始时间
        earliest_time = max(now_utc, start_utc)
    
    # 确保结束时间不会早于最早时间
    if end_utc <= earliest_time:
        end_utc = earliest_time + timedelta(hours=1)

    tasks: List[Task] = []

    # 按照顺序定义任务类型（1-9的顺序）
    module_order = [
        ("create_user", "create_user"),        # 1. 创建用户
        ("checkin", "checkin"),                # 2. 签到
        ("face_upload", "face_upload"),        # 3. 上传人脸
        ("makeup_creation", "makeup_creation"), # 4. 创建妆造
        ("post_community", "post_community"),   # 5. 发布到社区
        ("like_collect", "like_collect"),       # 6. 点赞收藏
        ("like_comment", "like_comment"),       # 7. 点赞评论
        ("follow_user", "follow_user"),         # 8. 关注用户
        ("collect_topic", "collect_topic"),     # 9. 收藏话题
    ]

    print(f"[TaskGenerator] ====== 开始生成任务 ======")
    print(f"[TaskGenerator] 时间范围: {earliest_time} 到 {end_utc}")
    print(f"[TaskGenerator] 任务配置: {plan}")

    # 先收集所有任务，按照顺序生成
    all_tasks: List[Task] = []
    
    for key, module in module_order:
        count = int(plan.get(key, 0) or 0)
        if count <= 0:
            continue

        print(f"[TaskGenerator] 生成 {count} 个 {module} 任务")
        for i in range(count):
            # 将模块名映射到 TaskType 枚举
            try:
                task_type = TaskType(module)
            except ValueError:
                # 如果模块名不在枚举中，使用 makeup 作为后备（向后兼容）
                task_type = TaskType.makeup
                payload = {"module": module, "seq": i + 1}
            else:
                # 模块名在枚举中，直接使用，payload 只保留序号
                payload = {"seq": i + 1}
            
            all_tasks.append(
                Task(
                    type=task_type,
                    payload=payload,
                    scheduled_at=None,  # 先不设置时间，后面统一设置
                    status=TaskStatus.pending,
                )
            )
    
    # 按照比例分配的方式分配时间：确保不同类型的任务按照比例均匀分布
    time_range = (end_utc - earliest_time).total_seconds()
    
    if len(all_tasks) == 0:
        tasks = []
    else:
        # 按照任务类型分组
        tasks_by_type: Dict[TaskType, List[Task]] = {}
        for task in all_tasks:
            if task.type not in tasks_by_type:
                tasks_by_type[task.type] = []
            tasks_by_type[task.type].append(task)
        
        # 统计每种类型的任务数量
        type_counts: Dict[TaskType, int] = {}
        available_types: List[TaskType] = []
        for key, module in module_order:
            count = int(plan.get(key, 0) or 0)
            if count <= 0:
                continue
            try:
                task_type = TaskType(module)
                type_counts[task_type] = count
                available_types.append(task_type)
            except ValueError:
                continue
        
        module_count = len(available_types)
        
        print(f"[TaskGenerator] 共有 {module_count} 种任务类型需要生成")
        print(f"[TaskGenerator] 总共 {len(all_tasks)} 个任务需要分配时间")
        print(f"[TaskGenerator] 任务类型及数量: {[(t.value, type_counts[t]) for t in available_types]}")
        
        if module_count > 0:
            # 计算最大公约数，用于简化比例
            def gcd(a: int, b: int) -> int:
                """计算最大公约数。"""
                while b:
                    a, b = b, a % b
                return a
            
            # 计算所有任务数量的最大公约数
            counts = [type_counts[t] for t in available_types]
            common_gcd = counts[0]
            for count in counts[1:]:
                common_gcd = gcd(common_gcd, count)
            
            # 计算简化后的比例
            type_ratios: Dict[TaskType, int] = {}
            for task_type in available_types:
                type_ratios[task_type] = type_counts[task_type] // common_gcd
            
            print(f"[TaskGenerator] 任务比例（简化后）: {[(t.value, type_ratios[t]) for t in available_types]}")
            
            # 为每种类型的任务创建索引指针
            type_indices: Dict[TaskType, int] = {}
            for task_type in available_types:
                type_indices[task_type] = 0
            
            # 按照比例创建任务序列
            # 例如：create_user:30, makeup_creation:20 -> 比例 3:2
            # 那么每轮应该是：create_user, create_user, create_user, makeup_creation, makeup_creation
            task_sequence: List[TaskType] = []
            max_ratio = max(type_ratios.values())
            
            # 创建多轮任务序列，确保按照比例分配
            for round_idx in range(max_ratio):
                for task_type in available_types:
                    ratio = type_ratios[task_type]
                    # 如果当前轮次小于该类型的比例，则添加该类型
                    if round_idx < ratio:
                        task_sequence.append(task_type)
            
            # 打乱任务序列，但保持比例
            # 将任务序列分成多个批次，每个批次内打乱
            batch_size = sum(type_ratios.values())
            shuffled_sequence: List[TaskType] = []
            
            # 计算需要多少轮才能分配完所有任务
            total_rounds = max((type_counts[t] + type_ratios[t] - 1) // type_ratios[t] for t in available_types)
            
            for round_num in range(total_rounds):
                round_tasks: List[TaskType] = []
                for task_type in available_types:
                    ratio = type_ratios[task_type]
                    remaining = type_counts[task_type] - type_indices[task_type]
                    # 在当前轮次中，按照比例添加该类型的任务
                    for _ in range(min(ratio, remaining)):
                        if type_indices[task_type] < type_counts[task_type]:
                            round_tasks.append(task_type)
                
                # 打乱当前轮次的任务顺序
                random.shuffle(round_tasks)
                shuffled_sequence.extend(round_tasks)
            
            print(f"[TaskGenerator] 生成的任务序列长度: {len(shuffled_sequence)}")
            print(f"[TaskGenerator] 前20个任务类型: {[t.value for t in shuffled_sequence[:20]]}")
            
            # 按照序列分配时间
            task_index = 0
            task_interval = time_range / len(all_tasks) if len(all_tasks) > 0 else 0
            
            for task_type in shuffled_sequence:
                if task_index >= len(all_tasks):
                    break
                
                # 获取该类型的下一个任务
                type_idx = type_indices[task_type]
                type_tasks = tasks_by_type.get(task_type, [])
                
                if type_idx >= len(type_tasks):
                    # 这个类型的任务已经分配完了，跳过
                    continue
                
                task = type_tasks[type_idx]
                type_indices[task_type] = type_idx + 1
                
                # 计算这个任务的时间
                offset_seconds = task_interval * task_index
                task.scheduled_at = earliest_time + timedelta(seconds=offset_seconds)
                
                task_index += 1
                
                # 每分配100个任务打印一次进度
                if task_index % 100 == 0 or task_index == len(all_tasks):
                    print(f"[TaskGenerator] 已分配 {task_index}/{len(all_tasks)} 个任务")
        
        print(f"[TaskGenerator] 总共生成了 {len(all_tasks)} 个任务")
        
        tasks = all_tasks

    for t in tasks:
        session.add(t)
    session.commit()
    if tasks:
        session.refresh(tasks[0])
    return tasks


