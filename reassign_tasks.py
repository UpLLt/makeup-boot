"""重新分配未执行任务的时间，按照比例分配确保均匀分布。"""
import sys
import io
import random
from datetime import datetime, timedelta
from typing import Dict, List
from sqlmodel import Session, select
from sqlalchemy import asc

# 修复中文乱码
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from app.db import engine
from app.models import Task, TaskStatus, TaskType

# 任务顺序（1-9）
MODULE_ORDER = [
    ("create_user", TaskType.create_user),        # 1. 创建用户
    ("checkin", TaskType.checkin),                # 2. 签到
    ("face_upload", TaskType.face_upload),        # 3. 上传人脸
    ("makeup_creation", TaskType.makeup_creation), # 4. 创建妆造
    ("post_community", TaskType.post_community),   # 5. 发布到社区
    ("like_collect", TaskType.like_collect),       # 6. 点赞收藏
    ("like_comment", TaskType.like_comment),       # 7. 点赞评论
    ("follow_user", TaskType.follow_user),         # 8. 关注用户
    ("collect_topic", TaskType.collect_topic),     # 9. 收藏话题
]

def gcd(a: int, b: int) -> int:
    """计算最大公约数。"""
    while b:
        a, b = b, a % b
    return a

def reassign_tasks(days=3, daily_start_hour=0, daily_end_hour=24, segments_per_day=12):
    """
    重新分配未执行任务的时间，按照比例分配。
    
    Args:
        days: 分配到多少天（默认3天）
        daily_start_hour: 每天开始时间（小时，默认0点）
        daily_end_hour: 每天结束时间（小时，默认24点）
        segments_per_day: 每天分成多少个时间段（默认12个）
    """
    with Session(engine) as session:
        # 查询所有未执行的任务
        pending_tasks = session.exec(
            select(Task)
            .where(Task.status == TaskStatus.pending)
            .order_by(asc(Task.id))  # 按ID排序，保持原始顺序
        ).all()
        
        if not pending_tasks:
            print("没有找到未执行的任务")
            return
        
        print(f"找到 {len(pending_tasks)} 个未执行的任务")
        
        # 按任务类型分组
        tasks_by_type: Dict[TaskType, List[Task]] = {}
        for task in pending_tasks:
            if task.type not in tasks_by_type:
                tasks_by_type[task.type] = []
            tasks_by_type[task.type].append(task)
        
        # 统计每种类型的任务数量
        type_counts: Dict[TaskType, int] = {}
        available_types: List[TaskType] = []
        for key, task_type in MODULE_ORDER:
            count = len(tasks_by_type.get(task_type, []))
            if count > 0:
                type_counts[task_type] = count
                available_types.append(task_type)
        
        # 打印当前任务分布
        print("\n当前任务分布:")
        total_tasks = 0
        for task_type in available_types:
            count = type_counts[task_type]
            total_tasks += count
            print(f"  {task_type.value}: {count} 个")
        print(f"  总计: {total_tasks} 个")
        
        if len(available_types) == 0:
            print("没有可分配的任务类型")
            return
        
        # 计算时间范围
        now_utc = datetime.utcnow()
        # 从下一个整点开始（比如现在是6:30，就从7:00开始）
        start_time = now_utc.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        # 如果开始时间早于每天的起始时间，调整到当天的起始时间
        if start_time.hour < daily_start_hour:
            start_time = start_time.replace(hour=daily_start_hour, minute=0)
        
        # 计算每天的工作时长（小时）
        if daily_end_hour == 24:
            daily_work_hours = 24
        else:
            daily_work_hours = daily_end_hour - daily_start_hour
        
        # 计算结束时间
        end_time = start_time
        for day in range(days):
            day_start = start_time.replace(hour=daily_start_hour, minute=0, second=0, microsecond=0) + timedelta(days=day)
            if daily_end_hour == 24:
                day_end = day_start + timedelta(days=1)
            else:
                day_end = day_start.replace(hour=daily_end_hour, minute=0, second=0, microsecond=0)
            if day == days - 1:
                end_time = day_end
        
        time_range = (end_time - start_time).total_seconds()
        
        print(f"\n分配配置:")
        print(f"  分配天数: {days} 天")
        print(f"  每天工作时间: {daily_start_hour}:00 - {daily_end_hour}:00")
        print(f"  时间范围: {start_time} 到 {end_time}")
        print(f"  总时长: {time_range / 3600:.2f} 小时")
        
        # 计算最大公约数，用于简化比例
        counts = [type_counts[t] for t in available_types]
        common_gcd = counts[0]
        for count in counts[1:]:
            common_gcd = gcd(common_gcd, count)
        
        # 计算简化后的比例
        type_ratios: Dict[TaskType, int] = {}
        for task_type in available_types:
            type_ratios[task_type] = type_counts[task_type] // common_gcd
        
        print(f"\n任务比例（简化后）: {[(t.value, type_ratios[t]) for t in available_types]}")
        
        # 为每种类型的任务创建索引指针
        type_indices: Dict[TaskType, int] = {}
        for task_type in available_types:
            type_indices[task_type] = 0
        
        # 按照比例创建任务序列
        shuffled_sequence: List[TaskType] = []
        
        # 计算每轮应该分配的任务数量（按照比例）
        ratio_sum = sum(type_ratios.values())
        max_count = max(type_counts.values())
        
        # 计算需要多少轮才能分配完所有任务
        # 每轮按照比例分配，直到所有任务分配完
        total_rounds = max((type_counts[t] + type_ratios[t] - 1) // type_ratios[t] for t in available_types)
        
        print(f"总共需要 {total_rounds} 轮来分配所有任务（每轮比例总和: {ratio_sum}）")
        
        for round_num in range(total_rounds):
            round_tasks: List[TaskType] = []
            for task_type in available_types:
                ratio = type_ratios[task_type]
                remaining = type_counts[task_type] - type_indices[task_type]
                # 在当前轮次中，按照比例添加该类型的任务
                # 如果剩余任务数小于比例，只添加剩余的任务
                tasks_to_add = min(ratio, remaining)
                for _ in range(tasks_to_add):
                    if type_indices[task_type] < type_counts[task_type]:
                        round_tasks.append(task_type)
            
            # 打乱当前轮次的任务顺序，但保持比例
            random.shuffle(round_tasks)
            shuffled_sequence.extend(round_tasks)
            
            # 检查是否所有任务都已分配
            all_assigned = all(type_indices[t] >= type_counts[t] for t in available_types)
            if all_assigned:
                break
        
        print(f"生成的任务序列长度: {len(shuffled_sequence)}")
        print(f"前20个任务类型: {[t.value for t in shuffled_sequence[:20]]}")
        
        # 按照序列分配时间
        task_index = 0
        task_interval = time_range / len(pending_tasks) if len(pending_tasks) > 0 else 0
        
        print("\n开始分配任务时间...")
        
        for task_type in shuffled_sequence:
            if task_index >= len(pending_tasks):
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
            task.scheduled_at = start_time + timedelta(seconds=offset_seconds)
            
            task_index += 1
            
            # 每分配100个任务打印一次进度
            if task_index % 100 == 0 or task_index == len(pending_tasks):
                print(f"  已分配 {task_index}/{len(pending_tasks)} 个任务")
        
        # 提交更改
        session.commit()
        print(f"\n[OK] 成功重新分配了 {task_index} 个任务的时间")
        
        # 验证分配结果
        print("\n验证分配结果（前30个任务）:")
        reassigned_tasks = session.exec(
            select(Task)
            .where(Task.status == TaskStatus.pending)
            .order_by(asc(Task.scheduled_at))
        ).all()
        
        # 统计前30个任务的类型分布
        type_counts_preview = {}
        for task in reassigned_tasks[:30]:
            task_type = task.type.value
            type_counts_preview[task_type] = type_counts_preview.get(task_type, 0) + 1
        
        print("  前30个任务的类型分布:")
        for task_type in available_types:
            count = type_counts_preview.get(task_type.value, 0)
            if count > 0:
                print(f"    {task_type.value}: {count} 个")
        
        print("\n  前30个任务的详细列表:")
        for idx, task in enumerate(reassigned_tasks[:30], 1):
            print(f"  {idx}. ID={task.id}, type={task.type.value}, scheduled_at={task.scheduled_at}")
        if len(reassigned_tasks) > 30:
            print(f"  ... and {len(reassigned_tasks) - 30} more tasks")

if __name__ == "__main__":
    # 可以调整参数：天数、每天开始/结束时间、每天时间段数
    # 0-24小时全天分配，分配到未来3天
    reassign_tasks(days=3, daily_start_hour=0, daily_end_hour=24, segments_per_day=12)
