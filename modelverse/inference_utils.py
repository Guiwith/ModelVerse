"""
用于模型推理的工具函数
"""

import os
import json
import asyncio
import subprocess
import socket
import psutil
import logging
import requests
import time
import shutil
from typing import Dict, Any, Optional, List, Set, Tuple
from datetime import datetime
from pathlib import Path
import torch
from models import InferenceTask, InferenceStatus
from database import update_inference_task, get_resource, get_inference_task

logger = logging.getLogger(__name__)

# 目录配置
BASE_DIR = Path(".")
MODELS_DIR = BASE_DIR / "models"
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# 存储活跃的推理进程
active_processes: List[Dict[str, Any]] = []

# 查找可用端口
def find_available_port(start_port: int = 8000, max_attempts: int = 100) -> int:
    """查找可用端口，从start_port开始尝试"""
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            result = s.connect_ex(('localhost', port))
            if result != 0:  # 端口未被占用
                return port
    raise RuntimeError(f"无法找到可用端口（尝试范围: {start_port}-{start_port + max_attempts - 1}）")

# 获取模型路径
def get_model_path(model_id: int) -> Optional[str]:
    """获取模型的本地路径"""
    model = get_resource(resource_id=model_id)
    if not model:
        return None
    return model.local_path

# 获取模型的显存占用估计（GB）
def estimate_model_memory(model_id: int, tensor_parallel_size: int = 1) -> float:
    """估计模型的显存占用（GB）"""
    model = get_resource(resource_id=model_id)
    if not model:
        return 0.0
    
    # 简单估算：根据模型名称或大小粗略估计
    # 实际占用取决于模型架构、量化和并行度
    
    # 从模型名称中提取参数规模（如果可能）
    model_name = model.name.lower()
    model_size = 0
    
    # 检查常见的命名模式
    for scale in ["7b", "13b", "70b", "1.8b", "3b", "2.7b"]:
        if scale in model_name:
            size_str = scale.replace("b", "")
            try:
                if "." in size_str:
                    model_size = float(size_str)
                else:
                    model_size = int(size_str)
            except ValueError:
                pass
            break
    
    # 默认估算
    if model_size == 0:
        # 基于文件大小粗略估计
        if model.size_mb:
            model_size = model.size_mb / 1024  # 转换为GB
    
    # 根据参数规模估算显存占用（粗略估计）
    if model_size <= 2:
        memory = 8.0  # ~2B 模型大约需要 8GB
    elif model_size <= 7:
        memory = 16.0  # ~7B 模型大约需要 16GB
    elif model_size <= 13:
        memory = 28.0  # ~13B 模型大约需要 28GB
    elif model_size <= 30:
        memory = 48.0  # ~30B 模型大约需要 48GB
    elif model_size <= 70:
        memory = 80.0  # ~70B 模型大约需要 80GB
    else:
        memory = 16.0  # 默认值
    
    # 考虑量化的影响（大约减少一半显存）
    if "quantization" in model_name or "int8" in model_name or "int4" in model_name:
        memory *= 0.5
    
    # 根据并行度调整
    if tensor_parallel_size > 1:
        memory = memory / tensor_parallel_size
    
    return memory

# 获取系统GPU信息
def get_gpu_info() -> Dict[str, Any]:
    """获取系统GPU信息"""
    try:
        if not torch.cuda.is_available():
            return {"available": False, "gpus": [], "total_memory": 0, "used_memory": 0, "free_memory": 0}
        
        gpu_count = torch.cuda.device_count()
        gpus = []
        total_memory = 0
        used_memory = 0
        
        for i in range(gpu_count):
            gpu_memory = torch.cuda.get_device_properties(i).total_memory / (1024 ** 3)  # GB
            total_memory += gpu_memory
            
            # 当前占用的估算
            used_memory_by_tasks = sum([p.get("gpu_memory", 0) for p in active_processes if p.get("gpu_device") == i])
            
            gpus.append({
                "id": i,
                "name": torch.cuda.get_device_name(i),
                "memory_total": gpu_memory,
                "memory_used": used_memory_by_tasks,
                "memory_free": gpu_memory - used_memory_by_tasks
            })
            
            used_memory += used_memory_by_tasks
        
        return {
            "available": True,
            "gpus": gpus,
            "total_memory": total_memory,
            "used_memory": used_memory,
            "free_memory": total_memory - used_memory,
            "max_concurrent_tasks": max(1, int((total_memory - used_memory) / 10))  # 假设每个任务需要10GB
        }
    except Exception as e:
        logger.error(f"获取GPU信息失败: {str(e)}")
        return {"available": False, "error": str(e), "gpus": [], "total_memory": 0, "used_memory": 0, "free_memory": 0}

# 构建vLLM启动命令
def build_vllm_command(task: InferenceTask, model_path: str) -> List[str]:
    """构建vLLM启动命令"""
    # 确保端口有效
    port = task.port
    if not port:
        # 如果端口为空，分配一个新端口
        port = find_available_port(start_port=8000)
        logger.info(f"任务端口为空，分配新端口: {port}")
    
    command = [
        "python", "-m", "vllm.entrypoints.openai.api_server",
        "--model", model_path,
        "--host", "0.0.0.0",
        "--port", str(port),
        "--tensor-parallel-size", str(task.tensor_parallel_size),
        "--max-model-len", str(task.max_model_len),
        "--served-model-name", task.name,  # 添加模型名称参数
        "--disable-log-requests",  # 禁用详细请求日志
        "--trust-remote-code"  # 信任远程代码，提高兼容性
    ]
    
    # 添加量化参数（如果启用）
    if task.quantization:
        command.extend(["--quantization", task.quantization])
    
    # 添加数据类型参数（如果不是auto）
    if task.dtype != "auto":
        command.extend(["--dtype", task.dtype])
    
    return command, port  # 返回命令和使用的端口

# 启动vLLM服务
async def start_inference_service(task_id: int) -> bool:
    """启动推理服务"""
    task = get_inference_task(task_id=task_id)
    if not task:
        logger.error(f"找不到推理任务: {task_id}")
        return False
    
    # 获取模型路径
    model_path = get_model_path(task.model_id)
    if not model_path:
        error_msg = f"找不到模型: {task.model_id}"
        logger.error(error_msg)
        update_inference_task(
            task_id=task_id,
            status=InferenceStatus.FAILED,
            error_message=error_msg
        )
        return False
    
    # 验证模型路径是否存在
    model_path_obj = Path(model_path)
    if not model_path_obj.exists():
        error_msg = f"模型路径不存在: {model_path}"
        logger.error(error_msg)
        update_inference_task(
            task_id=task_id,
            status=InferenceStatus.FAILED,
            error_message=error_msg
        )
        return False
    
    logger.info(f"模型路径验证成功: {model_path}")
    
    # 查找可用端口
    try:
        port = find_available_port(start_port=8000)
        logger.info(f"为推理任务 {task_id} 分配端口: {port}")
    except Exception as e:
        error_msg = f"无法找到可用端口: {str(e)}"
        logger.error(error_msg)
        update_inference_task(
            task_id=task_id,
            status=InferenceStatus.FAILED,
            error_message=error_msg
        )
        return False
    
    # 更新任务端口
    update_inference_task(
        task_id=task_id,
        port=port,
        api_base=f"http://localhost:{port}/v1"
    )
    task = get_inference_task(task_id=task_id)  # 重新获取更新后的任务
    
    # 构建命令
    command, used_port = build_vllm_command(task, model_path)
    command_str = " ".join(command)
    logger.info(f"启动推理服务: {command_str}")
    
    # 如果build_vllm_command分配了新端口，需要更新任务记录
    if used_port != task.port:
        update_inference_task(
            task_id=task_id,
            port=used_port,
            api_base=f"http://localhost:{used_port}/v1"
        )
        
    # 准备日志文件
    log_file = LOGS_DIR / f"inference_{task_id}.log"
    logger.info(f"推理日志文件路径: {log_file}")
    
    # 确保日志目录存在
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        # 启动进程
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            logger.info(f"推理进程启动成功: PID={process.pid}")
            
            # 异步读取输出并记录
            async def log_output():
                log_fp = open(log_file, "w")
                try:
                    while True:
                        line = await process.stdout.readline()
                        if not line and process.stdout.at_eof():
                            break
                        line_str = line.decode('utf-8', errors='replace').rstrip()
                        logger.info(f"vLLM输出: {line_str}")
                        log_fp.write(f"{line_str}\n")
                        log_fp.flush()
                except Exception as e:
                    logger.error(f"读取vLLM输出异常: {str(e)}")
                finally:
                    log_fp.close()
            
            async def log_error():
                try:
                    while True:
                        line = await process.stderr.readline()
                        if not line and process.stderr.at_eof():
                            break
                        line_str = line.decode('utf-8', errors='replace').rstrip()
                        logger.error(f"vLLM错误: {line_str}")
                        # 也写入到日志文件
                        with open(log_file, "a") as f:
                            f.write(f"ERROR: {line_str}\n")
                except Exception as e:
                    logger.error(f"读取vLLM错误输出异常: {str(e)}")
            
            # 启动日志记录任务，但不等待它完成
            asyncio.create_task(log_output())
            asyncio.create_task(log_error())
            
        except FileNotFoundError as e:
            error_msg = f"找不到Python或vLLM模块: {str(e)}"
            logger.error(error_msg)
            update_inference_task(
                task_id=task_id,
                status=InferenceStatus.FAILED,
                error_message=error_msg
            )
            return False
        except PermissionError as e:
            error_msg = f"权限错误，无法创建日志文件或启动进程: {str(e)}"
            logger.error(error_msg)
            update_inference_task(
                task_id=task_id,
                status=InferenceStatus.FAILED,
                error_message=error_msg
            )
            return False
        
        # 记录进程信息
        process_info = {
            "task_id": task_id,
            "process": process,
            "command": command_str,
            "port": used_port,
            "gpu_memory": estimate_model_memory(task.model_id, task.tensor_parallel_size),
            "gpu_device": 0  # 默认使用第一个GPU
        }
        active_processes.append(process_info)
        
        # 更新任务状态
        update_inference_task(
            task_id=task_id,
            status=InferenceStatus.RUNNING,
            process_id=process.pid,
            started_at=datetime.now(),
            gpu_memory=process_info["gpu_memory"],
            share_enabled=task.share_enabled,  # 保留共享设置
            display_name=task.display_name     # 保留显示名称
        )
        
        logger.info(f"推理服务已启动: 任务={task_id}, PID={process.pid}, 端口={used_port}")
        
        # 等待服务启动 - 增加初始等待时间
        await asyncio.sleep(5)
        
        # 检查服务是否成功启动
        tries = 0
        max_tries = 20  # 增加尝试次数
        while tries < max_tries:
            # 检查进程是否仍在运行
            if process.returncode is not None:
                error_msg = f"推理服务进程已终止: 退出码={process.returncode}"
                logger.error(error_msg)
                update_inference_task(
                    task_id=task_id,
                    status=InferenceStatus.FAILED,
                    error_message=error_msg
                )
                active_processes.remove(process_info)
                return False
                
            try:
                # 检查服务健康状态
                logger.info(f"尝试连接推理服务健康检查: http://localhost:{used_port}/v1/models (尝试 {tries+1}/{max_tries})")
                response = requests.get(f"http://localhost:{used_port}/v1/models", timeout=5)
                if response.status_code == 200:
                    logger.info(f"推理服务准备就绪: 任务={task_id}, 端口={used_port}, 响应={response.text[:100]}")
                    return True
                else:
                    logger.warning(f"推理服务健康检查返回非200状态码: {response.status_code}, 响应: {response.text[:100]}")
            except requests.exceptions.RequestException as e:
                logger.warning(f"推理服务健康检查连接失败: {str(e)}")
            except Exception as e:
                logger.warning(f"推理服务健康检查出错: {str(e)}")
            
            await asyncio.sleep(5)  # 增加等待间隔
            tries += 1
        
        # 尝试检查进程日志
        try:
            with open(log_file, 'r') as f:
                last_lines = f.readlines()[-20:]  # 获取最后20行
                log_excerpt = ''.join(last_lines)
                logger.error(f"推理服务日志摘要:\n{log_excerpt}")
        except Exception as e:
            logger.error(f"无法读取推理服务日志: {str(e)}")
        
        # 如果服务未能启动，标记为失败
        error_msg = "推理服务启动超时"
        logger.error(f"{error_msg}: 任务={task_id}")
        update_inference_task(
            task_id=task_id,
            status=InferenceStatus.FAILED,
            error_message=error_msg
        )
        
        # 尝试终止进程
        try:
            process.terminate()
        except Exception:
            pass
        
        # 从活跃进程列表中移除
        active_processes.remove(process_info)
        
        return False
        
    except Exception as e:
        error_msg = f"启动推理服务失败: {str(e)}"
        logger.error(error_msg)
        update_inference_task(
            task_id=task_id,
            status=InferenceStatus.FAILED,
            error_message=error_msg
        )
        return False

# 停止推理服务
async def stop_inference_service(task_id: int) -> bool:
    """停止推理服务"""
    task = get_inference_task(task_id=task_id)
    if not task:
        logger.error(f"找不到推理任务: {task_id}")
        return False
    
    # 查找对应的进程
    for process_info in active_processes[:]:
        if process_info["task_id"] == task_id:
            process = process_info["process"]
            
            try:
                # 尝试优雅终止
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    # 如果进程未能在5秒内终止，强制杀死
                    process.kill()
                
                logger.info(f"推理服务已停止: 任务={task_id}, PID={process.pid}")
                
                # 从活跃进程列表中移除
                active_processes.remove(process_info)
                
                # 更新任务状态
                update_inference_task(
                    task_id=task_id,
                    status=InferenceStatus.STOPPED,
                    stopped_at=datetime.now()
                )
                
                return True
            except Exception as e:
                logger.error(f"停止推理服务失败: {str(e)}")
                return False
    
    # 如果未找到进程但任务状态为运行中，更新状态
    if task.status == InferenceStatus.RUNNING:
        update_inference_task(
            task_id=task_id,
            status=InferenceStatus.STOPPED,
            stopped_at=datetime.now(),
            error_message="进程已不存在"
        )
        return True
    
    return False

# 检查推理服务状态
async def check_inference_service(task_id: int) -> Dict[str, Any]:
    """检查推理服务状态"""
    task = get_inference_task(task_id=task_id)
    if not task:
        return {"status": "not_found", "error": "推理任务不存在"}
    
    if task.status != InferenceStatus.RUNNING:
        return {"status": task.status, "task": task.dict()}
    
    # 检查进程是否在运行
    process_running = False
    for process_info in active_processes:
        if process_info["task_id"] == task_id:
            process = process_info["process"]
            if process.returncode is None:  # 进程仍在运行
                process_running = True
                break
    
    # 如果进程不在运行但状态为运行中，更新状态
    if not process_running and task.status == InferenceStatus.RUNNING:
        update_inference_task(
            task_id=task_id,
            status=InferenceStatus.FAILED,
            stopped_at=datetime.now(),
            error_message="进程意外终止"
        )
        task = get_inference_task(task_id=task_id)
    
    # 检查API是否可用
    api_available = False
    if task.port:
        try:
            response = requests.get(f"http://localhost:{task.port}/v1/models", timeout=2)
            api_available = response.status_code == 200
        except Exception:
            api_available = False
    
    return {
        "status": task.status,
        "task": task.dict(),
        "process_running": process_running,
        "api_available": api_available
    }

# 执行模型推理
async def perform_inference(
    task_id: int,
    messages: List[Dict[str, str]],
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
    max_tokens: Optional[int] = None,
    repetition_penalty: Optional[float] = None
) -> Dict[str, Any]:
    """执行模型推理"""
    logger.info(f"开始执行推理: 任务ID={task_id}, 消息数量={len(messages)}")
    
    task = get_inference_task(task_id=task_id)
    if not task:
        logger.error(f"推理任务不存在: {task_id}")
        return {"error": "推理任务不存在"}
    
    if task.status != InferenceStatus.RUNNING:
        logger.error(f"推理任务未运行: {task_id}, 当前状态={task.status}")
        return {"error": f"推理任务未运行，当前状态: {task.status}"}
    
    if not task.api_base or not task.port:
        logger.error(f"推理任务API基础URL未设置: {task_id}")
        return {"error": "推理任务API基础URL未设置"}
    
    # 准备请求参数
    final_temperature = temperature if temperature is not None else task.temperature
    final_top_p = top_p if top_p is not None else task.top_p
    final_max_tokens = max_tokens if max_tokens is not None else task.max_tokens
    final_repetition_penalty = repetition_penalty if repetition_penalty is not None else task.repetition_penalty
    
    payload = {
        "model": task.name,
        "messages": messages,
        "temperature": final_temperature,
        "top_p": final_top_p,
        "max_tokens": final_max_tokens,
        "repetition_penalty": final_repetition_penalty
    }
    
    logger.debug(f"推理参数: model={task.name}, temperature={final_temperature}, "
                f"top_p={final_top_p}, max_tokens={final_max_tokens}, "
                f"repetition_penalty={final_repetition_penalty}")
    
    # 获取最后一个用户消息（用于日志）
    last_user_msg = next((msg["content"] for msg in reversed(messages) if msg["role"] == "user"), None)
    if last_user_msg:
        logger.debug(f"最后用户消息(前50个字符): {last_user_msg[:50]}...")
    
    api_url = f"http://localhost:{task.port}/v1/chat/completions"
    logger.debug(f"发送请求到: {api_url}")
    
    try:
        start_time = time.time()
        
        # 发送请求到vLLM OpenAI兼容API
        response = requests.post(
            api_url,
            json=payload,
            timeout=60
        )
        
        request_time = time.time() - start_time
        logger.debug(f"请求处理时间: {request_time:.2f}秒")
        
        if response.status_code != 200:
            logger.error(f"推理请求失败: HTTP {response.status_code}, 响应: {response.text[:200]}")
            return {"error": f"推理请求失败: HTTP {response.status_code}", "details": response.text}
        
        # 解析响应
        result = response.json()
        
        # 提取生成的文本
        message = {
            "role": "assistant",
            "content": result["choices"][0]["message"]["content"]
        }
        
        # 记录推理结果
        content_length = len(message["content"])
        logger.info(f"推理成功: 任务ID={task_id}, 响应长度={content_length}, 处理时间={request_time:.2f}秒")
        logger.debug(f"推理响应(前50个字符): {message['content'][:50]}...")
        
        # 记录token使用情况（如果API提供）
        if "usage" in result:
            usage = result["usage"]
            logger.debug(f"Token使用情况: 输入={usage.get('prompt_tokens', 'N/A')}, "
                        f"输出={usage.get('completion_tokens', 'N/A')}, "
                        f"总计={usage.get('total_tokens', 'N/A')}")
        
        return {"message": message, "task_id": task_id}
    except Exception as e:
        logger.exception(f"执行推理失败: {str(e)}")
        return {"error": f"执行推理失败: {str(e)}"}

def cleanup_inference_files(task_id: int) -> dict:
    """清理推理任务相关的文件和目录
    
    Args:
        task_id: 推理任务ID
        
    Returns:
        包含清理结果的字典
    """
    result = {
        "success": True,
        "cleaned_files": [],
        "errors": []
    }
    
    try:
        # 清理日志文件
        log_dir = Path("logs/inference")
        if log_dir.exists():
            for log_file in log_dir.glob(f"*task_{task_id}*.log"):
                try:
                    log_file.unlink()
                    result["cleaned_files"].append(str(log_file))
                except Exception as e:
                    result["errors"].append(f"清理日志文件失败: {str(log_file)} - {str(e)}")
        
        # 清理可能的临时文件目录
        temp_dir = Path(f"temp/inference_task_{task_id}")
        if temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)
                result["cleaned_files"].append(str(temp_dir))
            except Exception as e:
                result["errors"].append(f"清理临时目录失败: {str(temp_dir)} - {str(e)}")
        
        return result
    except Exception as e:
        result["success"] = False
        result["errors"].append(f"清理过程中发生错误: {str(e)}")
        return result 