"""APScheduler 集成."""
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from sqlmodel import Session, select

from app.db import get_session
from app.services.task_runner import run_task
from app.models import Task, TaskStatus

scheduler = BackgroundScheduler()


def _run_pending() -> None:
    """执行到期任务，按照 scheduled_at 时间顺序执行。"""
    print(f"[Scheduler] ====== _run_pending START ======")
    with get_session() as session:
        # 按照 scheduled_at 时间顺序查询任务，确保按照生成顺序执行
        from sqlalchemy import asc
        due_tasks = session.exec(
            select(Task)
            .where(Task.scheduled_at <= datetime.utcnow(), Task.status == TaskStatus.pending)
            .order_by(asc(Task.scheduled_at))  # 按时间顺序排序
        ).all()
        print(f"[Scheduler] Found {len(due_tasks)} pending tasks (ordered by scheduled_at)")
        
        if due_tasks:
            print(f"[Scheduler] Task execution order:")
            for idx, task in enumerate(due_tasks[:10], 1):  # 只显示前10个
                print(f"  {idx}. ID={task.id}, type={task.type}, scheduled_at={task.scheduled_at}")
            if len(due_tasks) > 10:
                print(f"  ... and {len(due_tasks) - 10} more tasks")
        
        collect_topic_tasks = [t for t in due_tasks if t.type == "collect_topic"]
        if collect_topic_tasks:
            print(f"[Scheduler] Found {len(collect_topic_tasks)} collect_topic tasks: {[t.id for t in collect_topic_tasks]}")
        
        for task in due_tasks:
            print(f"[Scheduler] Executing task ID={task.id}, type={task.type}, scheduled_at={task.scheduled_at}")
            run_task(session, task)
    print(f"[Scheduler] ====== _run_pending END ======")


def init_scheduler(app: FastAPI) -> None:
    """启动调度器并注册定时任务。"""
    if scheduler.running:
        return

    scheduler.add_job(_run_pending, "interval", seconds=20, id="run_pending_tasks", max_instances=1)
    scheduler.start()

    @app.on_event("shutdown")
    def _shutdown() -> None:
        scheduler.shutdown(wait=False)


