"""Web 与 API 路由。"""
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Request, Form, UploadFile, File, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.db import get_session, engine
from app.models import Task, TaskStatus, TaskType, User, UserActivityLog, UserImage, PostedMakeup, TaskLog
import random
from app.clients.cf_r2 import get_r2_client
from app.services.task_generator import create_daily_tasks, create_configured_tasks
from app.services.user_signup_flow import create_single_user
from app.services.auth import (
    ADMIN_USERNAME,
    ADMIN_PASSWORD_HASH,
    verify_password,
    create_session,
    get_current_admin,
)
from app.models import AdminSession
from app.services.module_handlers import (
    handle_checkin,
    handle_face_upload,
    handle_makeup_creation,
    handle_post_to_community,
    handle_like_collect,
    handle_like_comment,
    handle_follow_user,
    handle_collect_topic,
)

router = APIRouter()


def handle_module_error(exc: Exception, module_name: str) -> JSONResponse:
    """统一处理模块执行异常，确保返回 JSON 格式响应。"""
    import traceback
    error_msg = str(exc)
    error_traceback = traceback.format_exc()
    print(f"[{module_name}] Error: {error_msg}")
    print(f"[{module_name}] Traceback: {error_traceback}")
    return JSONResponse(
        status_code=500,
        content={
            "data": {
                "success": False,
                "error": error_msg,
                "warnings": [f"{module_name}执行时发生异常: {error_msg}"],
                "traceback": error_traceback
            }
        }
    )
templates = Jinja2Templates(directory="app/web/templates")

# 北京时间时区 (UTC+8)
BEIJING_TZ = timezone(timedelta(hours=8))


def to_beijing_time(dt: Optional[datetime]) -> str:
    """将 UTC 时间转换为北京时间并格式化为字符串."""
    if dt is None:
        return ""
    # 如果时间没有时区信息，假设是 UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    # 转换为北京时间
    beijing_dt = dt.astimezone(BEIJING_TZ)
    # 格式化为: YYYY-MM-DD HH:MM:SS
    return beijing_dt.strftime("%Y-%m-%d %H:%M:%S")


def get_db():
    """Dependency to provide DB session."""
    # 直接创建 Session，不使用 contextmanager
    from app.db import engine
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()


@router.get("/login.html")
def login_page(request: Request):
    """登录页面."""
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/auth/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_db),
):
    """
    管理员登录接口。
    @param username - 用户名
    @param password - 密码
    @returns 包含token的JSON响应
    """
    try:
        # 验证用户名和密码
        if username != ADMIN_USERNAME:
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        
        if not verify_password(password, ADMIN_PASSWORD_HASH):
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        
        # 创建session
        token = create_session(session)
        
        # 设置cookie，24小时过期
        expires = datetime.now(timezone.utc) + timedelta(hours=24)
        
        # 返回JSON响应，同时设置cookie
        # 前端会读取token并跳转，cookie也会被设置
        response = JSONResponse({
            "success": True,
            "token": token,
            "message": "登录成功",
        })
        response.set_cookie(
            key="admin_token",
            value=token,
            expires=expires,
            httponly=True,
            samesite="lax",
            path="/",
        )
        print(f"[DEBUG] Login - Token created: {token[:20]}..., Cookie set with path=/, expires={expires}")
        
        return response
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_msg = f"登录失败: {str(e)}\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=error_msg)


@router.post("/auth/logout")
def logout(
    request: Request,
    session: Session = Depends(get_db),
):
    """
    退出登录接口。
    清除session和cookie。
    """
    try:
        # 从cookie获取token
        token = request.cookies.get("admin_token")
        
        if token:
            # 从数据库删除session
            admin_session = session.exec(
                select(AdminSession).where(AdminSession.token == token)
            ).first()
            
            if admin_session:
                session.delete(admin_session)
                session.commit()
                print(f"[DEBUG] Logout - Session deleted for token: {token[:20]}...")
        
        # 清除cookie
        response = JSONResponse({
            "success": True,
            "message": "已退出登录",
        })
        response.delete_cookie(
            key="admin_token",
            path="/",
            samesite="lax",
        )
        
        return response
    except Exception as e:
        import traceback
        error_msg = f"退出登录失败: {str(e)}\n{traceback.format_exc()}"
        print(f"[DEBUG] Logout error: {error_msg}")
        # 即使出错，也清除cookie
        response = JSONResponse({
            "success": True,
            "message": "已退出登录",
        })
        response.delete_cookie(
            key="admin_token",
            path="/",
            samesite="lax",
        )
        return response


@router.get("/")
def home(
    request: Request,
    session: Session = Depends(get_db),
    user_page: int = 1,
    task_page: int = 1,
    executed_page: int = 1,
    page_size: int = 20,
):
    """首页展示概要."""
    # 暂时移除登录验证逻辑，直接渲染页面，看看会报什么错
    print(f"[DEBUG] Home page - Request received")
    print(f"[DEBUG] Home page - Cookies: {list(request.cookies.keys())}")
    token = request.cookies.get("admin_token")
    print(f"[DEBUG] Home page - Token in cookie: {token[:30] + '...' if token else 'None'}")
    
    try:
        from sqlalchemy import func
        # 用户分页
        users_total_count = session.exec(select(func.count(User.id))).one()
        users_offset = (user_page - 1) * page_size
        users = session.exec(
            select(User)
            .order_by(User.created_at.desc())
            .offset(users_offset)
            .limit(page_size)
        ).all()
        users_total_pages = (users_total_count + page_size - 1) // page_size if users_total_count > 0 else 1
        
        # 计算今日的开始和结束时间（北京时间）
        beijing_now = datetime.now(BEIJING_TZ)
        today_start = beijing_now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        # 转换为 UTC 用于数据库查询
        today_start_utc = today_start.astimezone(timezone.utc)
        today_end_utc = today_end.astimezone(timezone.utc)
        
        # 只查询今日任务 - 分页
        tasks_total_count = session.exec(
            select(func.count(Task.id))
            .where(Task.scheduled_at >= today_start_utc)
            .where(Task.scheduled_at < today_end_utc)
        ).one()
        tasks_total_pages = (tasks_total_count + page_size - 1) // page_size if tasks_total_count > 0 else 1
        tasks_offset = (task_page - 1) * page_size
        tasks = session.exec(
            select(Task)
            .where(Task.scheduled_at >= today_start_utc)
            .where(Task.scheduled_at < today_end_utc)
            .order_by(Task.scheduled_at.desc())
            .offset(tasks_offset)
            .limit(page_size)
        ).all()
        
        # 获取所有图片URL
        images = session.exec(select(UserImage)).all()
        image_urls = [img.url for img in images] if images else []
        
        # 将对象转换为字典并添加北京时间字符串
        user_cache: dict[int, dict] = {}
        users_data = []
        for user in users:
            user_dict = user.dict() if hasattr(user, 'dict') else user.model_dump()
            user_dict['created_at_str'] = to_beijing_time(user.created_at)
            # 为每个用户随机分配一个图片URL（使用用户ID作为种子，确保同一用户总是显示同一张图片）
            if image_urls:
                random.seed(user.id)
                user_dict["avatar_url"] = random.choice(image_urls)
                random.seed()  # 重置随机种子
            else:
                user_dict["avatar_url"] = None
            users_data.append(user_dict)
            user_cache[user.id] = user_dict
        
        tasks_data = []
        for task in tasks:
            task_dict = task.dict() if hasattr(task, 'dict') else task.model_dump()
            task_dict['scheduled_at_str'] = to_beijing_time(task.scheduled_at)
            # 附加用户邮箱
            if task.user_id and task.user_id in user_cache:
                task_dict['user_email'] = user_cache[task.user_id].get('email', '')
            elif task.user_id:
                user_obj = session.get(User, task.user_id)
                task_dict['user_email'] = getattr(user_obj, 'email', '') if user_obj else ''
                if user_obj:
                    user_cache[task.user_id] = user_obj.dict() if hasattr(user_obj, 'dict') else user_obj.model_dump()
            else:
                task_dict['user_email'] = ''
            tasks_data.append(task_dict)
        
        # 查询今日执行的任务（UserActivityLog）- 分页
        executed_query = (
            select(UserActivityLog)
            .where(UserActivityLog.executed_at >= today_start_utc)
            .where(UserActivityLog.executed_at < today_end_utc)
            .order_by(UserActivityLog.executed_at.desc())
        )
        executed_total_count = session.exec(
            select(func.count(UserActivityLog.id))
            .where(UserActivityLog.executed_at >= today_start_utc)
            .where(UserActivityLog.executed_at < today_end_utc)
        ).one()
        executed_offset = (executed_page - 1) * page_size
        today_executed_logs = session.exec(
            executed_query.offset(executed_offset).limit(page_size)
        ).all()
        executed_total_pages = (
            (executed_total_count + page_size - 1) // page_size
            if executed_total_count > 0
            else 1
        )
        
        executed_logs_data = []
        for log in today_executed_logs:
            log_dict = log.dict() if hasattr(log, 'dict') else log.model_dump()
            log_dict['executed_at_str'] = to_beijing_time(log.executed_at)
            log_dict['scheduled_at_str'] = to_beijing_time(log.scheduled_at)
            # 附加用户邮箱
            if log.user_id and log.user_id in user_cache:
                log_dict['user_email'] = user_cache[log.user_id].get('email', '')
            elif log.user_id:
                user_obj = session.get(User, log.user_id)
                log_dict['user_email'] = getattr(user_obj, 'email', '') if user_obj else ''
                if user_obj:
                    user_cache[log.user_id] = user_obj.dict() if hasattr(user_obj, 'dict') else user_obj.model_dump()
            else:
                log_dict['user_email'] = ''
            executed_logs_data.append(log_dict)
        
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "users": users_data,
                "tasks": tasks_data,
                "executed_logs": executed_logs_data,
                "users_total_count": users_total_count,
                "tasks_total_count": tasks_total_count,
                "executed_total_count": executed_total_count,
                "executed_total_pages": executed_total_pages,
                "executed_page": executed_page,
                "user_total_pages": users_total_pages,
                "user_page": user_page,
                "task_total_pages": tasks_total_pages,
                "task_page": task_page,
                "page_size": page_size,
            },
        )
    except Exception as e:
        # 如果渲染页面时出错，返回错误信息
        import traceback
        error_msg = f"首页加载失败: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


@router.get("/api/users")
def api_users(
    session: Session = Depends(get_db),
    admin_session = Depends(get_current_admin),
    page: int = 1,
    page_size: int = 20,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """用户列表 JSON，可选日期范围筛选（默认返回全部，按北京时间）。"""
    
    def parse_beijing_datetime(value: Optional[str], is_end: bool = False) -> Optional[datetime]:
        """
        解析日期/时间字符串为北京时间:
        - 支持格式: YYYY-MM-DD、YYYY-MM-DDTHH:MM、YYYY-MM-DDTHH:MM:SS
        - 结束时间为上限，故若提供具体秒，向后偏移 1 秒以实现"含本秒"。
        - 如果 value 为空，返回 None
        """
        if not value:
            return None
        patterns = ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"]
        for fmt in patterns:
            try:
                dt = datetime.strptime(value, fmt)
                dt = dt.replace(tzinfo=BEIJING_TZ)
                if fmt == "%Y-%m-%d":
                    # 纯日期：开始取 00:00:00，结束取次日 00:00:00
                    if is_end:
                        return dt.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                    return dt.replace(hour=0, minute=0, second=0, microsecond=0)
                # 精确到分钟或秒：结束时间向后推一秒作为开区间上限
                if is_end:
                    return dt + timedelta(seconds=1)
                return dt
            except Exception:
                continue
        return None

    # 解析日期参数
    start_beijing = parse_beijing_datetime(start_date, is_end=False)
    end_beijing = parse_beijing_datetime(end_date, is_end=True)

    # 构建查询
    from sqlalchemy import func
    query = select(User)
    count_query = select(func.count(User.id))
    
    # 只有提供了日期参数时才添加日期筛选
    if start_beijing is not None:
        start_utc = start_beijing.astimezone(timezone.utc)
        query = query.where(User.created_at >= start_utc)
        count_query = count_query.where(User.created_at >= start_utc)
    
    if end_beijing is not None:
        end_utc = end_beijing.astimezone(timezone.utc)
        query = query.where(User.created_at < end_utc)
        count_query = count_query.where(User.created_at < end_utc)
    
    # 执行查询
    total = session.exec(count_query).one()
    offset = (page - 1) * page_size
    users = session.exec(
        query.order_by(User.created_at.desc()).offset(offset).limit(page_size)
    ).all()
    
    # 获取所有图片URL
    images = session.exec(select(UserImage)).all()
    image_urls = [img.url for img in images] if images else []
    
    data = []
    for u in users:
        d = u.dict() if hasattr(u, "dict") else u.model_dump()
        d["created_at_str"] = to_beijing_time(u.created_at)
        # 为每个用户随机分配一个图片URL
        if image_urls:
            # 使用用户ID作为种子，确保同一用户总是显示同一张图片
            random.seed(u.id)
            d["avatar_url"] = random.choice(image_urls)
            random.seed()  # 重置随机种子
        else:
            d["avatar_url"] = None
        data.append(d)
    return {"data": data, "total": total, "page": page, "page_size": page_size}


@router.get("/api/tasks")
def api_tasks(
    session: Session = Depends(get_db),
    admin_session = Depends(get_current_admin),
    page: int = 1,
    page_size: int = 20,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    task_type: Optional[str] = None,
):
    """任务列表 JSON，可选日期范围和任务类型筛选（默认返回全部，按北京时间）。"""
    
    def parse_beijing_datetime(value: Optional[str], is_end: bool = False) -> Optional[datetime]:
        """
        解析日期/时间字符串为北京时间:
        - 支持格式: YYYY-MM-DD、YYYY-MM-DDTHH:MM、YYYY-MM-DDTHH:MM:SS
        - 结束时间为上限，故若提供具体秒，向后偏移 1 秒以实现"含本秒"。
        - 如果 value 为空，返回 None
        """
        if not value:
            return None
        patterns = ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"]
        for fmt in patterns:
            try:
                dt = datetime.strptime(value, fmt)
                dt = dt.replace(tzinfo=BEIJING_TZ)
                if fmt == "%Y-%m-%d":
                    # 纯日期：开始取 00:00:00，结束取次日 00:00:00
                    if is_end:
                        return dt.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                    return dt.replace(hour=0, minute=0, second=0, microsecond=0)
                # 精确到分钟或秒：结束时间向后推一秒作为开区间上限
                if is_end:
                    return dt + timedelta(seconds=1)
                return dt
            except Exception:
                continue
        return None

    # 解析日期参数
    start_beijing = parse_beijing_datetime(start_date, is_end=False)
    end_beijing = parse_beijing_datetime(end_date, is_end=True)

    # 构建查询
    from sqlalchemy import func
    query = select(Task)
    count_query = select(func.count(Task.id))
    
    # 只有提供了日期参数时才添加日期筛选
    if start_beijing is not None:
        start_utc = start_beijing.astimezone(timezone.utc)
        query = query.where(Task.scheduled_at >= start_utc)
        count_query = count_query.where(Task.scheduled_at >= start_utc)
    
    if end_beijing is not None:
        end_utc = end_beijing.astimezone(timezone.utc)
        query = query.where(Task.scheduled_at < end_utc)
        count_query = count_query.where(Task.scheduled_at < end_utc)
    
    # 任务类型筛选
    if task_type:
        try:
            task_type_enum = TaskType(task_type)
            query = query.where(Task.type == task_type_enum)
            count_query = count_query.where(Task.type == task_type_enum)
        except ValueError:
            # 如果task_type无效，忽略该筛选条件
            pass
    
    # 执行查询
    total = session.exec(count_query).one()
    offset = (page - 1) * page_size
    tasks = session.exec(
        query.order_by(Task.scheduled_at.desc())
        .offset(offset)
        .limit(page_size)
    ).all()
    data = []
    user_cache: dict[int, str] = {}
    for t in tasks:
        d = t.dict() if hasattr(t, "dict") else t.model_dump()
        d["scheduled_at_str"] = to_beijing_time(t.scheduled_at)
        if t.user_id:
            if t.user_id in user_cache:
                d["user_email"] = user_cache[t.user_id]
            else:
                user_obj = session.get(User, t.user_id)
                user_cache[t.user_id] = getattr(user_obj, "email", "") if user_obj else ""
                d["user_email"] = user_cache[t.user_id]
        else:
            d["user_email"] = ""
        data.append(d)
    return {"data": data, "total": total, "page": page, "page_size": page_size}


@router.get("/api/executed")
def api_executed(
    session: Session = Depends(get_db),
    admin_session = Depends(get_current_admin),
    page: int = 1,
    page_size: int = 20,
):
    """今日执行日志 JSON，倒序分页。"""
    beijing_now = datetime.now(BEIJING_TZ)
    today_start = beijing_now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    today_start_utc = today_start.astimezone(timezone.utc)
    today_end_utc = today_end.astimezone(timezone.utc)
    from sqlalchemy import func
    total = session.exec(
        select(func.count(UserActivityLog.id))
        .where(UserActivityLog.executed_at >= today_start_utc)
        .where(UserActivityLog.executed_at < today_end_utc)
    ).one()
    offset = (page - 1) * page_size
    logs = session.exec(
        select(UserActivityLog)
        .where(UserActivityLog.executed_at >= today_start_utc)
        .where(UserActivityLog.executed_at < today_end_utc)
        .order_by(UserActivityLog.executed_at.desc())
        .offset(offset)
        .limit(page_size)
    ).all()
    data = []
    user_cache: dict[int, str] = {}
    for log in logs:
        d = log.dict() if hasattr(log, "dict") else log.model_dump()
        d["executed_at_str"] = to_beijing_time(log.executed_at)
        d["scheduled_at_str"] = to_beijing_time(log.scheduled_at)
        if log.user_id:
            if log.user_id in user_cache:
                d["user_email"] = user_cache[log.user_id]
            else:
                user_obj = session.get(User, log.user_id)
                user_cache[log.user_id] = getattr(user_obj, "email", "") if user_obj else ""
                d["user_email"] = user_cache[log.user_id]
        else:
            d["user_email"] = ""
        data.append(d)
    return {"data": data, "total": total, "page": page, "page_size": page_size}


@router.post("/generate-today")
def generate_today(session: Session = Depends(get_db), admin_session = Depends(get_current_admin)):
    """手动生成今日任务。"""
    tasks = create_daily_tasks(session)
    return JSONResponse({"created": len(tasks)})


@router.get("/admin/generate-tasks")
def generate_tasks_page(request: Request, admin_session = Depends(get_current_admin)):
    """生成任务配置页。"""
    default_plan = {
        "create_user": 5,
        "checkin": 10,
        "face_upload": 10,
        "makeup_creation": 10,
        "post_community": 10,
        "like_collect": 20,
        "like_comment": 20,
        "follow_user": 15,
        "collect_topic": 10,
    }
    # 默认显示今天的日期和时间范围（北京时间）
    beijing_now = datetime.now(BEIJING_TZ)
    today_str = beijing_now.strftime("%Y-%m-%d")
    start_time_str = "00:00"
    end_time_str = "23:59"
    return templates.TemplateResponse(
        "generate_tasks.html",
        {
            "request": request,
            "plan": default_plan,
            "result": None,
            "start_date": today_str,
            "end_date": today_str,
            "start_time": start_time_str,
            "end_time": end_time_str,
        },
    )


@router.post("/admin/generate-tasks")
def generate_tasks_submit(
    request: Request,
    session: Session = Depends(get_db),
    admin_session = Depends(get_current_admin),
    create_user: int = Form(0),
    checkin: int = Form(0),
    face_upload: int = Form(0),
    makeup_creation: int = Form(0),
    post_community: int = Form(0),
    like_collect: int = Form(0),
    like_comment: int = Form(0),
    follow_user: int = Form(0),
    collect_topic: int = Form(0),
    start_date: str = Form(...),
    end_date: str = Form(...),
    start_time: str = Form("00:00"),
    end_time: str = Form("23:59"),
):
    """
    接收配置并生成指定日期范围和时间范围的任务（落库）。
    
    Args:
        start_date: 开始日期字符串，格式：YYYY-MM-DD
        end_date: 结束日期字符串，格式：YYYY-MM-DD
        start_time: 开始时间字符串，格式：HH:MM
        end_time: 结束时间字符串，格式：HH:MM
    """
    plan = {
        "create_user": max(create_user, 0),
        "checkin": max(checkin, 0),
        "face_upload": max(face_upload, 0),
        "makeup_creation": max(makeup_creation, 0),
        "post_community": max(post_community, 0),
        "like_collect": max(like_collect, 0),
        "like_comment": max(like_comment, 0),
        "follow_user": max(follow_user, 0),
        "collect_topic": max(collect_topic, 0),
    }
    # 解析日期和时间字符串并传递给任务生成函数
    try:
        tasks = create_configured_tasks(
            session, plan, start_date=start_date, end_date=end_date, start_time=start_time, end_time=end_time
        )
        result = {"created": len(tasks), "plan": plan}
    except ValueError as e:
        # 日期或时间格式错误
        result = None
        error_message = f"格式错误: {str(e)}"
        return templates.TemplateResponse(
            "generate_tasks.html",
            {
                "request": request,
                "plan": plan,
                "result": result,
                "start_date": start_date,
                "end_date": end_date,
                "start_time": start_time,
                "end_time": end_time,
                "error": error_message,
            },
        )
    
    return templates.TemplateResponse(
        "generate_tasks.html",
        {
            "request": request,
            "plan": plan,
            "result": result,
            "start_date": start_date,
            "end_date": end_date,
            "start_time": start_time,
            "end_time": end_time,
        },
    )


@router.get("/activity/{user_id}")
def activity(user_id: int, request: Request, session: Session = Depends(get_db), admin_session = Depends(get_current_admin)):
    """查看单用户时间轴。"""
    logs = session.exec(
        select(UserActivityLog).where(UserActivityLog.user_id == user_id).order_by(UserActivityLog.executed_at.desc())
    ).all()
    user = session.get(User, user_id)
    
    # 将对象转换为字典并添加北京时间字符串
    logs_data = []
    for log in logs:
        log_dict = log.dict() if hasattr(log, 'dict') else log.model_dump()
        log_dict['scheduled_at_str'] = to_beijing_time(log.scheduled_at)
        log_dict['executed_at_str'] = to_beijing_time(log.executed_at)
        logs_data.append(log_dict)
    
    user_data = user.dict() if user and hasattr(user, 'dict') else (user.model_dump() if user else None)
    
    return templates.TemplateResponse(
        "activity.html",
        {"request": request, "logs": logs_data, "user": user_data},
    )


@router.get("/tasks/pending")
def pending_tasks(session: Session = Depends(get_db), admin_session = Depends(get_current_admin)):
    """返回待执行任务列表."""
    tasks = session.exec(select(Task).where(Task.status == TaskStatus.pending)).all()
    return JSONResponse({"tasks": jsonable_encoder(tasks)})


@router.post("/admin/create-user-once")
def create_user_once(session: Session = Depends(get_db), admin_session = Depends(get_current_admin)):
    """执行单次创建用户完整流程。"""
    try:
        result = create_single_user(session)
        return JSONResponse({"data": result})
    except Exception as exc:
        return handle_module_error(exc, "CreateUser")


@router.post("/admin/module/checkin")
def module_checkin(session: Session = Depends(get_db), admin_session = Depends(get_current_admin)):
    """1. 签到模块."""
    try:
        result = handle_checkin(session)
        return JSONResponse({"data": result})
    except Exception as exc:
        return handle_module_error(exc, "Checkin")


@router.post("/admin/module/face-upload")
def module_face_upload(session: Session = Depends(get_db), admin_session = Depends(get_current_admin)):
    """2. 用户上传脸模块."""
    try:
        result = handle_face_upload(session)
        return JSONResponse({"data": result})
    except Exception as exc:
        return handle_module_error(exc, "FaceUpload")


@router.post("/admin/module/makeup-creation")
def module_makeup_creation(session: Session = Depends(get_db), admin_session = Depends(get_current_admin)):
    """3. 模拟用户妆造模块."""
    try:
        result = handle_makeup_creation(session)
        return JSONResponse({"data": result})
    except Exception as exc:
        return handle_module_error(exc, "MakeupCreation")


@router.post("/admin/module/post-community")
def module_post_community(session: Session = Depends(get_db), admin_session = Depends(get_current_admin)):
    """4. 发布妆造到社区模块."""
    try:
        result = handle_post_to_community(session)
        return JSONResponse({"data": result})
    except Exception as exc:
        return handle_module_error(exc, "PostCommunity")


@router.post("/admin/module/like-collect")
def module_like_collect(session: Session = Depends(get_db), admin_session = Depends(get_current_admin)):
    """5. 对妆造进行点赞、收藏模块."""
    try:
        result = handle_like_collect(session)
        return JSONResponse({"data": result})
    except Exception as exc:
        return handle_module_error(exc, "LikeCollect")


@router.post("/admin/module/like-comment")
def module_like_comment(session: Session = Depends(get_db), admin_session = Depends(get_current_admin)):
    """6. 点赞评论模块."""
    try:
        result = handle_like_comment(session)
        return JSONResponse({"data": result})
    except Exception as exc:
        return handle_module_error(exc, "LikeComment")


@router.post("/admin/module/follow-user")
def module_follow_user(session: Session = Depends(get_db), admin_session = Depends(get_current_admin)):
    """7. 关注某个用户模块."""
    try:
        result = handle_follow_user(session)
        return JSONResponse({"data": result})
    except Exception as exc:
        return handle_module_error(exc, "FollowUser")


@router.post("/admin/module/collect-topic")
def module_collect_topic(session: Session = Depends(get_db), admin_session = Depends(get_current_admin)):
    """8. 话题收藏模块."""
    try:
        result = handle_collect_topic(session)
        return JSONResponse({"data": result})
    except Exception as exc:
        return handle_module_error(exc, "CollectTopic")


@router.get("/admin/task-progress")
def task_progress(session: Session = Depends(get_db), admin_session = Depends(get_current_admin)):
    """获取任务进度列表."""
    try:
        # 使用 NULLS LAST 确保 None 值排在最后，或者先过滤掉 None
        logs = session.exec(
            select(UserActivityLog)
            .where(UserActivityLog.executed_at.isnot(None))
            .order_by(UserActivityLog.executed_at.desc())
            .limit(100)
        ).all()
        
        logs_data = []
        for log in logs:
            try:
                log_dict = log.dict() if hasattr(log, 'dict') else log.model_dump()
                # 移除 datetime 对象，只保留字符串版本
                log_dict.pop('executed_at', None)
                log_dict.pop('scheduled_at', None)
                log_dict['executed_at_str'] = to_beijing_time(log.executed_at)
                log_dict['scheduled_at_str'] = to_beijing_time(log.scheduled_at)
                logs_data.append(log_dict)
            except Exception as exc:
                print(f"[Error] Failed to process log {log.id}: {exc}")
                # 即使单个日志处理失败，也继续处理其他日志
                continue
        
        return JSONResponse({"data": logs_data})
    except Exception as exc:
        print(f"[Error] Failed to load task progress: {exc}")
        import traceback
        traceback.print_exc()
        return JSONResponse({"data": [], "error": str(exc)}, status_code=500)


# ==================== 图片管理相关路由 ====================

@router.get("/admin/images")
def images_page(request: Request, session: Session = Depends(get_db), admin_session = Depends(get_current_admin)):
    """图片管理页面."""
    return templates.TemplateResponse(
        "images.html",
        {
            "request": request,
        },
    )


@router.post("/admin/images/upload")
async def upload_image(
    session: Session = Depends(get_db),
    admin_session = Depends(get_current_admin),
    file: UploadFile = File(...)
):
    """上传图片到 Cloudflare R2 并保存到数据库."""
    try:
        # 验证文件类型
        if not file.content_type or not file.content_type.startswith('image/'):
            return JSONResponse({
                "success": False,
                "error": f"不支持的文件类型: {file.content_type or '未知'}"
            }, status_code=400)
        
        # 读取文件内容
        file_content = await file.read()
        
        if len(file_content) == 0:
            return JSONResponse({
                "success": False,
                "error": "文件为空"
            }, status_code=400)
        
        # 上传到 Cloudflare R2
        try:
            r2_client = get_r2_client()
            url = r2_client.upload_file_obj(
                file_obj=file_content,
                filename=file.filename or "unknown",
                content_type=file.content_type
            )
        except ValueError as config_error:
            # 配置错误，提供友好的提示
            error_msg = str(config_error)
            if "configuration is incomplete" in error_msg:
                return JSONResponse({
                    "success": False,
                    "error": "Cloudflare R2 配置不完整，请在 .env 文件中配置以下项：\n"
                             "CF_R2_ENDPOINT、CF_R2_BUCKET、CF_R2_ACCESS_KEY_ID、CF_R2_SECRET_ACCESS_KEY\n"
                             "配置后请重启应用。"
                }, status_code=500)
            return JSONResponse({
                "success": False,
                "error": f"Cloudflare R2 配置错误: {error_msg}"
            }, status_code=500)
        except Exception as r2_error:
            import traceback
            error_detail = traceback.format_exc()
            print(f"[Error] R2 upload failed: {error_detail}")
            return JSONResponse({
                "success": False,
                "error": f"上传到 Cloudflare R2 失败: {str(r2_error)}"
            }, status_code=500)
        
        # 保存到数据库
        try:
            user_image = UserImage(
                url=url,
                original_filename=file.filename,
                file_size=len(file_content),
                content_type=file.content_type
            )
            session.add(user_image)
            session.commit()
            session.refresh(user_image)
        except Exception as db_error:
            session.rollback()
            return JSONResponse({
                "success": False,
                "error": f"保存到数据库失败: {str(db_error)}"
            }, status_code=500)
        
        return JSONResponse({
            "success": True,
            "data": {
                "id": user_image.id,
                "url": user_image.url,
                "original_filename": user_image.original_filename,
                "file_size": user_image.file_size,
                "content_type": user_image.content_type,
            }
        })
    except Exception as e:
        session.rollback()
        import traceback
        error_detail = traceback.format_exc()
        print(f"[Error] Upload image failed: {error_detail}")
        return JSONResponse({
            "success": False,
            "error": f"上传失败: {str(e)}"
        }, status_code=500)


@router.delete("/admin/images/{image_id}")
def delete_image(image_id: int, session: Session = Depends(get_db), admin_session = Depends(get_current_admin)):
    """删除图片（从数据库和 R2）."""
    try:
        image = session.get(UserImage, image_id)
        if not image:
            raise HTTPException(status_code=404, detail="Image not found")
        
        # 从 R2 删除文件
        r2_client = get_r2_client()
        r2_client.delete_file(image.url)
        
        # 从数据库删除
        session.delete(image)
        session.commit()
        
        return JSONResponse({
            "success": True,
            "message": "Image deleted successfully"
        })
    except Exception as e:
        session.rollback()
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@router.get("/api/images")
def api_images(session: Session = Depends(get_db), admin_session = Depends(get_current_admin), page: int = 1, page_size: int = 20):
    """获取图片列表 API."""
    from sqlalchemy import func
    total = session.exec(select(func.count(UserImage.id))).one()
    offset = (page - 1) * page_size
    images = session.exec(
        select(UserImage).order_by(UserImage.created_at.desc()).offset(offset).limit(page_size)
    ).all()
    
    data = []
    for img in images:
        d = img.dict() if hasattr(img, "dict") else img.model_dump()
        d["created_at_str"] = to_beijing_time(img.created_at)
        d["updated_at_str"] = to_beijing_time(img.updated_at)
        data.append(d)
    
    return {"data": data, "total": total, "page": page, "page_size": page_size}


@router.get("/api/images/random")
def get_random_image(session: Session = Depends(get_db), admin_session = Depends(get_current_admin)):
    """随机获取一张图片 URL."""
    import random
    from sqlalchemy import func
    
    total = session.exec(select(func.count(UserImage.id))).one()
    if total == 0:
        return JSONResponse({
            "success": False,
            "error": "No images available"
        }, status_code=404)
    
    # 随机选择一张图片
    offset = random.randint(0, total - 1)
    image = session.exec(
        select(UserImage).offset(offset).limit(1)
    ).first()
    
    if image:
        return JSONResponse({
            "success": True,
            "url": image.url
        })
    else:
        return JSONResponse({
            "success": False,
            "error": "Failed to get random image"
        }, status_code=500)


@router.delete("/admin/users/{user_id}")
def delete_user(user_id: int, session: Session = Depends(get_db), admin_session = Depends(get_current_admin)):
    """
    删除用户及其所有相关记录。
    
    删除顺序：
    1. TaskLog (通过 task_id 删除相关的)
    2. Task (user_id)
    3. UserActivityLog (user_id)
    4. PostedMakeup (user_id)
    6. User (最后删除)
    """
    try:
        # 检查用户是否存在
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # 1. 删除该用户的所有 Task（先获取 task_ids）
        tasks = session.exec(select(Task).where(Task.user_id == user_id)).all()
        task_ids = [task.id for task in tasks if task.id is not None]
        
        # 2. 删除这些任务相关的 TaskLog
        if task_ids:
            task_logs = session.exec(select(TaskLog).where(TaskLog.task_id.in_(task_ids))).all()
            for log in task_logs:
                session.delete(log)
        
        # 3. 删除该用户的所有 Task
        for task in tasks:
            session.delete(task)
        
        # 4. 删除该用户的所有 UserActivityLog
        activity_logs = session.exec(select(UserActivityLog).where(UserActivityLog.user_id == user_id)).all()
        for log in activity_logs:
            session.delete(log)
        
        # 5. 删除该用户的所有 PostedMakeup
        makeups = session.exec(select(PostedMakeup).where(PostedMakeup.user_id == user_id)).all()
        for makeup in makeups:
            session.delete(makeup)
        
        # 7. 最后删除用户本身
        session.delete(user)
        
        # 提交所有更改
        session.commit()
        
        return JSONResponse({
            "success": True,
            "message": f"User {user_id} and all related records deleted successfully"
        })
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        import traceback
        error_detail = traceback.format_exc()
        print(f"[Error] Delete user failed: {error_detail}")
        return JSONResponse({
            "success": False,
            "error": f"删除用户失败: {str(e)}"
        }, status_code=500)


