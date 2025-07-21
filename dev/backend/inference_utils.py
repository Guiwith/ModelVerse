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
def estimate_model_memory(model_id: int, tensor_parallel_size: int = 1, max_model_len: int = 4096, quantization: Optional[str] = None) -> float:
    """估计模型的显存占用（GB）- 改进版本，考虑KV cache等额外开销"""
    model = get_resource(resource_id=model_id)
    if not model:
        return 0.0
    
    # 从模型名称中提取参数规模（如果可能）
    model_name = model.name.lower()
    model_size = 0
    
    # 检查常见的命名模式（扩展更多规模）
    for scale in ["135m", "1.8b", "2.7b", "3b", "7b", "8b", "13b", "14b", "30b", "34b", "70b", "72b", "405b"]:
        if scale in model_name:
            size_str = scale.replace("b", "").replace("m", "")
            try:
                if "m" in scale:  # 百万参数
                    model_size = float(size_str) / 1000  # 转换为B
                elif "." in size_str:
                    model_size = float(size_str)
                else:
                    model_size = int(size_str)
            except ValueError:
                pass
            break
    
    # 如果无法从名称提取，尝试基于文件大小估算
    if model_size == 0 and model.size_mb:
        # 粗略估算：模型文件大小（MB）/ 1024 约等于参数规模（B）
        # 这个比例会根据精度（fp16/fp32）和量化而变化
        model_size = model.size_mb / 1024  # 转换为GB，作为参数规模的粗略估计
    
    # 基础模型权重显存占用（考虑精度）
    if model_size <= 0.2:  # ~135M-200M
        base_memory = 2.0
    elif model_size <= 2:  # ~1.8B-2B
        base_memory = 4.0  
    elif model_size <= 3:  # ~2.7B-3B
        base_memory = 6.0
    elif model_size <= 7:  # ~7B
        base_memory = 14.0
    elif model_size <= 8:  # ~8B
        base_memory = 16.0
    elif model_size <= 13:  # ~13B
        base_memory = 26.0
    elif model_size <= 14:  # ~14B
        base_memory = 28.0
    elif model_size <= 30:  # ~30B
        base_memory = 60.0
    elif model_size <= 34:  # ~34B
        base_memory = 68.0
    elif model_size <= 70:  # ~70B
        base_memory = 140.0
    elif model_size <= 405:  # ~405B
        base_memory = 800.0
    else:
        base_memory = max(8.0, model_size * 2)  # 默认估算公式
    
    # 考虑量化的影响
    if quantization:
        if quantization.lower() in ["awq", "gptq"]:
            base_memory *= 0.5  # 4-bit量化大约减少50%
        elif quantization.lower() in ["int8"]:
            base_memory *= 0.75  # 8-bit量化大约减少25%
    elif "quantization" in model_name or "int8" in model_name or "int4" in model_name or "awq" in model_name or "gptq" in model_name:
        base_memory *= 0.5
    
    # KV Cache 显存占用估算
    # KV cache 大小 ≈ 2 * num_layers * hidden_size * max_seq_len * batch_size * precision_bytes
    # 对于Transformer模型，粗略估算：
    kv_cache_factor = max_model_len / 2048  # 相对于2048基准长度的倍数
    if model_size <= 2:
        kv_cache_memory = 1.0 * kv_cache_factor
    elif model_size <= 7:
        kv_cache_memory = 2.0 * kv_cache_factor
    elif model_size <= 13:
        kv_cache_memory = 3.0 * kv_cache_factor
    elif model_size <= 30:
        kv_cache_memory = 6.0 * kv_cache_factor
    elif model_size <= 70:
        kv_cache_memory = 12.0 * kv_cache_factor
    else:
        kv_cache_memory = 20.0 * kv_cache_factor
    
    # vLLM 系统开销（缓冲区、内存池等）
    system_overhead = max(2.0, base_memory * 0.2)  # 至少2GB，或基础内存的20%
    
    # 总显存需求
    total_memory = base_memory + kv_cache_memory + system_overhead
    
    # 根据并行度调整（模型权重会分片，但KV cache和系统开销基本不变）
    if tensor_parallel_size > 1:
        total_memory = (base_memory / tensor_parallel_size) + kv_cache_memory + system_overhead
    
    logger.info(f"显存估算详情 - 模型: {model_name}, 参数规模: {model_size}B, "
                f"基础内存: {base_memory:.1f}GB, KV Cache: {kv_cache_memory:.1f}GB, "
                f"系统开销: {system_overhead:.1f}GB, 总计: {total_memory:.1f}GB")
    
    return total_memory

# 使用nvidia-smi获取实时GPU信息
def get_real_gpu_info() -> Dict[str, Any]:
    """使用nvidia-smi获取实时GPU信息"""
    try:
        # 查询GPU信息：名称、总显存、已用显存、空闲显存、GPU利用率、温度
        cmd = [
            'nvidia-smi', 
            '--query-gpu=gpu_name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu',
            '--format=csv,noheader,nounits'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode != 0:
            logger.error(f"nvidia-smi执行失败: {result.stderr}")
            return {"available": False, "error": "nvidia-smi执行失败", "gpus": []}
        
        lines = result.stdout.strip().split('\n')
        gpus = []
        total_memory = 0
        total_used = 0
        
        for i, line in enumerate(lines):
            if line.strip():
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 6:
                    gpu_name = parts[0]
                    memory_total = float(parts[1]) / 1024  # 转换为GB
                    memory_used = float(parts[2]) / 1024   # 转换为GB
                    memory_free = float(parts[3]) / 1024   # 转换为GB
                    gpu_util = parts[4]
                    temperature = parts[5]
                    
                    total_memory += memory_total
                    total_used += memory_used
                    
                    gpus.append({
                        "id": i,
                        "name": gpu_name,
                        "memory_total": memory_total,
                        "memory_used": memory_used,
                        "memory_free": memory_free,
                        "utilization": f"{gpu_util}%",
                        "temperature": f"{temperature}°C"
                    })
        
        return {
            "available": True,
            "gpus": gpus,
            "total_memory": total_memory,
            "used_memory": total_used,
            "free_memory": total_memory - total_used
        }
        
    except subprocess.TimeoutExpired:
        logger.error("nvidia-smi查询超时")
        return {"available": False, "error": "nvidia-smi查询超时", "gpus": []}
    except FileNotFoundError:
        logger.error("nvidia-smi命令未找到，可能未安装NVIDIA驱动")
        return {"available": False, "error": "nvidia-smi未找到", "gpus": []}
    except Exception as e:
        logger.error(f"获取GPU信息失败: {str(e)}")
        return {"available": False, "error": str(e), "gpus": []}

# 获取系统GPU信息（改进版本）
def get_gpu_info() -> Dict[str, Any]:
    """获取系统GPU信息 - 优先使用nvidia-smi实时查询"""
    # 首先尝试使用nvidia-smi获取实时信息
    real_gpu_info = get_real_gpu_info()
    
    if real_gpu_info["available"]:
        # 添加任务信息到实时GPU信息中
        for gpu in real_gpu_info["gpus"]:
            # 计算该GPU上运行的任务
            tasks_on_gpu = [p for p in active_processes if p.get("gpu_device") == gpu["id"]]
            gpu["running_tasks"] = len(tasks_on_gpu)
            gpu["task_details"] = [
                {
                    "task_id": p["task_id"],
                    "estimated_memory": p.get("gpu_memory", 0),
                    "command": p["command"][:100] + "..." if len(p["command"]) > 100 else p["command"]
                }
                for p in tasks_on_gpu
            ]
        
        # 计算建议的最大并发任务数（基于实际空闲显存）
        min_task_memory = 8.0  # 假设最小任务需要8GB
        max_concurrent_tasks = max(1, int(real_gpu_info["free_memory"] / min_task_memory))
        real_gpu_info["max_concurrent_tasks"] = max_concurrent_tasks
        
        return real_gpu_info
    
    # 如果nvidia-smi不可用，回退到torch方法
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
            
            # 尝试获取当前设备的实际显存使用情况
            try:
                torch.cuda.set_device(i)
                memory_allocated = torch.cuda.memory_allocated(i) / (1024 ** 3)
                memory_reserved = torch.cuda.memory_reserved(i) / (1024 ** 3)
                actual_used = max(memory_allocated, memory_reserved)
            except Exception:
                # 如果无法获取实际使用情况，使用估算
                actual_used = sum([p.get("gpu_memory", 0) for p in active_processes if p.get("gpu_device") == i])
            
            gpus.append({
                "id": i,
                "name": torch.cuda.get_device_name(i),
                "memory_total": gpu_memory,
                "memory_used": actual_used,
                "memory_free": gpu_memory - actual_used,
                "running_tasks": len([p for p in active_processes if p.get("gpu_device") == i])
            })
            
            used_memory += actual_used
        
        return {
            "available": True,
            "gpus": gpus,
            "total_memory": total_memory,
            "used_memory": used_memory,
            "free_memory": total_memory - used_memory,
            "max_concurrent_tasks": max(1, int((total_memory - used_memory) / 10))
        }
    except Exception as e:
        logger.error(f"获取GPU信息失败: {str(e)}")
        return {"available": False, "error": str(e), "gpus": [], "total_memory": 0, "used_memory": 0, "free_memory": 0}

# 检查GPU资源是否足够启动新任务
def check_gpu_resources_for_task(model_id: int, tensor_parallel_size: int = 1, max_model_len: int = 4096, quantization: Optional[str] = None) -> Dict[str, Any]:
    """检查GPU资源是否足够启动新任务"""
    # 获取实时GPU信息
    gpu_info = get_gpu_info()
    
    if not gpu_info["available"]:
        return {
            "sufficient": False,
            "reason": "没有可用的GPU",
            "gpu_info": gpu_info
        }
    
    # 估算新任务的显存需求
    estimated_memory = estimate_model_memory(
        model_id=model_id,
        tensor_parallel_size=tensor_parallel_size,
        max_model_len=max_model_len,
        quantization=quantization
    )
    
    # 检查是否有足够的空闲显存
    if estimated_memory > gpu_info["free_memory"]:
        return {
            "sufficient": False,
            "reason": f"显存不足: 需要 {estimated_memory:.1f}GB, 实际空闲 {gpu_info['free_memory']:.1f}GB",
            "required_memory": estimated_memory,
            "available_memory": gpu_info["free_memory"],
            "gpu_info": gpu_info
        }
    
    # 添加安全余量检查（保留10%的显存作为缓冲）
    safety_margin = gpu_info["total_memory"] * 0.1
    effective_available = gpu_info["free_memory"] - safety_margin
    
    if estimated_memory > effective_available:
        return {
            "sufficient": False,
            "reason": f"显存不足（含安全余量）: 需要 {estimated_memory:.1f}GB, 有效可用 {effective_available:.1f}GB",
            "required_memory": estimated_memory,
            "available_memory": gpu_info["free_memory"],
            "effective_available": effective_available,
            "safety_margin": safety_margin,
            "gpu_info": gpu_info
        }
    
    return {
        "sufficient": True,
        "required_memory": estimated_memory,
        "available_memory": gpu_info["free_memory"],
        "gpu_info": gpu_info
    }

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
        "--trust-remote-code",  # 信任远程代码，提高兼容性
        "--enforce-eager",  # 禁用torch.compile以加快启动速度
        "--gpu-memory-utilization", "0.85",  # 降低GPU内存使用率，提高稳定性
        "--max-num-batched-tokens", "4096",  # 限制批处理token数量
        "--disable-log-stats"  # 禁用统计日志
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
            "gpu_memory": estimate_model_memory(
                model_id=task.model_id, 
                tensor_parallel_size=task.tensor_parallel_size,
                max_model_len=task.max_model_len,
                quantization=task.quantization
            ),
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
        await asyncio.sleep(15)  # 增加到10秒，给模型加载更多时间
        
        # 检查服务是否成功启动
        tries = 0
        max_tries = 40  # 增加到40次，总共约210秒超时
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
                response = requests.get(f"http://localhost:{used_port}/v1/models", timeout=10)  # 增加单次请求超时
                if response.status_code == 200:
                    logger.info(f"推理服务准备就绪: 任务={task_id}, 端口={used_port}, 响应={response.text[:100]}")
                    return True
                else:
                    logger.warning(f"推理服务健康检查返回非200状态码: {response.status_code}, 响应: {response.text[:100]}")
            except requests.exceptions.RequestException as e:
                logger.warning(f"推理服务健康检查连接失败: {str(e)}")
            except Exception as e:
                logger.warning(f"推理服务健康检查出错: {str(e)}")
            
            # 根据尝试次数调整等待时间
            if tries < 10:
                wait_time = 3  # 前10次等待3秒
            elif tries < 20:
                wait_time = 5  # 中间10次等待5秒
            else:
                wait_time = 10  # 后面等待10秒
                
            await asyncio.sleep(wait_time)
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