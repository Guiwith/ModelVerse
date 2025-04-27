"""
用于模型训练的工具函数
"""

import os
import yaml
import json
import asyncio
import re
import shutil
from typing import Dict, Any, Optional, List, Set
from datetime import datetime
from pathlib import Path
import subprocess
import torch
import logging
from models import TrainingTask, TrainingStatus, Resource, ResourceType, DownloadStatus, ResourceCreate
from database import update_training_task, add_training_log, get_resource, create_resource, update_resource_status, clear_training_logs, save_db, get_training_task
from fastapi import WebSocket
import time

logger = logging.getLogger(__name__)

# 目录配置
BASE_DIR = Path(".")
TRAINING_CONFIGS_DIR = BASE_DIR / "training_configs"
TRAINED_MODELS_DIR = BASE_DIR / "trainedmodels"
MODELS_DIR = BASE_DIR / "models"
DATASETS_DIR = BASE_DIR / "datasets"

# 创建必要的目录
TRAINING_CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
TRAINED_MODELS_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)
DATASETS_DIR.mkdir(parents=True, exist_ok=True)

# 存储活跃的WebSocket连接
active_connections: Dict[str, Set] = {}

# 存储活跃的训练进程
active_processes: List[Dict[str, Any]] = []

def get_model_path(model_id: int) -> Optional[str]:
    """获取模型的本地路径"""
    model = get_resource(resource_id=model_id)
    if not model or model.resource_type != ResourceType.MODEL:
        return None
    return model.local_path

def get_dataset_path(dataset_id: int) -> Optional[str]:
    """获取数据集的本地路径"""
    dataset = get_resource(resource_id=dataset_id)
    if not dataset or dataset.resource_type != ResourceType.DATASET:
        return None
    return dataset.local_path

def generate_training_config(task: TrainingTask) -> str:
    """生成训练配置文件"""
    # 获取模型和数据集路径
    model_resource = get_resource(resource_id=task.base_model_id)
    dataset_resource = get_resource(resource_id=task.dataset_id)
    
    if not model_resource or not dataset_resource:
        raise ValueError("模型或数据集不存在")
    
    # 构建配置字典 - 严格按照示例中的字段顺序
    config = {}
    
    # 获取训练类型（默认为SFT）
    training_type = task.config_params.get("training_type", "SFT") if task.config_params else "SFT"
    
    # model部分
    config["model"] = {
        "model_name": model_resource.repo_id,
        "model_max_length": 2048,
        "torch_dtype_str": "bfloat16",
        "attn_implementation": "sdpa",
        "load_pretrained_weights": True,
        "trust_remote_code": True
    }
    
    # 根据训练类型设置不同的model配置
    if training_type == "LONGCTX":
        # 长上下文训练需要更大的上下文长度
        config["model"]["model_max_length"] = 32768
        config["model"]["enable_liger_kernel"] = True
    elif training_type == "PRETRAIN":
        # 预训练模型可能不需要加载预训练权重
        config["model"]["load_pretrained_weights"] = False
    
    # data部分
    config["data"] = {
        "train": {
            "datasets": [
                {"dataset_name": dataset_resource.repo_id}
            ],
            "target_col": "prompt"
        }
    }
    
    # 根据训练类型设置不同的data配置
    if training_type in ["PRETRAIN", "LONGCTX"]:
        # 预训练和长上下文训练需要数据流
        config["data"]["train"]["stream"] = True
        config["data"]["train"]["pack"] = True
        config["data"]["train"]["use_async_dataset"] = True
        
        if training_type == "LONGCTX":
            # 长上下文训练需要更长的序列长度
            config["data"]["train"]["datasets"][0]["dataset_kwargs"] = {"seq_length": 32768}
    
    # training部分 - 按照示例顺序排列
    config["training"] = {
        "trainer_type": "TRL_SFT",
        "save_final_model": True,
        "save_steps": 100,
        "max_steps": 10,
        "per_device_train_batch_size": 4,
        "gradient_accumulation_steps": 4,
        "ddp_find_unused_parameters": False,
        "optimizer": "adamw_torch",
        "learning_rate": 2.0e-05,
        "compile": False,
        "dataloader_num_workers": "auto",
        "dataloader_prefetch_factor": 32,
        "seed": 192847,
        "use_deterministic": True,
        "logging_steps": 5,
        "log_model_summary": False,
        "empty_device_cache_steps": 50,
        "output_dir": str(TRAINED_MODELS_DIR / task.name),
        "include_performance_metrics": True
    }
    
    # 根据训练类型调整training配置
    if training_type == "DPO":
        config["training"]["trainer_type"] = "TRL_DPO"
    elif training_type == "PRETRAIN":
        # 预训练通常使用更大的批次和不同的优化器
        config["training"]["optimizer"] = "adafactor"
        config["training"]["lr_scheduler_type"] = "cosine_with_min_lr"
        config["training"]["lr_scheduler_kwargs"] = {"min_lr": 3.0e-5}
        config["training"]["learning_rate"] = 3.0e-4
        config["training"]["warmup_steps"] = 500
        config["training"]["weight_decay"] = 0.1
    elif training_type == "LONGCTX":
        # 长上下文训练通常使用较小的批次大小
        config["training"]["per_device_train_batch_size"] = 1
        config["training"]["gradient_accumulation_steps"] = 1
        config["training"]["compile"] = True
        config["training"]["optimizer"] = "adamw_torch_fused"
    
    # 添加分布式训练配置
    if training_type in ["FSDP", "DDP"]:
        if training_type == "FSDP":
            # 添加FSDP配置
            config["fsdp"] = {
                "enable_fsdp": True,
                "sharding_strategy": "HYBRID_SHARD",
                "mixed_precision": "bf16",
                "forward_prefetch": True,
                "auto_wrap_policy": "TRANSFORMER_BASED_WRAP",
                "transformer_layer_cls": "LlamaDecoderLayer"
            }
            # FSDP通常使用fusion优化器
            config["training"]["optimizer"] = "adamw_torch_fused"
            config["training"]["enable_gradient_checkpointing"] = True
            config["training"]["gradient_checkpointing_kwargs"] = {"use_reentrant": False}
        
        # DDP特定配置
        if training_type == "DDP":
            config["training"]["ddp_find_unused_parameters"] = False
            config["training"]["enable_gradient_checkpointing"] = False
    
    # 添加LoRA配置(针对FSDP+LoRA场景)
    if training_type == "FSDP_LORA":
        config["training"]["use_peft"] = True
        config["peft"] = {
            "q_lora": False,
            "lora_r": 8,
            "lora_alpha": 16,
            "lora_dropout": 0.0,
            "lora_target_modules": [
                "q_proj",
                "v_proj"
            ]
        }
        # FSDP配置
        config["fsdp"] = {
            "enable_fsdp": True,
            "sharding_strategy": "HYBRID_SHARD",
            "forward_prefetch": True,
            "auto_wrap_policy": "TRANSFORMER_BASED_WRAP",
            "transformer_layer_cls": "LlamaDecoderLayer"
        }
        config["training"]["optimizer"] = "adamw_torch_fused"
        config["training"]["enable_gradient_checkpointing"] = True
        config["training"]["gradient_checkpointing_kwargs"] = {"use_reentrant": False}
    
    # 应用用户自定义配置
    if task.config_params:
        # 更新模型配置
        if "model" in task.config_params:
            # 兼容性修复：将max_length转换为model_max_length
            model_config = task.config_params["model"].copy()
            if "max_length" in model_config and "model_max_length" not in model_config:
                model_config["model_max_length"] = model_config.pop("max_length")
            # 确保不带入额外的max_length
            if "max_length" in model_config:
                del model_config["max_length"]
            # 确保trust_remote_code为True
            model_config["trust_remote_code"] = True
            
            # 更新各个字段，保持配置顺序
            for key, value in model_config.items():
                config["model"][key] = value
        
        # 更新数据配置
        if "data" in task.config_params:
            # 保持datasets不变，只更新其他数据配置
            data_config = task.config_params["data"]
            for key, value in data_config.items():
                if key != "datasets":
                    config["data"]["train"][key] = value
        
        # 更新训练配置
        if "training" in task.config_params:
            training_config = task.config_params["training"]
            for key, value in training_config.items():
                if key != "output_dir":  # 不允许覆盖输出目录
                    config["training"][key] = value
        
        # 更新FSDP配置
        if "fsdp" in task.config_params:
            if "fsdp" not in config:
                config["fsdp"] = {}
            for key, value in task.config_params["fsdp"].items():
                config["fsdp"][key] = value
        
        # 更新PEFT配置
        if "peft" in task.config_params:
            if "peft" not in config:
                config["peft"] = {}
            for key, value in task.config_params["peft"].items():
                config["peft"][key] = value
    
    # 确保输出目录存在
    output_dir = Path(config["training"]["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 转换输出路径为POSIX格式
    config["training"]["output_dir"] = str(output_dir).replace("\\", "/")
    
    # 自定义YAML表示类，确保特定字符串使用双引号
    class QuotedString(str):
        pass
    
    def quoted_scalar_representer(dumper, data):
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='"')
    
    # 注册表示器
    yaml.add_representer(QuotedString, quoted_scalar_representer)
    
    # 确保特定字段使用双引号
    config["model"]["model_name"] = QuotedString(config["model"]["model_name"])
    config["model"]["torch_dtype_str"] = QuotedString(config["model"]["torch_dtype_str"])
    config["model"]["attn_implementation"] = QuotedString(config["model"]["attn_implementation"])
    config["data"]["train"]["datasets"][0]["dataset_name"] = QuotedString(config["data"]["train"]["datasets"][0]["dataset_name"])
    config["data"]["train"]["target_col"] = QuotedString(config["data"]["train"]["target_col"])
    config["training"]["trainer_type"] = QuotedString(config["training"]["trainer_type"])
    config["training"]["optimizer"] = QuotedString(config["training"]["optimizer"])
    
    if isinstance(config["training"]["dataloader_num_workers"], str):
        config["training"]["dataloader_num_workers"] = QuotedString(config["training"]["dataloader_num_workers"])
    
    config["training"]["output_dir"] = QuotedString(config["training"]["output_dir"])
    
    # 写入配置文件
    config_path = TRAINING_CONFIGS_DIR / f"{task.name}_config.yaml"
    try:
        with open(config_path, "w") as f:
            # 使用PyYAML的dump方法，不使用默认的字段排序
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            
        # 记录调试信息
        logger.info(f"成功生成训练配置文件: {config_path}")
        logger.debug(f"配置内容: {config}")
    except Exception as e:
        logger.error(f"生成配置文件失败: {str(e)}")
        raise
    
    # 更新任务的配置路径和输出路径
    update_training_task(
        task_id=task.id, 
        config_path=str(config_path),
        output_path=str(output_dir)
    )
    
    return str(config_path)

async def broadcast_log(task_id: int, message: str, level: str = "INFO"):
    """向连接的WebSocket客户端广播日志消息"""
    # 记录到数据库
    add_training_log(task_id, message, level)
    
    # 同时记录到服务器日志
    if level == "INFO":
        logger.info(f"[Task {task_id}] {message}")
    elif level == "WARNING":
        logger.warning(f"[Task {task_id}] {message}")
    elif level == "ERROR":
        logger.error(f"[Task {task_id}] {message}")
    
    # 广播到WebSocket连接
    if str(task_id) in active_connections:
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "content": message,
            "level": level
        }
        
        for connection in active_connections[str(task_id)].copy():
            try:
                await connection.send_text(json.dumps(log_data))
            except Exception as e:
                logger.error(f"发送日志到WebSocket失败: {str(e)}")
                active_connections[str(task_id)].remove(connection)

async def parse_progress(line: str, task_id: int) -> Optional[float]:
    """解析训练日志中的进度信息"""
    # 匹配类似 "Step 5/10" 的模式
    step_match = re.search(r"Step (\d+)/(\d+)", line)
    if step_match:
        current_step = int(step_match.group(1))
        total_steps = int(step_match.group(2))
        
        if total_steps > 0:
            progress = current_step / total_steps
            # 更新数据库中的进度
            update_training_task(task_id=task_id, progress=progress)
            return progress
    
    return None

async def run_training(task_id: int):
    """执行训练任务"""
    # 导入清除日志函数
    from database import clear_training_logs, save_db
    
    # 1. 清除该任务的所有旧日志
    clear_training_logs(task_id)
    logger.info(f"已清除任务 {task_id} 的旧日志")
    
    # 2. 立即保存数据库，确保日志被完全清除
    save_db()
    
    # 3. 添加短暂延迟，确保清除操作完成
    await asyncio.sleep(1)
    
    # 4. 获取任务信息
    task = update_training_task(
        task_id=task_id,
        status=TrainingStatus.RUNNING,
        started_at=datetime.now(),
        progress=0.0
    )
    
    if not task:
        logger.error(f"找不到任务 ID: {task_id}")
        return
    
    # 5. 清理之前训练的输出目录
    output_dir = TRAINED_MODELS_DIR / task.name
    if output_dir.exists():
        try:
            shutil.rmtree(output_dir)
            await broadcast_log(task_id, f"清理之前的训练输出目录: {output_dir}")
        except Exception as e:
            await broadcast_log(task_id, f"清理训练输出目录失败: {str(e)}", "WARNING")
    
    # 6. 清理之前的配置文件
    config_path = TRAINING_CONFIGS_DIR / f"{task.name}_config.yaml"
    if config_path.exists():
        try:
            os.remove(config_path)
            await broadcast_log(task_id, f"清理之前的配置文件: {config_path}")
        except Exception as e:
            await broadcast_log(task_id, f"清理配置文件失败: {str(e)}", "WARNING")
    
    # 7. 添加训练开始日志 - 使用新的时间戳
    await broadcast_log(task_id, f"开始训练任务: {task.name}")
    await broadcast_log(task_id, f"任务ID: {task_id}, 时间戳: {datetime.now().isoformat()}")
    await broadcast_log(task_id, f"初始化训练环境...")
    
    try:
        # 确保配置文件已生成
        if not task.config_path:
            await broadcast_log(task_id, f"生成训练配置文件...")
            config_path = generate_training_config(task)
            await broadcast_log(task_id, f"训练配置文件已生成: {config_path}")
        else:
            config_path = task.config_path
            await broadcast_log(task_id, f"使用现有配置文件: {config_path}")
            
        if not os.path.exists(config_path):
            error_msg = f"配置文件不存在: {config_path}"
            logger.error(error_msg)
            await broadcast_log(task_id, error_msg, "ERROR")
            update_training_task(
                task_id=task_id,
                status=TrainingStatus.FAILED,
                completed_at=datetime.now(),
                error_message=error_msg
            )
            return
        
        # 检查配置文件内容
        try:
            with open(config_path, 'r') as f:
                config_content = f.read()
                await broadcast_log(task_id, f"配置文件有效，大小: {len(config_content)} 字节")
        except Exception as e:
            await broadcast_log(task_id, f"读取配置文件失败: {str(e)}", "ERROR")
        
        # 检查oumi命令是否可用
        await broadcast_log(task_id, "检查oumi命令...")
        try:
            which_cmd = "where" if os.name == "nt" else "which"
            oumi_path = subprocess.check_output([which_cmd, "oumi"], text=True).strip()
            await broadcast_log(task_id, f"找到oumi命令: {oumi_path}")
        except subprocess.CalledProcessError:
            error_msg = "oumi命令不可用，请确保已安装并添加到系统路径"
            logger.error(error_msg)
            await broadcast_log(task_id, error_msg, "ERROR")
            update_training_task(
                task_id=task_id,
                status=TrainingStatus.FAILED,
                completed_at=datetime.now(),
                error_message=error_msg
            )
            return
        
        # 构建训练命令
        cmd = ["oumi", "train", "-c", config_path]
        await broadcast_log(task_id, f"准备执行命令: {' '.join(cmd)}")
        
        # 设置环境变量
        env = os.environ.copy()
        env.update({
            'NCCL_P2P_DISABLE': '1',
            'NCCL_IB_DISABLE': '1'
        })
        await broadcast_log(task_id, f"设置环境变量: NCCL_P2P_DISABLE=1, NCCL_IB_DISABLE=1")
        
        # 启动训练进程
        await broadcast_log(task_id, f"正在启动训练进程...")
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env  # 使用更新后的环境变量
            )
            await broadcast_log(task_id, f"进程已启动，PID: {process.pid}")
        except Exception as e:
            error_msg = f"启动进程失败: {str(e)}"
            logger.error(error_msg)
            await broadcast_log(task_id, error_msg, "ERROR")
            update_training_task(
                task_id=task_id,
                status=TrainingStatus.FAILED,
                completed_at=datetime.now(),
                error_message=error_msg
            )
            return
        
        # 处理标准输出
        async def read_stdout():
            await broadcast_log(task_id, "开始监控标准输出...")
            line_count = 0
            while True:
                line = await process.stdout.readline()
                if not line:
                    await broadcast_log(task_id, "标准输出监控结束")
                    break
                    
                line_str = line.decode("utf-8").strip()
                line_count += 1
                await broadcast_log(task_id, line_str)
                logger.info(f"训练输出 [任务 {task_id}]: {line_str}")
                
                # 解析进度
                await parse_progress(line_str, task_id)
            await broadcast_log(task_id, f"共处理 {line_count} 行标准输出")
        
        # 处理标准错误
        async def read_stderr():
            await broadcast_log(task_id, "开始监控标准错误...")
            error_count = 0
            while True:
                line = await process.stderr.readline()
                if not line:
                    await broadcast_log(task_id, "标准错误监控结束")
                    break
                    
                line_str = line.decode("utf-8").strip()
                error_count += 1
                await broadcast_log(task_id, line_str, "ERROR")
                logger.error(f"训练错误 [任务 {task_id}]: {line_str}")
            await broadcast_log(task_id, f"共处理 {error_count} 行标准错误")
        
        # 同时处理stdout和stderr
        try:
            await broadcast_log(task_id, "开始处理进程输出...")
            await asyncio.gather(
                read_stdout(),
                read_stderr()
            )
            await broadcast_log(task_id, "进程输出处理完成")
        except Exception as e:
            error_msg = f"处理进程输出失败: {str(e)}"
            logger.error(error_msg)
            await broadcast_log(task_id, error_msg, "ERROR")
        
        # 等待进程完成
        exit_code = await process.wait()
        await broadcast_log(task_id, f"进程已退出，退出码: {exit_code}")
        logger.info(f"训练进程退出 [任务 {task_id}]，退出码: {exit_code}")
        
        # 根据退出码更新任务状态
        if exit_code == 0:
            # 训练成功
            update_training_task(
                task_id=task_id,
                status=TrainingStatus.COMPLETED,
                completed_at=datetime.now(),
                progress=1.0
            )
            
            await broadcast_log(task_id, "训练成功完成")
            
            # 获取最新的任务信息
            task = update_training_task(task_id=task_id)
            
            # 将训练好的模型添加到资源列表
            model_resource = get_resource(resource_id=task.base_model_id)
            if model_resource and task.output_path:
                # 创建新的资源记录
                trained_resource = create_resource(
                    resource_data=ResourceCreate(
                        name=f"trained_{model_resource.name}",
                        description=f"自训练模型，基于 {model_resource.name}",
                        repo_id=f"local/{task.name}",
                        resource_type=ResourceType.MODEL
                    ),
                    user_id=task.user_id
                )
                
                # 更新资源状态为已完成
                update_resource_status(
                    resource_id=trained_resource.id,
                    status=DownloadStatus.COMPLETED,
                    progress=1.0,
                    local_path=task.output_path
                )
                
                await broadcast_log(task_id, f"已创建自训练模型资源: {trained_resource.name}")
        else:
            # 训练失败
            update_training_task(
                task_id=task_id,
                status=TrainingStatus.FAILED,
                completed_at=datetime.now(),
                error_message=f"训练进程退出码: {exit_code}"
            )
            
            await broadcast_log(task_id, f"训练失败，进程退出码: {exit_code}", "ERROR")
    
    except Exception as e:
        # 处理任何异常
        error_message = str(e)
        logger.exception(f"训练任务 {task_id} 出错: {error_message}")
        update_training_task(
            task_id=task_id,
            status=TrainingStatus.FAILED,
            completed_at=datetime.now(),
            error_message=error_message
        )
        
        await broadcast_log(task_id, f"训练出错: {error_message}", "ERROR")

async def stop_training(task_id: int):
    """停止训练任务"""
    task = get_training_task(task_id=task_id)
    if not task:
        logger.error(f"找不到任务 ID: {task_id}")
        return
    
    # 查找任务进程
    for process in active_processes.copy():
        if process.get("task_id") == task_id:
            try:
                # 获取进程对象
                proc = process.get("process")
                if proc:
                    # 尝试终止进程
                    proc.terminate()
                    await asyncio.sleep(1)  # 给进程一点时间来终止
                    
                    # 如果进程仍在运行，强制终止
                    if proc.returncode is None:
                        proc.kill()
                    
                    logger.info(f"已停止训练进程: {proc.pid}")
                    active_processes.remove(process)
                    
                    # 更新任务状态
                    update_training_task(
                        task_id=task_id,
                        status=TrainingStatus.STOPPED,
                        completed_at=datetime.now(),
                        error_message="用户手动停止训练"
                    )
                    
                    await broadcast_log(task_id, "训练任务已被用户停止", "WARNING")
                    
                    # 清理训练输出目录 - 当用户停止训练时，不需要保留部分训练结果
                    output_dir = TRAINED_MODELS_DIR / task.name
                    if output_dir.exists():
                        try:
                            shutil.rmtree(output_dir)
                            await broadcast_log(task_id, f"已清理训练输出目录: {output_dir}", "INFO")
                        except Exception as e:
                            await broadcast_log(task_id, f"清理训练输出目录失败: {str(e)}", "ERROR")
                    
                    return True
            except Exception as e:
                logger.error(f"停止训练任务失败: {str(e)}")
    
    # 如果没有找到进程，但任务状态为运行中，更新为停止
    if task.status == TrainingStatus.RUNNING:
        update_training_task(
            task_id=task_id,
            status=TrainingStatus.STOPPED,
            completed_at=datetime.now(),
            error_message="训练进程未找到"
        )
        await broadcast_log(task_id, "训练进程未找到，状态已更新为停止", "WARNING")
        return True
    
    return False

def register_websocket(task_id: Any, websocket: WebSocket):
    """注册WebSocket连接"""
    # 确保task_id总是以字符串形式存储
    task_id_str = str(task_id)
    
    if task_id_str not in active_connections:
        active_connections[task_id_str] = set()
    active_connections[task_id_str].add(websocket)
    logger.info(f"WebSocket连接已注册: {task_id_str}")

def remove_websocket(task_id: Any, websocket: WebSocket):
    """移除WebSocket连接"""
    # 确保task_id总是以字符串形式存储
    task_id_str = str(task_id)
    
    if task_id_str in active_connections:
        active_connections[task_id_str].discard(websocket)
        if not active_connections[task_id_str]:
            del active_connections[task_id_str]
        logger.info(f"WebSocket连接已移除: {task_id_str}")

def get_gpu_info() -> Dict[str, Any]:
    """获取GPU信息"""
    try:
        # 使用nvidia-smi命令获取GPU信息
        result = subprocess.run(['nvidia-smi', '--query-gpu=gpu_name,memory.total,memory.free', '--format=csv,noheader,nounits'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            # 解析输出
            gpu_info = result.stdout.strip().split('\n')[0].split(',')
            return {
                'name': gpu_info[0].strip(),
                'total_memory': int(gpu_info[1].strip()),
                'free_memory': int(gpu_info[2].strip())
            }
    except Exception as e:
        logger.error(f"获取GPU信息失败: {str(e)}")
    return {}

def is_compute_gpu(gpu_name: str) -> bool:
    """检查是否为计算卡"""
    # 检查是否为A系列计算卡
    if 'A' in gpu_name:
        return True
    
    # 检查是否为5090或更高版本
    try:
        # 提取数字部分
        numbers = ''.join(filter(str.isdigit, gpu_name))
        if numbers:
            gpu_number = int(numbers)
            return gpu_number >= 5090
    except:
        pass
    
    return False

def get_training_env_vars(gpu_name: str) -> Dict[str, str]:
    """获取训练环境变量"""
    # 默认总是禁用P2P和IB功能，避免RTX系列GPU出现NotImplementedError
    env_vars = {
        'NCCL_P2P_DISABLE': '1',
        'NCCL_IB_DISABLE': '1'
    }
    
    logger.info(f"默认禁用P2P和IB功能，设置环境变量: {env_vars}")
    
    return env_vars

def start_training_task(task_id: int, config: Dict[str, Any]) -> None:
    """启动训练任务"""
    try:
        # 获取GPU信息
        gpu_info = get_gpu_info()
        gpu_name = gpu_info.get('name', '')
        
        # 获取环境变量
        env_vars = get_training_env_vars(gpu_name)
        
        # 设置基础环境变量
        env = os.environ.copy()
        env.update(env_vars)
        
        # 准备训练命令
        cmd = [
            'python', 'train.py',
            '--task_id', str(task_id),
            '--config', json.dumps(config)
        ]
        
        # 启动训练进程
        process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        logger.info(f"训练任务 {task_id} 已启动，使用GPU: {gpu_name}")
        if env_vars:
            logger.info(f"使用环境变量: {env_vars}")
        
        return process
        
    except Exception as e:
        logger.error(f"启动训练任务失败: {str(e)}")
        raise 

async def broadcast_resource_update(message: dict):
    """广播资源更新消息"""
    if "resources" not in active_connections:
        return
    
    # 确保包含必要的字段
    if "resource_id" in message and "type" in message and message["type"] == "resource_update":
        # 尝试获取完整的资源信息
        try:
            from database import get_resource
            resource = get_resource(message["resource_id"])
            if resource:
                # 使用完整的资源对象
                message["resource"] = resource.dict()
                
                # 保持向后兼容
                if "status" not in message and "status" in message["resource"]:
                    message["status"] = message["resource"]["status"]
                if "progress" not in message and "progress" in message["resource"]:
                    message["progress"] = message["resource"]["progress"]
                if "error_message" not in message and "error_message" in message["resource"]:
                    message["error_message"] = message["resource"]["error_message"]
        except Exception as e:
            logger.error(f"获取资源信息失败: {str(e)}")
    
    disconnected = set()
    for websocket in active_connections["resources"]:
        try:
            await websocket.send_json(message)
            logger.debug(f"已发送资源更新: {message}")
        except Exception as e:
            logger.error(f"发送WebSocket消息失败: {str(e)}")
            disconnected.add(websocket)
            
    # 清理断开的连接
    for websocket in disconnected:
        remove_websocket("resources", websocket)

def update_download_status(resource_id: int, status: str, progress: float = None):
    """更新下载状态"""
    try:
        # 更新数据库中的状态
        update_resource_status(resource_id, status, progress)
        
        # 获取更新后的资源信息
        resource = get_resource(resource_id)
        if resource:
            # 广播更新消息 - 只需要最基本的信息，broadcast_resource_update会补充完整信息
            asyncio.create_task(broadcast_resource_update({
                "type": "resource_update",
                "resource_id": resource_id
            }))
    except Exception as e:
        logger.error(f"更新下载状态失败: {str(e)}")

async def download_resource(resource_id: int, source: str = "OFFICIAL"):
    """下载资源"""
    resource = get_resource(resource_id=resource_id)
    if not resource:
        return
    
    try:
        # 更新状态为下载中
        update_resource_status(resource_id, DownloadStatus.DOWNLOADING, 0.0)
        
        # 确定下载目录
        if resource.resource_type == ResourceType.MODEL:
            base_dir = MODELS_DIR
        else:
            base_dir = DATASETS_DIR
            
        # 创建下载目录
        download_dir = base_dir / resource.repo_id.replace("/", "_")
        download_dir.mkdir(parents=True, exist_ok=True)
        
        # 下载资源
        logger.info(f"开始下载资源: {resource.repo_id} 到 {download_dir}")
        
        # 使用huggingface_hub下载
        from huggingface_hub import snapshot_download
        
        # 下载进度回调
        last_progress = 0
        last_update_time = time.time()
        is_completed = False
        
        def progress_callback(current, total):
            nonlocal last_progress, is_completed, last_update_time
            if is_completed:
                return
                
            if total > 0:
                current_time = time.time()
                progress = (current / total) * 100
                # 只在进度变化超过1%或者超过5秒未更新时发送更新
                if progress - last_progress >= 1 or current_time - last_update_time >= 5:
                    last_progress = progress
                    last_update_time = current_time
                    update_resource_status(
                        resource_id=resource_id,
                        status=DownloadStatus.DOWNLOADING,
                        progress=progress
                    )
        
        # 执行下载
        try:
            snapshot_download(
                repo_id=resource.repo_id,
                local_dir=str(download_dir),
                local_dir_use_symlinks=False,
                resume_download=True,
                progress_callback=progress_callback
            )
            
            # 标记下载完成
            is_completed = True
            
            # 更新资源的本地路径和状态为已完成
            update_resource_status(
                resource_id=resource_id,
                status=DownloadStatus.COMPLETED,
                progress=100.0,
                local_path=str(download_dir)
            )
            
            # 强制发送一次更新通知，确保前端即时更新
            resource = get_resource(resource_id)
            await broadcast_resource_update({
                "type": "resource_update",
                "resource_id": resource_id,
                "status": DownloadStatus.COMPLETED.value,
                "progress": 100.0,
                "resource": resource.dict(),
                "force_refresh": True
            })
            
            logger.info(f"资源下载完成: {resource.repo_id}")
            
        except Exception as e:
            # 更新状态为失败
            error_message = str(e)
            logger.error(f"下载失败: {error_message}")
            
            update_resource_status(
                resource_id=resource_id,
                status=DownloadStatus.FAILED,
                error_message=error_message
            )
            
            # 强制发送一次失败通知
            resource = get_resource(resource_id)
            await broadcast_resource_update({
                "type": "resource_update",
                "resource_id": resource_id,
                "status": DownloadStatus.FAILED.value,
                "error_message": error_message,
                "resource": resource.dict(),
                "force_refresh": True
            })
            
            raise
        
    except Exception as e:
        logger.error(f"下载资源失败: {str(e)}")
        update_resource_status(
            resource_id=resource_id,
            status=DownloadStatus.FAILED,
            error_message=str(e)
        )
        raise

def clean_training_files(task_name: str, task_id: int = None):
    """清理训练任务相关的所有文件和目录
    
    Args:
        task_name: 任务名称
        task_id: 可选的任务ID，用于清理日志
    """
    cleaned_files = []
    errors = []
    
    # 1. 清理输出目录
    output_dir = TRAINED_MODELS_DIR / task_name
    if output_dir.exists():
        try:
            shutil.rmtree(output_dir)
            cleaned_files.append(str(output_dir))
            logger.info(f"已删除训练输出目录: {output_dir}")
        except Exception as e:
            errors.append(f"删除输出目录失败 {output_dir}: {str(e)}")
            logger.error(f"删除训练输出目录失败: {output_dir}, 错误: {str(e)}")
    
    # 2. 清理配置文件
    config_path = TRAINING_CONFIGS_DIR / f"{task_name}_config.yaml"
    if config_path.exists():
        try:
            os.remove(config_path)
            cleaned_files.append(str(config_path))
            logger.info(f"已删除训练配置文件: {config_path}")
        except Exception as e:
            errors.append(f"删除配置文件失败 {config_path}: {str(e)}")
            logger.error(f"删除配置文件失败: {config_path}, 错误: {str(e)}")
    
    # 3. 如果提供了任务ID，清理日志
    if task_id is not None:
        from database import clear_training_logs
        try:
            clear_training_logs(task_id)
            logger.info(f"已清除任务日志: 任务ID {task_id}")
            cleaned_files.append(f"任务 {task_id} 的日志")
        except Exception as e:
            errors.append(f"清除任务日志失败: {str(e)}")
            logger.error(f"清除任务日志失败: 任务ID {task_id}, 错误: {str(e)}")
    
    return {
        "success": len(errors) == 0,
        "cleaned_files": cleaned_files,
        "errors": errors
    } 