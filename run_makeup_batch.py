"""
临时脚本：并发执行妆造创建
并发数：5
"""
import concurrent.futures
import time
from datetime import datetime

# 配置
CONCURRENCY = 20  # 并发数
TOTAL_TASKS = 100  # 总任务数，根据需要调整


def run_makeup_creation(task_id: int) -> dict:
    """
    执行妆造创建
    
    @param task_id - 任务编号（用于日志）
    @returns 结果字典
    """
    from app.db import get_session
    from app.services.module_handlers import handle_makeup_creation
    
    start_time = time.time()
    
    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Task {task_id}: 开始执行...")
        
        with get_session() as session:
            result = handle_makeup_creation(session)
        
        elapsed = time.time() - start_time
        success = result.get("success", False)
        user_id = result.get("user_id", "N/A")
        
        if success:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Task {task_id}: ✓ 完成 (耗时 {elapsed:.1f}s, user_id={user_id})")
        else:
            warnings = result.get("warnings", [])
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Task {task_id}: ✗ 失败 (耗时 {elapsed:.1f}s, user_id={user_id}, warnings={warnings[:2]})")
        
        return {"task_id": task_id, "success": success, "user_id": user_id, "elapsed": elapsed}
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Task {task_id}: ✗ 异常: {e} (耗时 {elapsed:.1f}s)")
        return {"task_id": task_id, "success": False, "error": str(e), "elapsed": elapsed}


def main():
    print(f"=" * 60)
    print(f"妆造创建批量执行")
    print(f"并发数: {CONCURRENCY}")
    print(f"总任务数: {TOTAL_TASKS}")
    print(f"=" * 60)
    
    start_time = time.time()
    results = []
    
    # 使用线程池控制并发
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        # 提交所有任务
        futures = {executor.submit(run_makeup_creation, i): i for i in range(1, TOTAL_TASKS + 1)}
        
        # 等待所有任务完成
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results.append(result)
    
    # 统计结果
    total_elapsed = time.time() - start_time
    success_count = sum(1 for r in results if r.get("success"))
    fail_count = len(results) - success_count
    
    print(f"\n" + "=" * 60)
    print(f"执行完成!")
    print(f"总耗时: {total_elapsed:.1f}s")
    print(f"成功: {success_count}/{len(results)}")
    print(f"失败: {fail_count}/{len(results)}")
    print(f"=" * 60)


if __name__ == "__main__":
    main()
