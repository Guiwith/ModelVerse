#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
任务清理脚本 - 用于修复不一致的共享任务状态
使用方法: python cleanup_tasks.py
"""

import os
import sys
import logging

# 设置python路径，确保可以导入backend模块
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(script_dir))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("cleanup_tasks")

# 导入所需模块
try:
    from backend.database import get_all_inference_tasks, update_inference_task
    from backend.models import InferenceStatus
except ImportError as e:
    logger.error(f"无法导入必要的模块: {str(e)}")
    sys.exit(1)

def cleanup_shared_tasks():
    """清理不一致的共享任务状态"""
    logger.info("开始清理共享任务...")
    
    # 获取所有任务
    all_tasks = get_all_inference_tasks()
    logger.info(f"找到 {len(all_tasks)} 个任务")
    
    # 记录状态
    stats = {
        "total": len(all_tasks),
        "shared": 0,
        "fixed": 0,
        "errors": 0
    }
    
    # 遍历所有任务
    for task in all_tasks:
        # 只关注被标记为共享的任务
        if task.share_enabled:
            stats["shared"] += 1
            logger.info(f"检查共享任务 [{task.id}] {task.name} - 状态: {task.status}")
            
            # 检查任务是否真正可用
            is_valid = (
                task.status == InferenceStatus.RUNNING and 
                task.api_base is not None and 
                task.port is not None and
                task.process_id is not None
            )
            
            # 如果任务被标记为共享但实际不可用，修复它
            if not is_valid:
                logger.warning(f"任务 [{task.id}] {task.name} 被标记为共享但状态不一致")
                try:
                    # 禁用共享标志
                    update_inference_task(
                        task_id=task.id,
                        share_enabled=False
                    )
                    logger.info(f"已修复任务 [{task.id}] {task.name} - 禁用共享标志")
                    stats["fixed"] += 1
                except Exception as e:
                    logger.error(f"修复任务 [{task.id}] 失败: {str(e)}")
                    stats["errors"] += 1
    
    # 输出统计信息
    logger.info("清理完成!")
    logger.info(f"总任务数: {stats['total']}")
    logger.info(f"共享任务数: {stats['shared']}")
    logger.info(f"修复任务数: {stats['fixed']}")
    logger.info(f"错误数: {stats['errors']}")
    
    return stats

if __name__ == "__main__":
    try:
        cleanup_stats = cleanup_shared_tasks()
        if cleanup_stats["fixed"] > 0:
            logger.info("成功修复了一些不一致的共享任务。请重启服务以应用更改。")
        else:
            logger.info("没有发现需要修复的共享任务。")
    except Exception as e:
        logger.error(f"运行清理脚本时出错: {str(e)}")
        sys.exit(1) 