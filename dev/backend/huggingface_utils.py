"""
用于从 Hugging Face Hub 下载模型和数据集的工具
特别适配huggingface_hub版本0.30.x，支持所有平台
默认使用中国镜像站hf-mirror.com加速下载
"""

import os
import threading
import time
import logging
import tempfile
import platform
import importlib.metadata
import subprocess
import json
import shutil
from typing import Dict, Optional, Any, Tuple
import re
from urllib.parse import urlparse

# 设置镜像站配置 - 统一使用hf-mirror.com作为镜像站
mirror_url = "https://hf-mirror.com"

# 强制设置环境变量
os.environ["HF_ENDPOINT"] = mirror_url
os.environ["HF_MIRROR"] = mirror_url  # 兼容某些旧版本

# 禁用hf_transfer，它可能会绕过镜像站
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"

# 打印当前huggingface_hub版本
hf_version = importlib.metadata.version("huggingface_hub")
print(f"当前huggingface_hub版本: {hf_version}")

# 设置huggingface缓存目录
cache_home = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hf_cache")
os.environ["HF_HOME"] = cache_home
os.environ["HUGGINGFACE_HUB_CACHE"] = os.path.join(cache_home, "hub")
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"

# 为Unix系统设置临时目录
if platform.system() != "Windows":
    os.environ["TMPDIR"] = os.path.join(cache_home, "tmp")
    
# 确保所有缓存目录存在
os.makedirs(os.environ["HUGGINGFACE_HUB_CACHE"], exist_ok=True)
if platform.system() != "Windows":
    os.makedirs(os.environ["TMPDIR"], exist_ok=True)

# 启用详细日志记录
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("huggingface_utils")

# 记录当前使用的镜像站
logger.info(f"当前使用的HuggingFace镜像站: {mirror_url}")

# 导入huggingface_hub并配置镜像站
from huggingface_hub import hf_hub_download, snapshot_download, HfApi

# 强制使用镜像站(在库导入后)
try:
   
    logger.info(f"使用环境变量配置镜像站: {mirror_url}")
except (ImportError, AttributeError):
    logger.warning("无法配置镜像站，将依赖环境变量")


try:
    import huggingface_hub.constants as hf_constants
    # 保存原始值用于日志
    original_endpoint = getattr(hf_constants, "ENDPOINT", "unknown")
    # 设置新的端点
    if hasattr(hf_constants, "ENDPOINT"):
        setattr(hf_constants, "ENDPOINT", mirror_url)
        logger.info(f"已修改huggingface_hub.constants.ENDPOINT: {original_endpoint} -> {mirror_url}")
    
    # 检查其他可能的URL常量
    for attr_name in dir(hf_constants):
        if attr_name.endswith("_URL") or "ENDPOINT" in attr_name:
            attr_value = getattr(hf_constants, attr_name, None)
            if attr_value and isinstance(attr_value, str) and "huggingface.co" in attr_value:
                new_value = attr_value.replace("huggingface.co", mirror_url.replace("https://", ""))
                setattr(hf_constants, attr_name, new_value)
                logger.info(f"已修改huggingface_hub常量 {attr_name}: {attr_value} -> {new_value}")
except Exception as e:
    logger.warning(f"修改huggingface_hub常量时出错: {str(e)}")

from models import Resource, DownloadStatus, MirrorSource, ResourceType
from database import update_resource_status, get_resource

# 下载线程管理
_active_downloads: Dict[int, Dict[str, Any]] = {}
_download_threads: Dict[int, threading.Thread] = {}
_stop_events: Dict[int, threading.Event] = {}

# 镜像源配置
MIRRORS = {
    MirrorSource.OFFICIAL: mirror_url,  # 改为默认使用镜像站
    MirrorSource.MODELSCOPE: "https://modelscope.cn/huggingface",  
    MirrorSource.MIRROR_CN: mirror_url
}

# 本地存储配置
DEFAULT_MODEL_DIR = os.environ.get("MODEL_DIR", "./models")
DEFAULT_DATASET_DIR = os.environ.get("DATASET_DIR", "./datasets")

# 默认使用中国镜像站
DEFAULT_MIRROR_SOURCE = MirrorSource.MIRROR_CN

def _get_save_dir(resource: Resource) -> str:
    """根据资源类型获取保存目录"""
    base_dir = DEFAULT_MODEL_DIR if resource.resource_type == ResourceType.MODEL else DEFAULT_DATASET_DIR
    # 确保目录存在
    os.makedirs(base_dir, exist_ok=True)
    return os.path.join(base_dir, resource.repo_id.replace("/", "_"))

def download_with_cli(repo_id: str, repo_type: str, save_dir: str, mirror_url: str) -> bool:
    """使用命令行工具下载资源（备选方法）"""
    try:
        logger.info(f"尝试使用命令行方式下载 {repo_id}")
        
        # 确保目录存在
        os.makedirs(save_dir, exist_ok=True)
        
        # 尝试使用Python代码直接下载单个文件
        try:
            logger.info(f"尝试直接下载文件列表")
            # 获取文件列表
            api = HfApi(endpoint=mirror_url)
            
            # 获取仓库文件列表
            if repo_type == "model":
                repo_info = api.model_info(repo_id=repo_id)
            else:
                repo_info = api.dataset_info(repo_id=repo_id)
                
            # 获取文件列表
            files = repo_info.siblings
            logger.info(f"仓库 {repo_id} 包含 {len(files)} 个文件")
            
            # 下载每个文件
            for idx, file_info in enumerate(files):
                if file_info.rfilename.startswith('.'):
                    continue
                    
                file_save_path = os.path.join(save_dir, file_info.rfilename)
                # 确保目录存在
                os.makedirs(os.path.dirname(file_save_path), exist_ok=True)
                
                logger.info(f"下载文件 ({idx+1}/{len(files)}): {file_info.rfilename}")
                try:
                    hf_hub_download(
                        repo_id=repo_id,
                        filename=file_info.rfilename,
                        repo_type=repo_type,
                        local_dir=save_dir,
                        local_dir_use_symlinks=False,
                        resume_download=True,
                        endpoint=mirror_url
                    )
                except Exception as e:
                    logger.warning(f"下载文件 {file_info.rfilename} 失败: {str(e)}")
            
            # 检查是否下载了文件
            downloaded_files = [f for f in os.listdir(save_dir) if not f.startswith('.')]
            if downloaded_files:
                logger.info(f"成功下载 {len(downloaded_files)} 个文件到 {save_dir}")
                return True
            else:
                logger.warning(f"没有文件被下载到 {save_dir}")
                
        except Exception as e:
            logger.warning(f"直接下载文件列表失败: {str(e)}")
        
        # 尝试使用huggingface-cli命令
        try:
            logger.info("尝试使用huggingface-cli命令")
            # 确保设置了环境变量
            env = dict(os.environ)
            env["HF_ENDPOINT"] = mirror_url
            
            cmd = [
                "huggingface-cli", "download",
                repo_id,
                "--repo-type", repo_type,
                "--local-dir", save_dir,
                "--local-dir-use-symlinks", "False"
            ]
            
            logger.info(f"执行命令: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                env=env
            )
            
            if result.returncode == 0:
                logger.info(f"huggingface-cli下载成功: {repo_id}")
                return True
            else:
                logger.warning(f"huggingface-cli下载失败: {result.stderr}")
        except Exception as e:
            logger.warning(f"huggingface-cli命令执行失败: {str(e)}")
        
        # 最后尝试直接使用curl或wget下载
        try:
            logger.info("尝试使用系统命令(wget/curl)直接下载")
            
            # 构建镜像API URL，使用镜像站
            base_url = mirror_url.rstrip('/')
            if repo_type == "dataset":
                api_url = f"{base_url}/datasets/{repo_id}/resolve/main/data/train.json"
            else:
                api_url = f"{base_url}/models/{repo_id}/resolve/main/config.json"
            
            logger.info(f"下载URL: {api_url}")
            
            # 检测系统中是否有wget或curl
            wget_available = shutil.which("wget") is not None
            curl_available = shutil.which("curl") is not None
            
            if wget_available:
                cmd = ["wget", "-P", save_dir, api_url]
            elif curl_available:
                cmd = ["curl", "-o", os.path.join(save_dir, "download.json"), api_url]
            else:
                logger.warning("系统中没有找到wget或curl命令")
                return False
            
            logger.info(f"执行命令: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                logger.info(f"使用{cmd[0]}下载成功")
                return True
            else:
                logger.warning(f"{cmd[0]}下载失败: {result.stderr}")
                return False
        except Exception as e:
            logger.warning(f"系统命令下载失败: {str(e)}")
            
        return False
            
    except Exception as e:
        logger.error(f"命令行下载出错: {str(e)}")
        return False

def download_with_git(repo_id: str, repo_type: str, save_dir: str, mirror_url: str) -> bool:
    """使用Git克隆方式下载（适用于Ubuntu环境）"""
    try:
        logger.info(f"尝试使用Git克隆仓库 {repo_id}")
        
        # 检查git命令是否可用
        git_available = shutil.which("git") is not None
        if not git_available:
            logger.warning("系统中未找到git命令")
            return False
            
        # 从mirror_url中提取域名部分
        mirror_domain = urlparse(mirror_url).netloc
        if not mirror_domain:
            mirror_domain = mirror_url.replace("https://", "").replace("http://", "").split('/')[0]
            
        # 构建git URL - 使用镜像站
        git_url = f"https://{mirror_domain}/{repo_id}"
            
        logger.info(f"使用Git URL: {git_url}")
            
        # 清空目标目录
        if os.path.exists(save_dir):
            try:
                shutil.rmtree(save_dir)
            except Exception as e:
                logger.warning(f"清空目录失败，尝试直接克隆: {str(e)}")
                
        # 确保父目录存在
        parent_dir = os.path.dirname(save_dir)
        os.makedirs(parent_dir, exist_ok=True)
            
        # 执行git clone命令
        cmd = ["git", "clone", git_url, save_dir]
        logger.info(f"执行命令: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            logger.info(f"Git克隆成功: {repo_id}")
            return True
        else:
            logger.warning(f"Git克隆失败: {result.stderr}")
            
            # 尝试通过镜像站单独获取一些文件
            try:
                # 检查是否有参考下载URL
                if repo_type == "model":
                    # 模型通常有config.json
                    ref_file = "config.json"
                else:
                    # 数据集通常有dataset_infos.json
                    ref_file = "dataset_infos.json"
                    
                # 使用镜像站URL构建下载链接
                url = f"{mirror_url}/{repo_type}s/{repo_id}/resolve/main/{ref_file}"
                logger.info(f"尝试单独下载文件: {url}")
                
                download_cmd = ["wget", "-P", save_dir, url]
                
                logger.info(f"执行命令: {' '.join(download_cmd)}")
                dl_result = subprocess.run(
                    download_cmd,
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if dl_result.returncode == 0:
                    logger.info(f"成功下载参考文件: {ref_file}")
                    return True
            except Exception as e:
                logger.warning(f"单独下载文件失败: {str(e)}")
                
            return False
    except Exception as e:
        logger.error(f"Git克隆下载失败: {str(e)}")
        return False

def check_cached_download(result_dir, output, download_completed):
    """检查是否使用了本地缓存并验证有效性"""
    if "existing local_dir" in output or "Cannot access" in output:
        logger.info(f"使用了本地缓存: {output}")
        
        # 检查目录中的文件
        if os.path.exists(result_dir):
            files = [f for f in os.listdir(result_dir) if not f.startswith('.')]
            if files:
                logger.info(f"本地缓存目录包含 {len(files)} 个文件")
                # 标记下载已完成
                download_completed.set()
                return True
    return False

def safe_snapshot_download(repo_id, repo_type, save_dir, mirror_url, max_workers=1, download_completed=None):
    """安全地执行snapshot_download，同时检查是否使用了本地缓存"""
    # 导入必要的模块
    import io
    import sys
    from huggingface_hub import snapshot_download
    
    # 确保设置了环境变量
    os.environ["HF_ENDPOINT"] = mirror_url
    
    # 显示调试信息
    logger.info(f"调用snapshot_download: repo_id={repo_id}, endpoint={mirror_url}")
    logger.info(f"当前环境变量: HF_ENDPOINT={os.environ.get('HF_ENDPOINT')}")
    
    # 保存原始stdout以便恢复
    original_stdout = sys.stdout
    captured_output = io.StringIO()
    sys.stdout = captured_output
    
    try:
        # 强制使用镜像站
        result_dir = snapshot_download(
            repo_id=repo_id,
            repo_type=repo_type,
            local_dir=save_dir,
            local_dir_use_symlinks=False,
            resume_download=True,
            endpoint=mirror_url,  # 显式指定端点，不依赖环境变量
            max_workers=max_workers,
            etag_timeout=60,
            tqdm_class=None
        )
        
        # 恢复stdout
        sys.stdout = original_stdout
        output = captured_output.getvalue()
        
        # 记录输出以便调试
        if output:
            logger.info(f"snapshot_download输出: {output}")
        
        # 验证下载内容
        if os.path.exists(result_dir):
            files = [f for f in os.listdir(result_dir) if not f.startswith('.')]
            logger.info(f"下载目录 {result_dir} 包含 {len(files)} 个文件")
            
            # 如果有文件，可能是下载成功或使用了缓存
            if files and download_completed:
                logger.info(f"标记下载完成")
                download_completed.set()
        
        return result_dir
        
    except Exception as e:
        # 恢复stdout
        sys.stdout = original_stdout
        output = captured_output.getvalue()
        
        # 记录错误以便调试
        logger.error(f"snapshot_download错误: {str(e)}")
        if output:
            logger.info(f"snapshot_download错误输出: {output}")
        
        # 即使出错，也检查是否使用了本地缓存
        if "existing local_dir" in output:
            dir_match = re.search(r"existing local_dir `([^`]+)`", output)
            if dir_match:
                result_dir = dir_match.group(1)
                logger.info(f"检测到使用本地缓存: {result_dir}")
                
                # 验证缓存目录
                if os.path.exists(result_dir):
                    files = [f for f in os.listdir(result_dir) if not f.startswith('.')]
                    logger.info(f"缓存目录 {result_dir} 包含 {len(files)} 个文件")
                    
                    # 如果有文件，标记为完成
                    if files and download_completed:
                        logger.info(f"尽管有错误，但使用了有效缓存，标记下载完成")
                        download_completed.set()
                        return result_dir
        
        # 将错误往上传递
        raise e

def _download_worker(resource_id: int, resource: Resource, source: MirrorSource, stop_event: threading.Event):
    """后台下载工作线程"""
    try:
        # 获取镜像URL
        mirror_url = MIRRORS.get(source, MIRRORS[DEFAULT_MIRROR_SOURCE])
        save_dir = _get_save_dir(resource)
        
        # 强制设置环境变量
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
        logger.info(f"设置环境变量HF_ENDPOINT={mirror_url}")
        
        # 开始下载
        logger.info(f"开始下载资源: {resource.repo_id} 到 {save_dir}, 使用镜像站: {mirror_url}")
        
        # 初始化进度数据
        _active_downloads[resource_id] = {
            "progress": 0.0,
            "status": "downloading",
            "error": None
        }
        
        # 更新数据库中的状态
        update_resource_status(
            resource_id=resource_id, 
            status=DownloadStatus.DOWNLOADING,
            progress=0.0
        )
        
        # 创建下载完成事件
        download_completed = threading.Event()
        
        # 创建一个线程来检查下载进度
        def check_download_progress():
            """检查下载目录变化来监控实际下载进度"""
            last_size = 0
            last_count = 0
            unchanged_count = 0
            max_unchanged_checks = 10  # 如果连续10次（50秒）没有变化则考虑完成
            
            while not stop_event.is_set() and not download_completed.is_set():
                time.sleep(5)  # 每5秒检查一次
                
                # 检查目录是否存在及其内容
                try:
                    if os.path.exists(save_dir):
                        # 计算目录大小
                        total_size = 0
                        file_count = 0
                        
                        for dirpath, _, filenames in os.walk(save_dir):
                            for filename in filenames:
                                if filename.startswith('.'):
                                    continue
                                file_path = os.path.join(dirpath, filename)
                                if os.path.exists(file_path):
                                    total_size += os.path.getsize(file_path)
                                    file_count += 1
                        
                        # 检查文件变化以判断下载进度
                        if file_count > 0:
                            size_mb = total_size / (1024 * 1024)
                            
                            # 如果文件大小相同，可能下载停滞
                            if total_size == last_size and file_count == last_count:
                                unchanged_count += 1
                                if unchanged_count >= 6:  # 30秒无变化
                                    logger.warning(f"下载可能卡住，30秒内未检测到文件变化: {size_mb:.2f} MB, {file_count} 个文件")
                                
                                # 检测长时间无变化 - 超过max_unchanged_checks次检查
                                if unchanged_count >= max_unchanged_checks:
                                    # 检查是否有典型数据集或模型文件
                                    has_valid_files = False
                                    model_files = ['config.json', 'pytorch_model.bin', 'model.safetensors', 'tokenizer.json']
                                    dataset_files = ['dataset_info.json', 'train.json', 'data.json', 'dataset_dict.json']
                                    
                                    all_files = []
                                    for dirpath, _, filenames in os.walk(save_dir):
                                        all_files.extend([os.path.join(dirpath, f) for f in filenames])
                                    
                                    # 检查是否包含典型文件
                                    for f in model_files + dataset_files:
                                        for path in all_files:
                                            if path.endswith(f):
                                                has_valid_files = True
                                                break
                                            
                                    # 如果文件大小不为零且包含有效文件，认为下载已完成
                                    if total_size > 0 and (has_valid_files or file_count >= 2):
                                        logger.info(f"长时间无变化且目录中有有效文件，认为下载已完成: {size_mb:.2f} MB, {file_count} 个文件")
                                        download_completed.set()  # 设置下载完成标志
                                        return
                            else:
                                unchanged_count = 0
                                
                            # 更新上次大小
                            last_size = total_size
                            last_count = file_count
                            
                            logger.info(f"下载进度检查: {size_mb:.2f} MB, {file_count} 个文件")
                            
                            # 进度设置为0.5 - 表示正在下载中但尚未完成
                            if _active_downloads[resource_id]["progress"] < 0.5:
                                _active_downloads[resource_id]["progress"] = 0.5
                                update_resource_status(
                                    resource_id=resource_id,
                                    status=DownloadStatus.DOWNLOADING,
                                    progress=0.5
                                )
                except Exception as e:
                    logger.warning(f"检查下载进度时出错: {str(e)}")
        
        # 启动进度检查线程
        progress_thread = threading.Thread(target=check_download_progress)
        progress_thread.daemon = True
        progress_thread.start()
        
        # 检查停止事件
        if stop_event.is_set():
            raise Exception("下载被用户中止")
            
        try:
            # 根据资源类型选择下载方法
            if resource.resource_type == ResourceType.MODEL:
                # 获取模型快照（下载整个仓库）
                try:
                    # 首先尝试使用命令行方式下载
                    logger.info(f"首先尝试使用命令行方式下载模型 {resource.repo_id}")
                    if download_with_cli(
                        repo_id=resource.repo_id,
                        repo_type="model",
                        save_dir=save_dir,
                        mirror_url=mirror_url
                    ):
                        logger.info("命令行下载成功")
                    else:
                        # 命令行下载失败，尝试使用API方式
                        logger.warning("命令行下载失败，尝试API方式下载")
                        
                        # 使用huggingface_hub直接下载
                        logger.info(f"使用huggingface_hub {importlib.metadata.version('huggingface_hub')} 版本下载模型")
                        
                        # 确保目录存在
                        os.makedirs(save_dir, exist_ok=True)
                        
                        try:
                            # 尝试直接下载文件列表
                            api = HfApi(endpoint=mirror_url)
                            repo_info = api.model_info(repo_id=resource.repo_id)
                            
                            # 检查是否能获取文件列表
                            if hasattr(repo_info, 'siblings') and repo_info.siblings:
                                logger.info(f"仓库包含 {len(repo_info.siblings)} 个文件，尝试单独下载")
                                
                                for idx, file_info in enumerate(repo_info.siblings):
                                    if file_info.rfilename.startswith('.'):
                                        continue
                                    
                                    file_path = os.path.join(save_dir, file_info.rfilename)
                                    dir_path = os.path.dirname(file_path)
                                    if not os.path.exists(dir_path):
                                        os.makedirs(dir_path, exist_ok=True)
                                    
                                    # 发送文件下载进度信息
                                    try:
                                        from training_utils import broadcast_resource_update
                                        import asyncio
                                        
                                        progress_data = {
                                            "type": "resource_file_progress",
                                            "resource_id": resource_id,
                                            "file_name": file_info.rfilename,
                                            "file_index": idx + 1,
                                            "total_files": len(repo_info.siblings),
                                            "status": "DOWNLOADING"
                                        }
                                        
                                        # 异步发送WebSocket消息
                                        asyncio.run(broadcast_resource_update(progress_data))
                                        logger.info(f"已发送文件下载进度: {idx+1}/{len(repo_info.siblings)}, 文件: {file_info.rfilename}")
                                    except Exception as e:
                                        logger.error(f"发送下载进度失败: {str(e)}")
                                    
                                    logger.info(f"下载文件 ({idx+1}/{len(repo_info.siblings)}): {file_info.rfilename}")
                                    hf_hub_download(
                                        repo_id=resource.repo_id,
                                        filename=file_info.rfilename,
                                        repo_type="model",
                                        local_dir=save_dir,
                                        local_dir_use_symlinks=False,
                                        resume_download=True,
                                        endpoint=mirror_url
                                    )
                                
                                logger.info(f"已完成所有文件的下载")
                            else:
                                # 使用snapshot_download方式下载
                                logger.info("使用snapshot_download下载整个仓库")
                                try:
                                    result_dir = safe_snapshot_download(
                                        repo_id=resource.repo_id,
                                        repo_type="model",
                                        save_dir=save_dir,
                                        mirror_url=mirror_url,
                                        max_workers=1,  # 减少工作线程数
                                        download_completed=download_completed
                                    )
                                except Exception as e:
                                    logger.error(f"snapshot_download失败: {str(e)}")
                                    # 尝试标准方式
                                    from huggingface_hub import snapshot_download
                                    snapshot_download(
                                        repo_id=resource.repo_id,
                                        repo_type="model",
                                        local_dir=save_dir,
                                        local_dir_use_symlinks=False,
                                        resume_download=True,
                                        endpoint=mirror_url,
                                        max_workers=4,
                                        etag_timeout=60,
                                        tqdm_class=None
                                    )
                        except Exception as api_error:
                            # API下载失败，尝试Git克隆
                            logger.error(f"API下载失败: {str(api_error)}，尝试Git克隆")
                            
                            if download_with_git(
                                repo_id=resource.repo_id,
                                repo_type="model",
                                save_dir=save_dir,
                                mirror_url=mirror_url
                            ):
                                logger.info("使用Git克隆成功下载")
                            else:
                                logger.error("所有下载尝试均失败")
                                raise api_error
                    
                except Exception as e:
                    logger.error(f"下载过程中出错: {str(e)}")
                    raise e
                    
            else:  # DATASET
                # 获取数据集快照
                try:
                    # 首先尝试使用命令行方式下载
                    logger.info(f"首先尝试使用命令行方式下载数据集 {resource.repo_id}")
                    if download_with_cli(
                        repo_id=resource.repo_id,
                        repo_type="dataset",
                        save_dir=save_dir,
                        mirror_url=mirror_url
                    ):
                        logger.info("命令行下载成功")
                    else:
                        # 命令行下载失败，尝试使用API方式
                        logger.warning("命令行下载失败，尝试API方式下载")
                        
                        # 使用huggingface_hub直接下载
                        logger.info(f"使用huggingface_hub {importlib.metadata.version('huggingface_hub')} 版本下载数据集")
                        
                        # 确保目录存在
                        os.makedirs(save_dir, exist_ok=True)
                        
                        try:
                            # 尝试直接下载文件列表
                            api = HfApi(endpoint=mirror_url)
                            repo_info = api.dataset_info(repo_id=resource.repo_id)
                            
                            # 检查是否能获取文件列表
                            if hasattr(repo_info, 'siblings') and repo_info.siblings:
                                logger.info(f"仓库包含 {len(repo_info.siblings)} 个文件，尝试单独下载")
                                
                                for idx, file_info in enumerate(repo_info.siblings):
                                    if file_info.rfilename.startswith('.'):
                                        continue
                                    
                                    file_path = os.path.join(save_dir, file_info.rfilename)
                                    dir_path = os.path.dirname(file_path)
                                    if not os.path.exists(dir_path):
                                        os.makedirs(dir_path, exist_ok=True)
                                    
                                    # 发送文件下载进度信息
                                    try:
                                        from training_utils import broadcast_resource_update
                                        import asyncio
                                        
                                        progress_data = {
                                            "type": "resource_file_progress",
                                            "resource_id": resource_id,
                                            "file_name": file_info.rfilename,
                                            "file_index": idx + 1,
                                            "total_files": len(repo_info.siblings),
                                            "status": "DOWNLOADING"
                                        }
                                        
                                        # 异步发送WebSocket消息
                                        asyncio.run(broadcast_resource_update(progress_data))
                                        logger.info(f"已发送文件下载进度: {idx+1}/{len(repo_info.siblings)}, 文件: {file_info.rfilename}")
                                    except Exception as e:
                                        logger.error(f"发送下载进度失败: {str(e)}")
                                    
                                    logger.info(f"下载文件 ({idx+1}/{len(repo_info.siblings)}): {file_info.rfilename}")
                                    hf_hub_download(
                                        repo_id=resource.repo_id,
                                        filename=file_info.rfilename,
                                        repo_type="dataset",
                                        local_dir=save_dir,
                                        local_dir_use_symlinks=False,
                                        resume_download=True,
                                        endpoint=mirror_url
                                    )
                                
                                logger.info(f"已完成所有文件的下载")
                            else:
                                # 使用snapshot_download方式下载
                                logger.info("使用snapshot_download下载整个仓库")
                                try:
                                    result_dir = safe_snapshot_download(
                                        repo_id=resource.repo_id,
                                        repo_type="dataset",
                                        save_dir=save_dir,
                                        mirror_url=mirror_url,
                                        max_workers=1,  # 减少工作线程数
                                        download_completed=download_completed
                                    )
                                except Exception as e:
                                    logger.error(f"snapshot_download失败: {str(e)}")
                                    # 尝试标准方式
                                    from huggingface_hub import snapshot_download
                                    snapshot_download(
                                        repo_id=resource.repo_id,
                                        repo_type="dataset",
                                        local_dir=save_dir,
                                        local_dir_use_symlinks=False,
                                        resume_download=True,
                                        endpoint=mirror_url,
                                        max_workers=4,
                                        etag_timeout=60,
                                        tqdm_class=None
                                    )
                        except Exception as api_error:
                            # API下载失败，尝试Git克隆
                            logger.error(f"API下载失败: {str(api_error)}，尝试Git克隆")
                            
                            if download_with_git(
                                repo_id=resource.repo_id,
                                repo_type="dataset",
                                save_dir=save_dir,
                                mirror_url=mirror_url
                            ):
                                logger.info("使用Git克隆成功下载")
                            else:
                                logger.error("所有下载尝试均失败")
                                raise api_error
                    
                except Exception as e:
                    logger.error(f"下载过程中出错: {str(e)}")
                    raise e
            
            # 检查下载结果
            if os.path.exists(save_dir):
                files = [f for f in os.listdir(save_dir) if not f.startswith('.')]
                if len(files) > 0:
                    logger.info(f"下载完成，目录 {save_dir} 中有 {len(files)} 个文件")
                else:
                    raise Exception(f"下载可能失败: 目录 {save_dir} 不包含任何文件")
            else:
                raise Exception(f"下载失败: 目录 {save_dir} 不存在")
                
        except Exception as download_error:
            logger.error(f"下载过程中出错: {str(download_error)}")
            # 设置下载完成事件，停止进度检查线程
            download_completed.set()
            raise download_error
            
        # 设置下载完成事件，停止进度检查线程
        download_completed.set()
        
        # 等待进度线程结束 (最多等待1秒)
        if progress_thread and progress_thread.is_alive():
            progress_thread.join(timeout=1.0)
            
        # 下载完成，更新状态
        if not stop_event.is_set():
            # 确保最终进度为100%
            _active_downloads[resource_id]["progress"] = 1.0
            update_resource_status(
                resource_id=resource_id,
                status=DownloadStatus.COMPLETED,
                progress=1.0,
                local_path=save_dir
            )
            _active_downloads[resource_id]["status"] = "completed"
            logger.info(f"资源下载完成: {resource.repo_id}")
        
    except Exception as e:
        # 下载出错
        if stop_event.is_set():
            error_msg = "下载被用户中止"
            status = DownloadStatus.CANCELLED
        else:
            error_msg = str(e)
            status = DownloadStatus.FAILED
        
        _active_downloads[resource_id]["status"] = "error"
        _active_downloads[resource_id]["error"] = error_msg
        
        # 更新数据库中的状态
        update_resource_status(
            resource_id=resource_id,
            status=status,
            progress=_active_downloads[resource_id].get("progress", 0),
            error_message=error_msg
        )
        logger.error(f"下载失败: {resource.repo_id} - {error_msg}")
        
        # 确保下载完成事件被设置
        try:
            if 'download_completed' in locals():
                download_completed.set()
        except:
            pass
    
    finally:
        # 清理下载线程数据
        if resource_id in _download_threads:
            del _download_threads[resource_id]
        if resource_id in _stop_events:
            del _stop_events[resource_id]

def start_download(resource: Resource, source: MirrorSource = DEFAULT_MIRROR_SOURCE) -> bool:
    """开始下载资源"""
    resource_id = resource.id
    
    # 检查资源是否已经在下载
    if resource_id in _download_threads and _download_threads[resource_id].is_alive():
        return False
    
    # 创建停止事件
    stop_event = threading.Event()
    _stop_events[resource_id] = stop_event
    
    # 创建并启动下载线程
    thread = threading.Thread(
        target=_download_worker,
        args=(resource_id, resource, source, stop_event),
        daemon=True
    )
    _download_threads[resource_id] = thread
    thread.start()
    
    return True

def stop_download(resource_id: int) -> bool:
    """停止资源下载"""
    # 检查资源是否在下载中
    if resource_id not in _stop_events or resource_id not in _download_threads:
        return False
    
    # 设置停止事件
    _stop_events[resource_id].set()
    
    # 等待线程完成（最多等待5秒）
    _download_threads[resource_id].join(timeout=5.0)
    
    # 更新资源状态为已取消
    update_resource_status(
        resource_id=resource_id,
        status=DownloadStatus.CANCELLED,
        progress=_active_downloads.get(resource_id, {}).get("progress", 0),
        error_message="下载被用户取消"
    )
    
    # 清理下载数据
    if resource_id in _active_downloads:
        del _active_downloads[resource_id]
    if resource_id in _download_threads:
        del _download_threads[resource_id]
    if resource_id in _stop_events:
        del _stop_events[resource_id]
    
    return True

def get_active_downloads() -> Dict[int, float]:
    """获取当前活跃的下载及其进度"""
    # 清理已完成但未清理的下载
    for resource_id in list(_active_downloads.keys()):
        if resource_id not in _download_threads:
            del _active_downloads[resource_id]
    
    # 返回活跃下载的ID和进度
    return {
        rid: data["progress"] 
        for rid, data in _active_downloads.items()
        if data["status"] == "downloading"
    }

def get_download_progress(resource_id: int) -> Optional[float]:
    """获取特定资源的下载进度"""
    if resource_id in _active_downloads:
        return _active_downloads[resource_id]["progress"]
    return None

def search_resources(query: str, resource_type: Optional[ResourceType] = None) -> list:
    """在Hugging Face Hub上搜索资源"""
    try:
        api = HfApi(endpoint=MIRRORS[DEFAULT_MIRROR_SOURCE])
        
        # 根据资源类型选择搜索类型
        if resource_type == ResourceType.MODEL:
            results = api.list_models(search=query, limit=20)
        elif resource_type == ResourceType.DATASET:
            results = api.list_datasets(search=query, limit=20)
        else:
            # 搜索模型和数据集
            models = api.list_models(search=query, limit=10)
            datasets = api.list_datasets(search=query, limit=10)
            results = list(models) + list(datasets)
        
        # 转换为简单格式
        return [
            {
                "id": item.id,
                "name": item.modelId if hasattr(item, 'modelId') else item.id.split('/')[-1],
                "type": "MODEL" if hasattr(item, 'modelId') else "DATASET",
                "author": item.id.split('/')[0],
                "tags": item.tags,
                "downloads": getattr(item, "downloads", 0),
                "likes": getattr(item, "likes", 0),
            }
            for item in results
        ]
    except Exception as e:
        print(f"搜索资源出错: {str(e)}")
        return []

def get_resource_info(repo_id: str, resource_type: ResourceType) -> Optional[dict]:
    """获取Hugging Face Hub上资源的详细信息"""
    try:
        api = HfApi(endpoint=MIRRORS[DEFAULT_MIRROR_SOURCE])
        
        if resource_type == ResourceType.MODEL:
            info = api.model_info(repo_id=repo_id)
        else:
            info = api.dataset_info(repo_id=repo_id)
        
        return {
            "id": info.id,
            "name": getattr(info, "name", info.id.split('/')[-1]),
            "author": info.author,
            "description": info.description,
            "tags": info.tags,
            "downloads": getattr(info, "downloads", 0),
            "likes": getattr(info, "likes", 0),
            "last_modified": str(info.lastModified),
            "files": [f.rfilename for f in info.siblings],
            "size_bytes": sum(f.size for f in info.siblings if f.size),
        }
    except Exception as e:
        print(f"获取资源信息出错: {str(e)}")
        return None

def print_huggingface_config():
    """打印当前huggingface_hub配置以便诊断"""
    try:
        logger.info("============ HuggingFace配置信息 ============")
        logger.info(f"huggingface_hub版本: {importlib.metadata.version('huggingface_hub')}")
        logger.info(f"环境变量HF_ENDPOINT: {os.environ.get('HF_ENDPOINT', '未设置')}")
        logger.info(f"环境变量HF_HUB_ENABLE_HF_TRANSFER: {os.environ.get('HF_HUB_ENABLE_HF_TRANSFER', '未设置')}")
        
        # 检查huggingface_hub常量
        try:
            import huggingface_hub.constants as hf_constants
            if hasattr(hf_constants, "ENDPOINT"):
                logger.info(f"huggingface_hub.constants.ENDPOINT = {hf_constants.ENDPOINT}")
            
            # 查找其他URL常量
            for attr_name in dir(hf_constants):
                if attr_name.endswith("_URL") or "ENDPOINT" in attr_name:
                    attr_value = getattr(hf_constants, attr_name, None)
                    if attr_value and isinstance(attr_value, str):
                        logger.info(f"huggingface_hub.constants.{attr_name} = {attr_value}")
        except Exception as e:
            logger.warning(f"无法检查huggingface_hub常量: {str(e)}")
        
        # 检查是否安装了hf_transfer
        try:
        
            logger.info(f"hf_transfer已安装，版本: {importlib.metadata.version('hf_transfer')}")
        except ImportError:
            logger.info("hf_transfer未安装")
        
        # 检查网络连接
        try:
            logger.info("测试镜像站连接...")
            import urllib.request
            response = urllib.request.urlopen(mirror_url, timeout=5)
            logger.info(f"连接到 {mirror_url} 成功，状态码: {response.getcode()}")
        except Exception as e:
            logger.warning(f"连接到 {mirror_url} 失败: {str(e)}")
            
        logger.info("=========================================")
    except Exception as e:
        logger.error(f"打印配置时出错: {str(e)}")

def test_network_connection(url, timeout=5):
    """测试是否可以连接到指定URL"""
    try:
        import urllib.request
        import socket
        socket.setdefaulttimeout(timeout)
        response = urllib.request.urlopen(url, timeout=timeout)
        return True, f"连接成功，状态码: {response.getcode()}"
    except Exception as e:
        return False, f"连接失败: {str(e)}"

def check_network_connectivity():
    """检查网络连接情况"""
    logger.info("============= 网络连接测试 =============")
    
    # 测试镜像站连接
    for mirror_name, mirror_url in MIRRORS.items():
        success, message = test_network_connection(mirror_url)
        if success:
            logger.info(f"✓ 可以连接到 {mirror_name}: {mirror_url}")
        else:
            logger.warning(f"✗ 无法连接到 {mirror_name}: {mirror_url} - {message}")
    
    # 测试DNS解析
    try:
        import socket
        for domain in ["hf-mirror.com"]:  # 只检查镜像站域名
            try:
                ip = socket.gethostbyname(domain)
                logger.info(f"✓ DNS解析 {domain} -> {ip}")
            except socket.error as e:
                logger.warning(f"✗ DNS解析 {domain} 失败: {str(e)}")
    except Exception as e:
        logger.error(f"DNS测试失败: {str(e)}")
    
    logger.info("========================================")

# 检查网络连接
check_network_connectivity()

# 打印配置信息
print_huggingface_config() 