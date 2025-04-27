from fastapi import FastAPI, Depends, HTTPException, status, Response, File, UploadFile, Form, BackgroundTasks, Query, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from fastapi.staticfiles import StaticFiles
from datetime import timedelta, datetime
from typing import List, Dict, Any, Optional, Union
import io
import os
import random
import string
import shutil
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import base64
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
import json
import logging
import time
import importlib.metadata
import asyncio

from models import User, UserCreate, Token, UserRegister, ProfileUpdate, PasswordChange, ResourceType, DownloadStatus, ResourceCreate, Resource, MirrorSource, DownloadRequest, TrainingTask, TrainingTaskCreate, TrainingStatus, InferenceTask, InferenceTaskCreate, InferenceTaskUpdate, InferenceStatus, Message, ChatRequest, ChatResponse, EvaluationTask, EvaluationTaskCreate, EvaluationStatus
from database import authenticate_user, create_user, get_users, init_db, check_username_exists, update_user_profile, update_user_password, create_resource, get_all_resources, get_user_resources, get_resource, update_resource_status, delete_resource, create_training_task, get_all_training_tasks, get_user_training_tasks, get_training_task, update_training_task, get_training_logs, create_inference_task, get_all_inference_tasks, get_user_inference_tasks, get_inference_task, update_inference_task, delete_inference_task, create_evaluation_task, get_all_evaluation_tasks, get_user_evaluation_tasks, get_evaluation_task, update_evaluation_task, delete_evaluation_task, get_evaluation_logs, add_evaluation_log, start_evaluation_task, stop_evaluation_task
from auth import create_access_token, get_current_user, get_current_admin, ACCESS_TOKEN_EXPIRE_MINUTES
import huggingface_utils as hf_utils
import training_utils
import inference_utils
import evaluation_utils

# 配置日志记录器
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 初始化数据库
init_db()

# 创建上传目录
UPLOAD_DIR = Path("./uploads")
AVATAR_DIR = UPLOAD_DIR / "avatars"
AVATAR_DIR.mkdir(parents=True, exist_ok=True)

# 存储WebSocket连接的字典
evaluation_ws_connections = {}

# 处理datetime的JSON序列化
def datetime_json_serializer(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"无法序列化类型: {type(obj)}")

# 发送评估日志到WebSocket客户端
async def send_evaluation_log(task_id: int, log_data: str):
    """发送评估日志到WebSocket客户端"""
    if task_id in evaluation_ws_connections:
        for websocket in list(evaluation_ws_connections.get(task_id, [])):
            try:
                await websocket.send_text(log_data)
            except Exception as e:
                logger.error(f"WebSocket发送消息失败: {str(e)}")
                # 如果发送失败，可能是连接已关闭，从字典中移除
                try:
                    evaluation_ws_connections[task_id].remove(websocket)
                except:
                    pass

app = FastAPI()

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有头部
)

# 配置静态文件服务 - 恢复到原来的配置
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/models", StaticFiles(directory="LLM/models"), name="models")
app.mount("/datasets", StaticFiles(directory="LLM/datasets"), name="datasets")

# 存储验证码
captcha_store: Dict[str, str] = {}

# 生成随机验证码
def generate_captcha(length=4):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# 创建验证码图片
def create_captcha_image(text, width=120, height=48):
    # 创建空白图片
    image = Image.new('RGB', (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)
    
    # 使用默认字体
    font = ImageFont.load_default()
    
    # 绘制文本
    draw.text((10, 10), text, font=font, fill=(0, 0, 0))
    
    # 添加干扰线
    for i in range(5):
        start_x = random.randint(0, width)
        start_y = random.randint(0, height)
        end_x = random.randint(0, width)
        end_y = random.randint(0, height)
        draw.line([(start_x, start_y), (end_x, end_y)], fill=(128, 128, 128), width=1)
    
    # 添加噪点
    for i in range(width * height // 20):
        x = random.randint(0, width - 1)
        y = random.randint(0, height - 1)
        draw.point((x, y), fill=(0, 0, 0))
    
    # 将图片转为字节流
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    
    return img_byte_arr

# 以下路由模块暂时未创建，先注释掉
# app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
# app.include_router(users.router, prefix="/api/users", tags=["users"])
# app.include_router(models.router, prefix="/api/models", tags=["models"])
# app.include_router(conversations.router, prefix="/api/conversations", tags=["conversations"])

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/users/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@app.get("/api/users", response_model=List[User])
async def read_users(current_user: User = Depends(get_current_admin)):
    return get_users()

@app.post("/api/users", response_model=User)
async def create_new_user(user: UserCreate, current_user: User = Depends(get_current_admin)):
    try:
        return create_user(user)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"创建用户失败: {str(e)}"
        )

@app.get("/api/captcha")
async def get_captcha():
    # 生成验证码
    captcha_text = generate_captcha()
    captcha_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=24))
    
    # 存储验证码
    captcha_store[captcha_id] = captcha_text
    
    # 生成图片
    img_bytes = create_captcha_image(captcha_text)
    
    # 设置响应头
    headers = {"captcha-id": captcha_id}
    
    # 返回图片流
    return StreamingResponse(img_bytes, media_type="image/png", headers=headers)

@app.post("/api/register", response_model=User)
async def register_user(user_data: UserRegister):
    # 验证验证码
    captcha_id = user_data.captcha_id
    if captcha_id not in captcha_store or captcha_store[captcha_id].lower() != user_data.captcha.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码错误或已过期"
        )
    
    # 删除使用过的验证码
    if captcha_id in captcha_store:
        del captcha_store[captcha_id]
    
    # 检查用户名是否已存在
    if check_username_exists(user_data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在"
        )
    
    # 创建用户
    try:
        user_create = UserCreate(
            username=user_data.username,
            password=user_data.password,
            email=f"{user_data.username}@example.com",  # 简化版本，使用用户名生成默认邮箱
            is_admin=False
        )
        return create_user(user_create)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"创建用户失败: {str(e)}"
        )

@app.get("/api/profile")
async def get_profile(current_user: User = Depends(get_current_user)):
    # 返回用户个人资料，包括头像URL
    user_dict = current_user.dict()
    
    # 检查用户是否有头像
    avatar_path = AVATAR_DIR / f"{current_user.id}.jpg"
    if avatar_path.exists():
        user_dict["avatar_url"] = f"/uploads/avatars/{current_user.id}.jpg"
    else:
        user_dict["avatar_url"] = None
        
    # 添加其他可能的个人资料字段
    user_dict["display_name"] = getattr(current_user, "display_name", None)
    user_dict["phone"] = getattr(current_user, "phone", None)
    
    return user_dict

@app.put("/api/profile", response_model=User)
async def update_profile(profile_data: ProfileUpdate, current_user: User = Depends(get_current_user)):
    # 更新用户个人资料
    try:
        updated_user = update_user_profile(current_user.id, profile_data)
        return updated_user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"更新个人资料失败: {str(e)}"
        )

@app.post("/api/profile/avatar")
async def upload_avatar(avatar: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    # 检查文件类型
    if avatar.content_type not in ["image/jpeg", "image/png", "image/gif"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只支持JPG, PNG, GIF格式的图片"
        )
    
    # 读取文件内容
    contents = await avatar.read()
    
    # 检查文件大小（最大2MB）
    if len(contents) > 2 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件大小不能超过2MB"
        )
    
    # 处理图片并保存
    try:
        # 转换为JPEG格式并调整大小
        image = Image.open(io.BytesIO(contents))
        image = image.convert("RGB")
        image.thumbnail((200, 200))  # 调整大小，保持比例
        
        # 保存图片
        avatar_path = AVATAR_DIR / f"{current_user.id}.jpg"
        image.save(avatar_path)
        
        # 返回头像URL
        return {
            "message": "头像上传成功",
            "avatar_url": f"/uploads/avatars/{current_user.id}.jpg"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"处理头像图片失败: {str(e)}"
        )

@app.post("/api/profile/change-password")
async def change_password(password_data: PasswordChange, current_user: User = Depends(get_current_user)):
    # 验证当前密码并更新为新密码
    try:
        # 验证当前密码
        user = authenticate_user(current_user.username, password_data.current_password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="当前密码不正确"
            )
        
        # 更新密码
        update_user_password(current_user.id, password_data.new_password)
        
        return {"message": "密码已成功更新"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"修改密码失败: {str(e)}"
        )

@app.get("/api/admin/dashboard")
async def admin_dashboard(current_user: User = Depends(get_current_admin)):
    return {
        "message": "管理员面板",
        "user_count": len(get_users())
    }

@app.get("/api/items")
async def get_items(current_user: User = Depends(get_current_user)):
    return {"items": ["Item 1", "Item 2", "Item 3"]}

# 获取当前活跃用户
def get_current_active_user(current_user: User = Depends(get_current_user)):
    # 检查用户是否被禁用等操作
    return current_user

# 资源和下载管理相关接口
@app.post("/api/resources", response_model=Resource)
async def create_new_resource(
    resource: ResourceCreate,
    current_user: User = Depends(get_current_active_user)
):
    """创建新的资源（模型或数据集）"""
    return create_resource(resource_data=resource, user_id=current_user.id)

@app.get("/api/resources", response_model=List[Resource])
async def get_resources(
    resource_type: Optional[ResourceType] = None,
    status: Optional[DownloadStatus] = None,
    current_user: User = Depends(get_current_active_user)
):
    """获取当前用户的所有资源"""
    if current_user.is_admin:
        # 管理员可以查看所有用户的资源
        resources = get_all_resources()
    else:
        # 普通用户只能查看自己的资源
        resources = get_user_resources(user_id=current_user.id)
    
    # 根据类型和状态过滤
    if resource_type:
        resources = [r for r in resources if r.resource_type == resource_type]
    if status:
        resources = [r for r in resources if r.status == status]
    
    return resources

@app.get("/api/resources/{resource_id}", response_model=Resource)
async def get_resource_by_id(
    resource_id: int,
    current_user: User = Depends(get_current_active_user)
):
    """获取单个资源详情"""
    resource = get_resource(resource_id=resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="资源不存在")
    
    # 检查访问权限
    if not current_user.is_admin and resource.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问此资源")
    
    return resource

@app.delete("/api/resources/{resource_id}", status_code=204)
async def remove_resource(
    resource_id: int,
    current_user: User = Depends(get_current_active_user)
):
    """删除资源"""
    resource = get_resource(resource_id=resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="资源不存在")
    
    # 检查删除权限
    if not current_user.is_admin and resource.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权删除此资源")
    
    # 如果资源正在下载，先停止下载
    if resource.status == DownloadStatus.DOWNLOADING:
        hf_utils.stop_download(resource_id)
    
    # 删除实际文件
    if resource.local_path:
        try:
            local_path = Path(resource.local_path)
            # 确保路径是在允许的目录内
            allowed_dirs = ["./models", "./datasets", "LLM/models", "LLM/datasets"]
            is_allowed = any(str(local_path).startswith(d) for d in allowed_dirs)
            
            if is_allowed and local_path.exists():
                logger.info(f"删除资源文件: {local_path}")
                # 如果是目录，递归删除
                if local_path.is_dir():
                    shutil.rmtree(local_path, ignore_errors=True)
                # 如果是文件，直接删除
                elif local_path.is_file():
                    os.remove(local_path)
                logger.info(f"资源文件删除成功: {local_path}")
            else:
                logger.warning(f"资源路径不存在或不在允许的目录中: {local_path}")
        except Exception as e:
            logger.error(f"删除资源文件失败: {str(e)}")
            # 继续删除数据库记录，即使文件删除失败
    
    # 删除资源记录
    delete_resource(resource_id=resource_id)
    return Response(status_code=204)

@app.post("/api/resources/{resource_id}/download", response_model=Resource)
async def start_resource_download(
    resource_id: int,
    download_request: DownloadRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user)
):
    """开始下载资源"""
    resource = get_resource(resource_id=resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="资源不存在")
    
    # 检查权限
    if not current_user.is_admin and resource.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权下载此资源")
    
    # 检查资源当前状态
    if resource.status == DownloadStatus.DOWNLOADING:
        raise HTTPException(status_code=400, detail="资源已经在下载中")
    
    # 启动下载（在后台任务中执行）
    def download_task():
        hf_utils.start_download(
            resource=resource,
            source=download_request.source
        )
    
    background_tasks.add_task(download_task)
    
    # 更新资源状态为下载中
    updated_resource = update_resource_status(
        resource_id=resource_id,
        status=DownloadStatus.DOWNLOADING,
        progress=0.0
    )
    
    return updated_resource

@app.post("/api/resources/{resource_id}/stop", response_model=Resource)
async def stop_resource_download(
    resource_id: int,
    current_user: User = Depends(get_current_active_user)
):
    """停止资源下载"""
    resource = get_resource(resource_id=resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="资源不存在")
    
    # 检查权限
    if not current_user.is_admin and resource.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权停止此资源下载")
    
    # 检查资源当前状态
    if resource.status != DownloadStatus.DOWNLOADING:
        raise HTTPException(status_code=400, detail="资源当前不在下载中")
    
    # 停止下载
    success = hf_utils.stop_download(resource_id)
    if not success:
        raise HTTPException(status_code=500, detail="停止下载失败")
    
    # 获取更新后的资源状态
    updated_resource = get_resource(resource_id=resource_id)
    return updated_resource

@app.post("/api/resources/{resource_id}/retry", response_model=Resource)
async def retry_resource_download(
    resource_id: int,
    download_request: DownloadRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user)
):
    """重试下载失败的资源"""
    resource = get_resource(resource_id=resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="资源不存在")
    
    # 检查权限
    if not current_user.is_admin and resource.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权重试此资源下载")
    
    # 检查资源当前状态
    if resource.status == DownloadStatus.DOWNLOADING:
        raise HTTPException(status_code=400, detail="资源已经在下载中")
    
    # 启动下载（在后台任务中执行）
    def download_task():
        hf_utils.start_download(
            resource=resource,
            source=download_request.source
        )
    
    background_tasks.add_task(download_task)
    
    # 更新资源状态为下载中
    updated_resource = update_resource_status(
        resource_id=resource_id,
        status=DownloadStatus.DOWNLOADING,
        progress=0.0
    )
    
    return updated_resource

@app.get("/api/downloads/active", response_model=List[int])
async def get_active_downloads(
    current_user: User = Depends(get_current_active_user)
):
    """获取当前活动下载的资源ID列表"""
    active_downloads = hf_utils.get_active_downloads()
    
    # 如果不是管理员，只返回当前用户的活动下载
    if not current_user.is_admin:
        user_resources = get_user_resources(user_id=current_user.id)
        user_resource_ids = [r.id for r in user_resources]
        active_downloads = {k: v for k, v in active_downloads.items() if k in user_resource_ids}
    
    return list(active_downloads.keys())

@app.get("/api/mirror-sources")
async def get_mirror_sources():
    """获取可用的镜像源"""
    return {source.name: source.value for source in MirrorSource}

@app.get("/api/search")
async def search_huggingface_resources(
    query: str,
    resource_type: Optional[ResourceType] = None,
    current_user: User = Depends(get_current_active_user)
):
    """搜索Hugging Face上的模型或数据集"""
    results = hf_utils.search_resources(query=query, resource_type=resource_type)
    return results

@app.get("/api/resource-info/{repo_id}")
async def get_huggingface_resource_info(
    repo_id: str,
    resource_type: ResourceType,
    current_user: User = Depends(get_current_active_user)
):
    """获取Hugging Face上资源的详细信息"""
    info = hf_utils.get_resource_info(repo_id=repo_id, resource_type=resource_type)
    if not info:
        raise HTTPException(status_code=404, detail="无法获取资源信息")
    return info

@app.get("/api/storage-info")
async def get_storage_info(
    current_user: User = Depends(get_current_active_user)
):
    """获取存储空间信息"""
    # 获取模型和数据集目录的大小
    model_dir = os.path.abspath(hf_utils.DEFAULT_MODEL_DIR)
    dataset_dir = os.path.abspath(hf_utils.DEFAULT_DATASET_DIR)
    
    # 计算目录大小
    def get_dir_size(path):
        total_size = 0
        if os.path.exists(path):
            for dirpath, dirnames, filenames in os.walk(path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if os.path.exists(fp):
                        total_size += os.path.getsize(fp)
        return total_size / (1024 * 1024)  # 转换为MB
    
    model_size_mb = get_dir_size(model_dir)
    dataset_size_mb = get_dir_size(dataset_dir)
    
    return {
        "model_dir": model_dir,
        "dataset_dir": dataset_dir,
        "model_size_mb": model_size_mb,
        "dataset_size_mb": dataset_size_mb,
        "total_size_mb": model_size_mb + dataset_size_mb
    }

# 训练相关接口
@app.post("/api/training/tasks", response_model=TrainingTask)
async def create_training_task(
    task: TrainingTaskCreate,
    current_user: User = Depends(get_current_active_user)
):
    """创建新的训练任务"""
    try:
        # 确保模型和数据集存在且已下载
        model = get_resource(resource_id=task.base_model_id)
        if not model or model.resource_type != ResourceType.MODEL or model.status != DownloadStatus.COMPLETED:
            raise HTTPException(status_code=400, detail="选择的模型不存在或未下载完成")
        
        dataset = get_resource(resource_id=task.dataset_id)
        if not dataset or dataset.resource_type != ResourceType.DATASET or dataset.status != DownloadStatus.COMPLETED:
            raise HTTPException(status_code=400, detail="选择的数据集不存在或未下载完成")
        
        # 创建训练任务
        from database import create_training_task as db_create_training_task
        return db_create_training_task(task_data=task, user_id=current_user.id)
    except Exception as e:
        # 记录错误并返回详细信息
        logger.error(f"创建训练任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建训练任务失败: {str(e)}")

@app.get("/api/training/tasks", response_model=List[TrainingTask])
async def get_training_tasks(
    current_user: User = Depends(get_current_active_user)
):
    """获取训练任务列表"""
    if current_user.is_admin:
        return get_all_training_tasks()
    else:
        return get_user_training_tasks(user_id=current_user.id)

@app.get("/api/training/tasks/{task_id}", response_model=TrainingTask)
async def get_training_task_by_id(
    task_id: int,
    current_user: User = Depends(get_current_active_user)
):
    """获取训练任务详情"""
    task = get_training_task(task_id=task_id)
    if not task:
        raise HTTPException(status_code=404, detail="训练任务不存在")
    
    # 检查权限
    if not current_user.is_admin and task.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权查看此训练任务")
    
    return task

@app.post("/api/training/tasks/{task_id}/start", response_model=TrainingTask)
async def start_training_task(
    task_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user)
):
    """开始训练任务"""
    try:
        logger.info(f"尝试启动训练任务 ID: {task_id}, 用户: {current_user.username}")
        
        task = get_training_task(task_id=task_id)
        if not task:
            logger.error(f"训练任务不存在: {task_id}")
            raise HTTPException(status_code=404, detail="训练任务不存在")
        
        # 检查权限
        if not current_user.is_admin and task.user_id != current_user.id:
            logger.warning(f"用户 {current_user.username} 无权启动任务 {task_id}")
            raise HTTPException(status_code=403, detail="无权启动此训练任务")
        
        # 检查任务状态
        if task.status == TrainingStatus.RUNNING:
            logger.warning(f"任务 {task_id} 已经在运行中")
            raise HTTPException(status_code=400, detail="训练任务已经在运行")
        
        # 先清除任务日志，确保旧日志不会干扰
        from database import clear_training_logs
        clear_training_logs(task_id)
        logger.info(f"已清除任务 {task_id} 的旧日志")
        
        logger.info(f"将在后台启动训练任务: {task_id}")
        
        # 在后台启动训练
        background_tasks.add_task(training_utils.run_training, task_id)
        logger.info(f"已将训练任务 {task_id} 添加到后台任务")
        
        # 更新任务状态
        updated_task = update_training_task(
            task_id=task_id,
            status=TrainingStatus.PENDING
        )
        
        if not updated_task:
            logger.error(f"无法更新任务 {task_id} 的状态")
            raise HTTPException(status_code=500, detail="无法更新任务状态")
        
        logger.info(f"训练任务 {task_id} 状态已更新为 PENDING")
        return updated_task
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"启动训练任务 {task_id} 时发生异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"启动训练任务失败: {str(e)}")

@app.post("/api/training/tasks/{task_id}/stop", response_model=TrainingTask)
async def stop_training_task(
    task_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user)
):
    """停止训练任务"""
    task = get_training_task(task_id=task_id)
    if not task:
        raise HTTPException(status_code=404, detail="训练任务不存在")
    
    # 检查权限
    if not current_user.is_admin and task.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权停止此训练任务")
    
    # 检查任务状态
    if task.status != TrainingStatus.RUNNING:
        raise HTTPException(status_code=400, detail="训练任务未在运行")
    
    # 在后台停止训练
    background_tasks.add_task(training_utils.stop_training, task_id)
    
    # 更新任务状态
    updated_task = update_training_task(
        task_id=task_id,
        status=TrainingStatus.STOPPED
    )
    
    return updated_task

@app.get("/api/training/tasks/{task_id}/logs")
async def get_training_logs(
    task_id: int,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user)
):
    """获取训练日志"""
    try:
        task = get_training_task(task_id=task_id)
        if not task:
            raise HTTPException(status_code=404, detail="训练任务不存在")
        
        # 检查权限
        if not current_user.is_admin and task.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权查看此训练任务的日志")
        
        # 从数据库获取日志
        from database import get_training_logs as db_get_training_logs
        logs = db_get_training_logs(task_id=task_id, limit=limit, offset=offset)
        return logs
    except Exception as e:
        logger.error(f"获取训练日志失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取训练日志失败: {str(e)}")

@app.delete("/api/training/tasks/{task_id}", response_model=dict)
async def delete_training_task(
    task_id: int,
    current_user: User = Depends(get_current_active_user)
):
    """删除训练任务"""
    try:
        logger.info(f"尝试删除训练任务 ID: {task_id}, 用户: {current_user.username}")
        
        task = get_training_task(task_id=task_id)
        if not task:
            logger.error(f"训练任务不存在: {task_id}")
            raise HTTPException(status_code=404, detail="训练任务不存在")
        
        # 检查权限
        if not current_user.is_admin and task.user_id != current_user.id:
            logger.warning(f"用户 {current_user.username} 无权删除任务 {task_id}")
            raise HTTPException(status_code=403, detail="无权删除此训练任务")
        
        # 检查任务状态 - 不允许删除正在运行的任务
        if task.status == TrainingStatus.RUNNING:
            logger.warning(f"无法删除正在运行的任务 {task_id}")
            raise HTTPException(status_code=400, detail="无法删除正在运行的训练任务，请先停止任务")
        
        # 清理所有相关文件和目录
        task_name = task.name
        cleanup_result = training_utils.clean_training_files(task_name, task_id)
        logger.info(f"清理训练文件结果: {cleanup_result}")
        
        # 确保输出目录被彻底删除
        if task.output_path and os.path.exists(task.output_path):
            try:
                if os.path.isdir(task.output_path):
                    logger.info(f"删除训练输出目录: {task.output_path}")
                    shutil.rmtree(task.output_path, ignore_errors=True)
                    logger.info(f"训练输出目录删除成功: {task.output_path}")
            except Exception as e:
                logger.error(f"删除训练输出目录失败: {str(e)}")
        
        # 确保配置文件被删除
        if task.config_path and os.path.exists(task.config_path):
            try:
                logger.info(f"删除训练配置文件: {task.config_path}")
                os.remove(task.config_path)
                logger.info(f"训练配置文件删除成功: {task.config_path}")
            except Exception as e:
                logger.error(f"删除训练配置文件失败: {str(e)}")
        
        # 从数据库中删除任务
        from database import delete_training_task as db_delete_training_task
        result = db_delete_training_task(task_id=task_id)
        
        if result:
            logger.info(f"成功删除训练任务 {task_id}")
            return {
                "message": "训练任务已成功删除",
                "task_id": task_id,
                "cleaned_files": cleanup_result.get("cleaned_files", []),
                "errors": cleanup_result.get("errors", [])
            }
        else:
            logger.error(f"删除训练任务 {task_id} 失败")
            raise HTTPException(status_code=500, detail="删除训练任务失败")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"删除训练任务 {task_id} 时发生异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除训练任务失败: {str(e)}")

@app.get("/api/training/available-models")
async def get_available_models(
    current_user: User = Depends(get_current_active_user)
):
    """获取可用于训练的模型列表"""
    if current_user.is_admin:
        models = get_all_resources()
    else:
        models = get_user_resources(user_id=current_user.id)
    
    # 过滤出已下载完成的模型
    available_models = [
        model for model in models 
        if model.resource_type == ResourceType.MODEL and model.status == DownloadStatus.COMPLETED
    ]
    
    return available_models

@app.get("/api/training/available-datasets")
async def get_available_datasets(
    current_user: User = Depends(get_current_active_user)
):
    """获取可用于训练的数据集列表"""
    if current_user.is_admin:
        datasets = get_all_resources()
    else:
        datasets = get_user_resources(user_id=current_user.id)
    
    # 过滤出已下载完成的数据集
    available_datasets = [
        dataset for dataset in datasets 
        if dataset.resource_type == ResourceType.DATASET and dataset.status == DownloadStatus.COMPLETED
    ]
    
    return available_datasets

@app.get("/api/training/default-config")
async def get_default_training_config():
    """获取默认训练配置"""
    return {
        "model": {
            "model_max_length": 2048,
            "torch_dtype_str": "bfloat16",
            "attn_implementation": "sdpa",
            "load_pretrained_weights": True,
            "trust_remote_code": True
        },
        "data": {
            "target_col": "prompt"
        },
        "training": {
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
            "include_performance_metrics": True
        }
    }

@app.websocket("/ws/training/{task_id}")
async def websocket_training_logs(
    websocket: WebSocket,
    task_id: int
):
    """WebSocket端点，用于实时发送训练日志"""
    await websocket.accept()
    
    # 获取训练任务
    task = get_training_task(task_id=task_id)
    if not task:
        await websocket.close(code=1000, reason="训练任务不存在")
        logger.error(f"WebSocket连接请求任务不存在: task_id={task_id}")
        return
    
    # 记录连接建立时间，用于过滤日志
    connection_time = datetime.now()
    logger.info(f"WebSocket连接已建立: task_id={task_id}, time={connection_time}, status={task.status}")
    
    # 注册WebSocket连接
    training_utils.register_websocket(task_id, websocket)
    
    try:
        # 发送连接建立确认消息
        await websocket.send_text(json.dumps({
            "timestamp": datetime.now().isoformat(),
            "content": f"WebSocket连接已建立，任务状态: {task.status}，等待训练日志...",
            "level": "INFO"
        }))
        logger.info(f"已发送WebSocket初始消息: task_id={task_id}")
        
        # 如果任务已经在运行，先发送一个状态信息
        if task.status == TrainingStatus.RUNNING:
            await websocket.send_text(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "content": f"任务正在运行中，进度: {task.progress*100:.2f}%",
                "level": "INFO"
            }))
            logger.info(f"已发送任务运行状态更新: task_id={task_id}, progress={task.progress}")
        
        # 保持连接打开，直到客户端关闭
        while True:
            try:
                data = await websocket.receive_text()
                logger.debug(f"WebSocket收到消息: task_id={task_id}, data={data}")
                if data == "ping":
                    await websocket.send_text("pong")
                    logger.debug(f"WebSocket发送pong响应: task_id={task_id}")
                elif data == "refresh":
                    # 客户端请求刷新日志
                    await websocket.send_text(json.dumps({
                        "timestamp": datetime.now().isoformat(),
                        "content": "正在刷新...",
                        "level": "INFO"
                    }))
                    logger.info(f"客户端请求刷新日志: task_id={task_id}")
            except WebSocketDisconnect:
                logger.info(f"WebSocket客户端断开连接: task_id={task_id}")
                break
            except Exception as e:
                logger.error(f"WebSocket接收消息错误: task_id={task_id}, error={str(e)}")
                break
    except Exception as e:
        logger.error(f"WebSocket错误: task_id={task_id}, error={str(e)}")
    finally:
        # 移除WebSocket连接
        training_utils.remove_websocket(task_id, websocket)
        logger.info(f"WebSocket连接已移除: task_id={task_id}")

@app.websocket("/ws/resources")
async def websocket_resources(websocket: WebSocket):
    """资源WebSocket连接"""
    await websocket.accept()
    
    try:
        # 注册WebSocket连接
        training_utils.register_websocket("resources", websocket)
        
        # 保持连接
        while True:
            try:
                # 等待消息
                data = await websocket.receive_text()
                
                # 处理消息
                message = json.loads(data)
                if message.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                    
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket错误: {str(e)}")
                break
                
    finally:
        
        training_utils.remove_websocket("resources", websocket)

# ========== 推理API ==========

@app.get("/api/inference/tasks", response_model=List[InferenceTask])
async def get_inference_tasks(current_user: User = Depends(get_current_active_user)):
    """获取推理任务列表"""
    try:
        if current_user.is_admin:
            tasks = get_all_inference_tasks()
        else:
            tasks = get_user_inference_tasks(user_id=current_user.id)
        return tasks
    except Exception as e:
        logger.exception(f"获取推理任务列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取推理任务列表失败: {str(e)}")

@app.post("/api/inference/tasks", response_model=InferenceTask)
async def create_inference_task_api(
    task_create: InferenceTaskCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user)
):
    """创建推理任务"""
    try:
        logger.info(f"创建推理任务: {task_create.name}, 用户: {current_user.username}")
        
        # 检查模型是否存在
        model = get_resource(resource_id=task_create.model_id)
        if not model:
            logger.error(f"模型不存在: {task_create.model_id}")
            raise HTTPException(status_code=404, detail="模型不存在")
        
        # 检查模型类型
        if model.resource_type != ResourceType.MODEL:
            logger.error(f"资源不是模型: {task_create.model_id}")
            raise HTTPException(status_code=400, detail="资源不是模型")
        
        # 检查模型是否已下载
        if model.status != DownloadStatus.COMPLETED:
            logger.error(f"模型未下载完成: {task_create.model_id}")
            raise HTTPException(status_code=400, detail="模型未下载完成")
        
        # 检查GPU资源是否足够
        gpu_info = inference_utils.get_gpu_info()
        if not gpu_info["available"]:
            logger.error("没有可用的GPU")
            raise HTTPException(status_code=400, detail="没有可用的GPU")
        
        # 估算模型显存占用
        estimated_memory = inference_utils.estimate_model_memory(
            model_id=task_create.model_id,
            tensor_parallel_size=task_create.tensor_parallel_size
        )
        
        # 检查显存是否足够
        if estimated_memory > gpu_info["free_memory"]:
            logger.error(f"GPU显存不足: 需要 {estimated_memory:.2f}GB, 可用 {gpu_info['free_memory']:.2f}GB")
            raise HTTPException(
                status_code=400,
                detail=f"GPU显存不足: 需要 {estimated_memory:.2f}GB, 可用 {gpu_info['free_memory']:.2f}GB"
            )
        
        # 创建推理任务
        task = create_inference_task(
            name=task_create.name,
            model_id=task_create.model_id,
            user_id=current_user.id,
            tensor_parallel_size=task_create.tensor_parallel_size,
            max_model_len=task_create.max_model_len,
            quantization=task_create.quantization,
            dtype=task_create.dtype,
            max_tokens=task_create.max_tokens,
            temperature=task_create.temperature,
            top_p=task_create.top_p,
            top_k=task_create.top_k,
            repetition_penalty=task_create.repetition_penalty,
            presence_penalty=task_create.presence_penalty,
            frequency_penalty=task_create.frequency_penalty
        )
        
        if not task:
            logger.error("创建推理任务失败")
            raise HTTPException(status_code=500, detail="创建推理任务失败")
        
        # 在后台启动推理服务
        background_tasks.add_task(inference_utils.start_inference_service, task.id)
        
        logger.info(f"推理任务创建成功: ID={task.id}, 名称={task.name}")
        return task
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"创建推理任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建推理任务失败: {str(e)}")

@app.get("/api/inference/tasks/{task_id}", response_model=InferenceTask)
async def get_inference_task_api(
    task_id: int,
    current_user: User = Depends(get_current_active_user)
):
    """获取推理任务详情"""
    try:
        task = get_inference_task(task_id=task_id)
        if not task:
            logger.error(f"推理任务不存在: {task_id}")
            raise HTTPException(status_code=404, detail="推理任务不存在")
        
        # 检查权限
        if not current_user.is_admin and task.user_id != current_user.id:
            logger.warning(f"用户 {current_user.username} 无权查看推理任务 {task_id}")
            raise HTTPException(status_code=403, detail="无权查看此推理任务")
        
        return task
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"获取推理任务详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取推理任务详情失败: {str(e)}")

@app.delete("/api/inference/tasks/{task_id}", response_model=dict)
async def delete_inference_task_api(
    task_id: int,
    current_user: User = Depends(get_current_active_user)
):
    """删除推理任务"""
    try:
        logger.info(f"删除推理任务: {task_id}, 用户: {current_user.username}")
        
        task = get_inference_task(task_id=task_id)
        if not task:
            logger.error(f"推理任务不存在: {task_id}")
            raise HTTPException(status_code=404, detail="推理任务不存在")
        
        # 检查权限
        if not current_user.is_admin and task.user_id != current_user.id:
            logger.warning(f"用户 {current_user.username} 无权删除推理任务 {task_id}")
            raise HTTPException(status_code=403, detail="无权删除此推理任务")
        
        # 如果任务正在运行，先停止
        if task.status == InferenceStatus.RUNNING:
            await inference_utils.stop_inference_service(task_id)
            logger.info(f"已停止正在运行的推理任务: {task_id}")
        
        # 清理任务相关的临时文件
        try:
            # 清理推理任务可能创建的临时文件或目录
            inference_utils.cleanup_inference_files(task_id)
            logger.info(f"已清理推理任务相关文件: {task_id}")
        except Exception as e:
            logger.error(f"清理推理任务文件失败: {str(e)}")
        
        # 删除任务
        if delete_inference_task(task_id):
            logger.info(f"推理任务删除成功: {task_id}")
            return {"message": "推理任务已删除"}
        else:
            logger.error(f"删除推理任务失败: {task_id}")
            raise HTTPException(status_code=500, detail="删除推理任务失败")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"删除推理任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除推理任务失败: {str(e)}")

@app.post("/api/inference/tasks/{task_id}/stop", response_model=dict)
async def stop_inference_task(
    task_id: int,
    current_user: User = Depends(get_current_active_user)
):
    """停止推理任务"""
    try:
        logger.info(f"停止推理任务: {task_id}, 用户: {current_user.username}")
        
        task = get_inference_task(task_id=task_id)
        if not task:
            logger.error(f"推理任务不存在: {task_id}")
            raise HTTPException(status_code=404, detail="推理任务不存在")
        
        # 检查权限
        if not current_user.is_admin and task.user_id != current_user.id:
            logger.warning(f"用户 {current_user.username} 无权停止推理任务 {task_id}")
            raise HTTPException(status_code=403, detail="无权停止此推理任务")
        
        # 检查任务状态
        if task.status != InferenceStatus.RUNNING:
            logger.warning(f"推理任务不在运行中: {task_id}, 当前状态: {task.status}")
            raise HTTPException(status_code=400, detail=f"推理任务不在运行中，当前状态: {task.status}")
        
        # 停止任务
        if await inference_utils.stop_inference_service(task_id):
            logger.info(f"推理任务已停止: {task_id}")
            return {"message": "推理任务已停止"}
        else:
            logger.error(f"停止推理任务失败: {task_id}")
            raise HTTPException(status_code=500, detail="停止推理任务失败")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"停止推理任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"停止推理任务失败: {str(e)}")

@app.post("/api/inference/tasks/{task_id}/start", response_model=dict)
async def start_inference_task(
    task_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user)
):
    """启动推理任务"""
    try:
        logger.info(f"启动推理任务: {task_id}, 用户: {current_user.username}")
        
        task = get_inference_task(task_id=task_id)
        if not task:
            logger.error(f"推理任务不存在: {task_id}")
            raise HTTPException(status_code=404, detail="推理任务不存在")
        
        # 检查权限
        if not current_user.is_admin and task.user_id != current_user.id:
            logger.warning(f"用户 {current_user.username} 无权启动推理任务 {task_id}")
            raise HTTPException(status_code=403, detail="无权启动此推理任务")
        
        # 检查任务状态
        if task.status == InferenceStatus.RUNNING:
            logger.warning(f"推理任务已在运行中: {task_id}")
            raise HTTPException(status_code=400, detail="推理任务已在运行中")
        
        # 检查GPU资源是否足够
        gpu_info = inference_utils.get_gpu_info()
        if not gpu_info["available"]:
            logger.error("没有可用的GPU")
            raise HTTPException(status_code=400, detail="没有可用的GPU")
        
        # 估算模型显存占用
        estimated_memory = inference_utils.estimate_model_memory(
            model_id=task.model_id,
            tensor_parallel_size=task.tensor_parallel_size
        )
        
        # 检查显存是否足够
        if estimated_memory > gpu_info["free_memory"]:
            logger.error(f"GPU显存不足: 需要 {estimated_memory:.2f}GB, 可用 {gpu_info['free_memory']:.2f}GB")
            raise HTTPException(
                status_code=400,
                detail=f"GPU显存不足: 需要 {estimated_memory:.2f}GB, 可用 {gpu_info['free_memory']:.2f}GB"
            )
        
        # 更新任务状态
        update_inference_task(
            task_id=task_id,
            status=InferenceStatus.CREATING
        )
        
        # 在后台启动推理服务
        background_tasks.add_task(inference_utils.start_inference_service, task_id)
        
        logger.info(f"推理任务正在启动: {task_id}")
        return {"message": "推理任务正在启动"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"启动推理任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"启动推理任务失败: {str(e)}")

@app.get("/api/inference/tasks/{task_id}/status", response_model=dict)
async def get_inference_task_status(
    task_id: int,
    current_user: User = Depends(get_current_active_user)
):
    """获取推理任务状态"""
    try:
        task = get_inference_task(task_id=task_id)
        if not task:
            logger.error(f"推理任务不存在: {task_id}")
            raise HTTPException(status_code=404, detail="推理任务不存在")
        
        # 检查权限
        if not current_user.is_admin and task.user_id != current_user.id:
            logger.warning(f"用户 {current_user.username} 无权查看推理任务 {task_id} 状态")
            raise HTTPException(status_code=403, detail="无权查看此推理任务状态")
        
        # 获取任务状态
        status = await inference_utils.check_inference_service(task_id)
        
        return status
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"获取推理任务状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取推理任务状态失败: {str(e)}")

@app.get("/api/inference/gpu", response_model=dict)
async def get_gpu_status(current_user: User = Depends(get_current_active_user)):
    """获取GPU状态"""
    try:
        gpu_info = inference_utils.get_gpu_info()
        return gpu_info
    except Exception as e:
        logger.exception(f"获取GPU状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取GPU状态失败: {str(e)}")

@app.post("/api/inference/tasks/{task_id}/chat", response_model=ChatResponse)
async def inference_chat(
    task_id: int,
    chat_request: ChatRequest,
    current_user: User = Depends(get_current_active_user)
):
    """推理聊天接口"""
    try:
        logger.info(f"处理聊天请求: 任务ID={task_id}, 用户={current_user.username}, 消息数量={len(chat_request.messages)}")
        
        task = get_inference_task(task_id=task_id)
        if not task:
            logger.error(f"推理任务不存在: {task_id}")
            raise HTTPException(status_code=404, detail="推理任务不存在")
        
        # 检查权限
        if not current_user.is_admin and task.user_id != current_user.id:
            logger.warning(f"用户 {current_user.username} 无权使用推理任务 {task_id}")
            raise HTTPException(status_code=403, detail="无权使用此推理任务")
        
        # 检查任务状态
        if task.status != InferenceStatus.RUNNING:
            logger.error(f"推理任务不在运行中: {task_id}, 当前状态: {task.status}")
            raise HTTPException(status_code=400, detail=f"推理任务不在运行中，当前状态: {task.status}")
        
        # 记录请求参数
        logger.debug(f"聊天请求参数: task_id={task_id}, temperature={chat_request.temperature}, " 
                    f"top_p={chat_request.top_p}, max_tokens={chat_request.max_tokens}, "
                    f"repetition_penalty={chat_request.repetition_penalty}")
        
        # 记录最后一条用户消息（用于调试）
        last_user_msg = next((msg.content for msg in reversed(chat_request.messages) if msg.role == "user"), None)
        if last_user_msg:
            logger.debug(f"最后用户消息(前50个字符): {last_user_msg[:50]}...")
        
        # 执行推理
        messages = [msg.dict() for msg in chat_request.messages]
        start_time = time.time()
        result = await inference_utils.perform_inference(
            task_id=task_id,
            messages=messages,
            temperature=chat_request.temperature,
            top_p=chat_request.top_p,
            max_tokens=chat_request.max_tokens,
            repetition_penalty=chat_request.repetition_penalty
        )
        inference_time = time.time() - start_time
        
        if "error" in result:
            logger.error(f"推理失败: {result['error']}")
            raise HTTPException(status_code=500, detail=result["error"])
        
        # 记录响应结果
        response_content = result["message"]["content"]
        logger.info(f"推理成功: 任务ID={task_id}, 耗时={inference_time:.2f}秒, 响应长度={len(response_content)}")
        logger.debug(f"响应内容(前50个字符): {response_content[:50]}...")
        
        return ChatResponse(
            message=Message(**result["message"]),
            task_id=task_id
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"推理失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"推理失败: {str(e)}")

@app.put("/api/inference/tasks/{task_id}/params", response_model=InferenceTask)
async def update_inference_params(
    task_id: int,
    params: dict,
    current_user: User = Depends(get_current_active_user)
):
    """更新推理任务的参数"""
    # 获取任务
    task = get_inference_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="推理任务不存在")
    
    # 检查权限
    if task.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="无权更新此推理任务")
    
    # 提取共享设置参数（不受任务状态限制）
    share_settings = {}
    
    # 共享设置
    if "share_enabled" in params:
        share_enabled = params["share_enabled"]
        if not isinstance(share_enabled, bool):
            raise HTTPException(status_code=400, detail="share_enabled必须是布尔值")
        share_settings["share_enabled"] = share_enabled
    
    # 显示名称
    if "display_name" in params:
        display_name = params["display_name"]
        if display_name is not None and not isinstance(display_name, str):
            raise HTTPException(status_code=400, detail="display_name必须是字符串")
        share_settings["display_name"] = display_name
    
    # 如果有共享设置参数，无论任务状态如何都更新它们
    if share_settings:
        updated_task = update_inference_task(
            task_id=task_id,
            **share_settings
        )
        
        if not updated_task:
            raise HTTPException(status_code=500, detail="更新共享设置失败")
        
        logger.info(f"已更新推理任务共享设置: task_id={task_id}, settings={share_settings}")
        
        # 如果只有共享设置参数且已更新，直接返回更新后的任务
        if task.status != InferenceStatus.RUNNING or not set(params.keys()) - set(share_settings.keys()):
            return updated_task
        
        # 如果还有其他参数且任务在运行中，继续处理其他参数
        task = updated_task
    
    # 只允许更新运行中的任务的推理参数
    if task.status != InferenceStatus.RUNNING:
        raise HTTPException(status_code=400, detail="只能更新运行中的任务的推理参数")
    
    # 提取并验证推理参数
    update_data = {}
    
    # 最大输出Token
    if "max_tokens" in params:
        max_tokens = params["max_tokens"]
        if not isinstance(max_tokens, int) or max_tokens < 1 or max_tokens > 4096:
            raise HTTPException(status_code=400, detail="max_tokens必须是1-4096之间的整数")
        update_data["max_tokens"] = max_tokens
    
    # 温度
    if "temperature" in params:
        temperature = params["temperature"]
        if not isinstance(temperature, (int, float)) or temperature < 0 or temperature > 2:
            raise HTTPException(status_code=400, detail="temperature必须是0-2之间的数值")
        update_data["temperature"] = float(temperature)
    
    # Top P
    if "top_p" in params:
        top_p = params["top_p"]
        if not isinstance(top_p, (int, float)) or top_p < 0 or top_p > 1:
            raise HTTPException(status_code=400, detail="top_p必须是0-1之间的数值")
        update_data["top_p"] = float(top_p)
    
    # Top K
    if "top_k" in params:
        top_k = params["top_k"]
        if not isinstance(top_k, int) or top_k < 1 or top_k > 100:
            raise HTTPException(status_code=400, detail="top_k必须是1-100之间的整数")
        update_data["top_k"] = top_k
    
    # 重复惩罚
    if "repetition_penalty" in params:
        repetition_penalty = params["repetition_penalty"]
        if not isinstance(repetition_penalty, (int, float)) or repetition_penalty < 1 or repetition_penalty > 2:
            raise HTTPException(status_code=400, detail="repetition_penalty必须是1-2之间的数值")
        update_data["repetition_penalty"] = float(repetition_penalty)
    
    # 如果没有要更新的参数，直接返回当前任务
    if not update_data:
        return task
    
    # 更新任务参数
    updated_task = update_inference_task(
        task_id=task_id,
        **update_data
    )
    
    if not updated_task:
        raise HTTPException(status_code=500, detail="更新参数失败")
    
    logger.info(f"已更新推理任务参数: task_id={task_id}, params={update_data}")
    return updated_task

@app.get("/api/resources/scan")
async def scan_local_resources(current_user: User = Depends(get_current_active_user)):
    """扫描本地模型和数据集文件，自动创建资源记录"""
    result = {"added": [], "existing": [], "errors": []}
    
    # 扫描模型目录
    models_dir = Path("./LLM/models")
    datasets_dir = Path("./LLM/datasets")
    
    # 使用当前登录用户的ID
    user_id = current_user.id
    
    if models_dir.exists():
        # 遍历模型目录
        for model_dir in models_dir.iterdir():
            if model_dir.is_dir():
                try:
                    # 检查是否已经存在同名资源
                    exists = False
                    for resource in get_all_resources():
                        if resource.name == model_dir.name:
                            exists = True
                            result["existing"].append(f"模型: {model_dir.name}")
                            break
                    
                    if not exists:
                        # 创建新的资源记录
                        resource_data = ResourceCreate(
                            name=model_dir.name,
                            repo_id=f"local/{model_dir.name}",
                            description=f"本地模型: {model_dir.name}",
                            resource_type=ResourceType.MODEL
                        )
                        resource = create_resource(resource_data=resource_data, user_id=user_id)
                        
                        # 更新资源状态为已完成
                        update_resource_status(
                            resource_id=resource.id,
                            status=DownloadStatus.COMPLETED,
                            progress=1.0,
                            local_path=f"LLM/models/{model_dir.name}"
                        )
                        
                        result["added"].append(f"模型: {model_dir.name}")
                except Exception as e:
                    result["errors"].append(f"模型 {model_dir.name} 添加失败: {str(e)}")
    
    if datasets_dir.exists():
        # 遍历数据集目录
        for dataset_dir in datasets_dir.iterdir():
            if dataset_dir.is_dir():
                try:
                    # 检查是否已经存在同名资源
                    exists = False
                    for resource in get_all_resources():
                        if resource.name == dataset_dir.name:
                            exists = True
                            result["existing"].append(f"数据集: {dataset_dir.name}")
                            break
                    
                    if not exists:
                        # 创建新的资源记录
                        resource_data = ResourceCreate(
                            name=dataset_dir.name,
                            repo_id=f"local/{dataset_dir.name}",
                            description=f"本地数据集: {dataset_dir.name}",
                            resource_type=ResourceType.DATASET
                        )
                        resource = create_resource(resource_data=resource_data, user_id=user_id)
                        
                        # 更新资源状态为已完成
                        update_resource_status(
                            resource_id=resource.id,
                            status=DownloadStatus.COMPLETED,
                            progress=1.0,
                            local_path=f"LLM/datasets/{dataset_dir.name}"
                        )
                        
                        result["added"].append(f"数据集: {dataset_dir.name}")
                except Exception as e:
                    result["errors"].append(f"数据集 {dataset_dir.name} 添加失败: {str(e)}")
    
    return result

# 简化版API，不使用下划线或连字符
@app.get("/api/share")
async def get_shared_tasks_simple():
    """获取所有已共享的推理任务的简化API"""
    tasks = []
    
    # 获取所有推理任务
    all_tasks = get_all_inference_tasks()
    
    # 记录找到的任务总数
    total_tasks = len(all_tasks)
    shared_tasks = len([t for t in all_tasks if t.share_enabled])
    running_tasks = len([t for t in all_tasks if t.status == InferenceStatus.RUNNING])
    shared_running = len([t for t in all_tasks if t.share_enabled and t.status == InferenceStatus.RUNNING])
    
    logger.info(f"共享API - 总任务数: {total_tasks}, 共享任务: {shared_tasks}, 运行中任务: {running_tasks}, 共享且运行中: {shared_running}")
    
    # 过滤出已共享且正在运行的任务
    for task in all_tasks:
        if task.share_enabled and task.status == InferenceStatus.RUNNING:
            # 验证任务是否真正可用
            try:
                # 检查推理服务是否真正运行
                if not task.api_base or not task.port:
                    logger.warning(f"任务 {task.id}:{task.name} 被标记为共享但缺少API信息，已跳过")
                    continue
                
                # 尝试通过进程ID检查服务是否真正运行中
                if task.process_id:
                    # 这里只是记录，不做实际检查，可以根据需要添加进程检查
                    logger.info(f"任务 {task.id}:{task.name} 进程ID: {task.process_id}")
                else:
                    logger.warning(f"任务 {task.id}:{task.name} 没有关联的进程ID，可能未正常运行")
                    # 实际应用中可能需要额外检查或跳过
                
                # 只返回必要的信息
                tasks.append({
                    "id": task.id,
                    "display_name": task.display_name or task.name,
                    "status": task.status
                })
                logger.info(f"添加共享任务 {task.id}:{task.name} 到公开列表")
            except Exception as e:
                logger.error(f"处理共享任务 {task.id} 时出错: {str(e)}")
                continue
    
    logger.info(f"共享API - 最终返回的可用共享任务数: {len(tasks)}")
    return tasks

@app.get("/api/share/{task_id}")
async def get_shared_task_simple(task_id: int):
    """获取指定的共享推理任务信息的简化API"""
    task = get_inference_task(task_id=task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="推理任务不存在")
    
    if not task.share_enabled or task.status != InferenceStatus.RUNNING:
        raise HTTPException(status_code=403, detail="该推理任务未共享或未运行")
    
    # 验证任务是否真正可用
    if not task.api_base or not task.port:
        raise HTTPException(status_code=503, detail="该推理任务配置不完整，暂不可用")
    
    # 返回任务信息（仅包含必要字段）
    return {
        "id": task.id,
        "display_name": task.display_name or task.name,
        "status": task.status,
        "max_tokens": task.max_tokens,
        "temperature": task.temperature,
        "top_p": task.top_p,
        "repetition_penalty": task.repetition_penalty
    }

@app.websocket("/api/ws/chat/{task_id}")
async def websocket_chat(
    websocket: WebSocket,
    task_id: int
):
    """WebSocket端点，用于实时推理聊天"""
    # 定义connection_id，确保在finally块中可用
    connection_id = f"chat_{task_id}"
    
    try:
        await websocket.accept()
        
        # 获取推理任务
        task = get_inference_task(task_id=task_id)
        if not task:
            await websocket.close(code=1000, reason="推理任务不存在")
            logger.error(f"WebSocket聊天连接请求任务不存在: task_id={task_id}")
            return
        
        # 检查任务状态
        if task.status != InferenceStatus.RUNNING:
            await websocket.close(code=1000, reason=f"推理任务未运行，当前状态: {task.status}")
            logger.error(f"WebSocket聊天连接请求任务未运行: task_id={task_id}, status={task.status}")
            return
        
        # 验证任务是否可访问
        is_shared_task = task.share_enabled
        authorized_user = None
        
        # 从查询参数中获取令牌
        token = websocket.query_params.get("token")
        
        # 如果是共享任务，则无需认证直接允许访问
        if is_shared_task:
            logger.info(f"共享任务WebSocket连接: task_id={task_id}")
        else:
            # 如果提供了token，尝试验证用户
            if token:
                try:
                    from auth import decode_token
                    
                    # 解析token获取用户名
                    username = decode_token(token).get("sub")
                    if username:
                        from database import get_user_by_username
                        authorized_user = get_user_by_username(username)
                        
                        # 检查用户是否有权限访问该任务
                        if authorized_user and (authorized_user.id == task.user_id or authorized_user.is_admin):
                            logger.info(f"认证用户WebSocket连接: user={username}, task_id={task_id}")
                        else:
                            authorized_user = None
                except Exception as e:
                    logger.error(f"Token验证失败: {str(e)}")
                    authorized_user = None
            
            # 如果不是共享任务且用户未认证，则拒绝访问
            if not authorized_user:
                await websocket.close(code=1000, reason="未授权访问非共享任务")
                logger.error(f"未认证用户尝试访问非共享任务: task_id={task_id}")
                return
        
        # 注册WebSocket连接
        if hasattr(training_utils, 'register_websocket'):
            training_utils.register_websocket(connection_id, websocket)
        
        logger.info(f"WebSocket聊天连接已建立: task_id={task_id}, 共享任务={is_shared_task}")
        
        # 历史消息记录
        chat_history = []
        
        # 发送连接建立确认
        display_name = task.display_name or task.name
        await websocket.send_text(json.dumps({
            "type": "connected",
            "task_id": task_id,
            "model_name": display_name
        }))
        
        # 保持连接打开，监听消息
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                if message.get("type") == "ping":
                    # 心跳保持连接活跃
                    await websocket.send_text(json.dumps({"type": "pong"}))
                
                elif message.get("type") == "message":
                    # 用户发送了新消息
                    user_message = message.get("content", "")
                    log_prefix = "共享" if is_shared_task else ""
                    logger.info(f"WebSocket收到{log_prefix}聊天消息: task_id={task_id}, length={len(user_message)}")
                    
                    # 添加到历史记录
                    chat_history.append({"role": "user", "content": user_message})
                    
                    try:
                        # 调用推理API
                        result = await inference_utils.perform_inference(
                            task_id=task_id,
                            messages=chat_history,
                            temperature=task.temperature,
                            top_p=task.top_p,
                            max_tokens=task.max_tokens,
                            repetition_penalty=task.repetition_penalty
                        )
                        
                        if "error" in result:
                            # 发送错误消息
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "error": result["error"]
                            }))
                            logger.error(f"WebSocket{log_prefix}聊天推理错误: task_id={task_id}, error={result['error']}")
                        else:
                            # 添加回复到历史记录
                            assistant_message = result["message"]
                            chat_history.append(assistant_message)
                            
                            # 获取回复内容
                            content = ""
                            if isinstance(assistant_message, dict) and "content" in assistant_message:
                                content = assistant_message["content"]
                            elif hasattr(assistant_message, "content"):
                                content = assistant_message.content
                            else:
                                logger.warning(f"无法从消息中提取内容: {assistant_message}")
                                content = str(assistant_message)
                            
                            if not content:
                                logger.warning("模型返回了空回复")
                                content = "抱歉，模型返回了空回复。"
                            
                            # 先发送一个流式消息通知开始输出
                            await websocket.send_text(json.dumps({
                                "type": "stream",
                                "content": ""
                            }))
                            
                            # 分段发送响应内容 (每30个字符分一段)
                            chunk_size = 30
                            for i in range(0, len(content), chunk_size):
                                chunk = content[i:i+chunk_size]
                                if chunk:
                                    await websocket.send_text(json.dumps({
                                        "type": "stream",
                                        "content": chunk
                                    }))
                                    # 添加小延迟模拟打字效果
                                    await asyncio.sleep(0.05)
                            
                            # 发送结束消息
                            await websocket.send_text(json.dumps({
                                "type": "end",
                                "content": content
                            }))
                            logger.info(f"WebSocket{log_prefix}聊天推理完成: task_id={task_id}")
                    except Exception as e:
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "error": f"推理处理错误: {str(e)}"
                        }))
                        logger.exception(f"WebSocket{log_prefix}聊天处理异常: task_id={task_id}")
                
                elif message.get("type") == "clear_history":
                    # 清空聊天历史
                    chat_history = []
                    logger.info(f"WebSocket{log_prefix}聊天历史已清空: task_id={task_id}")
                    
            except WebSocketDisconnect:
                logger.info(f"WebSocket{log_prefix}聊天客户端断开连接: task_id={task_id}")
                break
            except Exception as e:
                logger.error(f"WebSocket{log_prefix}聊天错误: task_id={task_id}, error={str(e)}")
                break
    
    except Exception as e:
        logger.exception(f"WebSocket聊天连接错误: task_id={task_id}, error={str(e)}")
    
    finally:
        # 移除WebSocket连接
        if hasattr(training_utils, 'remove_websocket'):
            training_utils.remove_websocket(connection_id, websocket)
        logger.info(f"WebSocket聊天连接已关闭: task_id={task_id}")

# 评估相关的API接口
@app.get("/api/evaluation/tasks", response_model=List[EvaluationTask], tags=["evaluation"])
async def get_evaluation_tasks(
    current_user: User = Depends(get_current_active_user)
):
    """获取评估任务列表"""
    tasks = get_user_evaluation_tasks(current_user.id)
    return tasks

@app.post("/api/evaluation/tasks", response_model=EvaluationTask)
async def create_evaluation_task_api(
    task_create: EvaluationTaskCreate,
    current_user: User = Depends(get_current_active_user)
):
    """创建评估任务"""
    # 检查模型是否存在
    model = get_resource(task_create.model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"模型 ID {task_create.model_id} 不存在"
        )
    
    # 检查模型是否已下载
    if model.status != DownloadStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"模型 {model.name} 尚未完成下载，无法评估"
        )
    
    # 如果是自定义基准测试，检查数据集路径
    if task_create.benchmark_type == "custom" and not task_create.custom_dataset_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="自定义基准测试需要提供数据集路径"
        )
    
    # 创建评估任务
    try:
        task = create_evaluation_task(task_create, current_user.id)
        return task
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建评估任务失败: {str(e)}"
        )

@app.get("/api/evaluation/tasks/{task_id}", response_model=EvaluationTask)
async def get_evaluation_task_api(
    task_id: int,
    current_user: User = Depends(get_current_active_user)
):
    """获取评估任务详情"""
    task = get_evaluation_task(task_id)
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"评估任务 ID {task_id} 不存在"
        )
    
    # 检查权限
    if task.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您没有权限访问此评估任务"
        )
    
    return task

@app.delete("/api/evaluation/tasks/{task_id}", response_model=dict)
async def delete_evaluation_task_api(
    task_id: int,
    current_user: User = Depends(get_current_active_user)
):
    """删除评估任务"""
    task = get_evaluation_task(task_id)
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"评估任务 ID {task_id} 不存在"
        )
    
    # 检查权限
    if task.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您没有权限删除此评估任务"
        )
    
    # 检查任务状态，不能删除正在运行的任务
    if task.status == EvaluationStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无法删除正在运行的评估任务，请先停止任务"
        )
    
    # 删除任务
    success = delete_evaluation_task(task_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除评估任务失败"
        )
    
    return {"message": "评估任务已删除", "task_id": task_id}

@app.post("/api/evaluation/tasks/{task_id}/start")
async def start_evaluation_task_api(
    task_id: int,
    current_user: User = Depends(get_current_active_user)
):
    """启动评估任务"""
    task = get_evaluation_task(task_id)
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"评估任务 ID {task_id} 不存在"
        )
    
    # 检查权限
    if task.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您没有权限操作此评估任务"
        )
    
    # 检查任务状态
    if task.status == EvaluationStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="评估任务已在运行中"
        )
    
    # 更新任务状态
    try:
        updated_task = start_evaluation_task(task_id)
        return {"status": "success", "task": updated_task}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"启动评估任务失败: {str(e)}"
        )

@app.post("/api/evaluation/tasks/{task_id}/stop")
async def stop_evaluation_task_api(
    task_id: int,
    current_user: User = Depends(get_current_active_user)
):
    """停止评估任务"""
    task = get_evaluation_task(task_id)
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"评估任务 ID {task_id} 不存在"
        )
    
    # 检查权限
    if task.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您没有权限操作此评估任务"
        )
    
    # 检查任务状态
    if task.status != EvaluationStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能停止正在运行的评估任务"
        )
    
    # 更新任务状态
    try:
        updated_task = stop_evaluation_task(task_id)
        return {"status": "success", "task": updated_task}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"停止评估任务失败: {str(e)}"
        )

@app.get("/api/evaluation/tasks/{task_id}/logs")
async def get_evaluation_logs_api(
    task_id: int,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_active_user)
):
    """获取评估任务日志"""
    task = get_evaluation_task(task_id)
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"评估任务 ID {task_id} 不存在"
        )
    
    # 检查权限
    if task.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您没有权限查看此评估任务日志"
        )
    
    # 获取日志
    logs = get_evaluation_logs(task_id, limit, offset)
    return logs

@app.get("/api/evaluation/benchmarks", tags=["evaluation"])
async def get_benchmarks(
    current_user: User = Depends(get_current_active_user)
):
    """获取可用的基准测试列表"""
    benchmarks = evaluation_utils.get_available_benchmarks()
    return benchmarks

@app.websocket("/ws/evaluation/{task_id}")
async def websocket_evaluation_logs(
    websocket: WebSocket,
    task_id: int
):
    """通过WebSocket获取评估任务日志"""
    await websocket.accept()
    
    # 将连接添加到连接字典中
    if task_id not in evaluation_ws_connections:
        evaluation_ws_connections[task_id] = set()
    evaluation_ws_connections[task_id].add(websocket)
    
    # 定义最后一条日志的时间戳
    last_timestamp = datetime.min.isoformat()  # 使用ISO格式字符串
    
    try:
        # 检查任务是否存在
        task = get_evaluation_task(task_id)
        if not task:
            await websocket.send_text(json.dumps(
                {"error": f"评估任务 ID {task_id} 不存在"},
                default=datetime_json_serializer
            ))
            await websocket.close()
            return
        
        # 发送初始任务状态
        await websocket.send_text(json.dumps({
            "type": "task_status",
            "data": {
                "id": task.id,
                "status": task.status,
                "progress": task.progress,
                "error_message": task.error_message
            }
        }, default=datetime_json_serializer))
        
        # 循环发送日志和状态更新
        while True:
            # 获取最新的日志
            logs = get_evaluation_logs(task_id, limit=100)
            
            # 过滤出新的日志
            new_logs = []
            for log in logs:
                # 确保时间戳是字符串类型
                log_timestamp = log["timestamp"]
                if isinstance(log_timestamp, datetime):
                    log_timestamp = log_timestamp.isoformat()
                
                if log_timestamp > last_timestamp:
                    new_logs.append(log)
            
            # 更新最后一条日志的时间戳
            if new_logs:
                # 确保时间戳是字符串
                latest_timestamp = new_logs[0]["timestamp"]
                if isinstance(latest_timestamp, datetime):
                    latest_timestamp = latest_timestamp.isoformat()
                last_timestamp = latest_timestamp
                
                # 发送新日志
                await websocket.send_text(json.dumps({
                    "type": "logs",
                    "data": new_logs
                }, default=datetime_json_serializer))
            
            # 获取最新的任务状态
            updated_task = get_evaluation_task(task_id)
            if updated_task and (updated_task.status != task.status or updated_task.progress != task.progress):
                # 发送任务状态更新
                await websocket.send_text(json.dumps({
                    "type": "task_status",
                    "data": {
                        "id": updated_task.id,
                        "status": updated_task.status,
                        "progress": updated_task.progress,
                        "error_message": updated_task.error_message,
                        "metrics": updated_task.metrics
                    }
                }, default=datetime_json_serializer))
                
                # 更新任务状态引用
                task = updated_task
            
            # 如果任务已完成、失败或停止，退出循环
            if updated_task and updated_task.status in [EvaluationStatus.COMPLETED, EvaluationStatus.FAILED, EvaluationStatus.STOPPED]:
                # 再等待5秒，确保所有日志都已获取
                await asyncio.sleep(5)
                break
            
            # 等待一段时间再查询
            await asyncio.sleep(1)
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket评估日志异常: {str(e)}")
        try:
            await websocket.send_text(json.dumps(
                {"error": f"发生错误: {str(e)}"},
                default=datetime_json_serializer
            ))
        except:
            pass
    
    finally:
        # 从连接字典中移除
        if task_id in evaluation_ws_connections and websocket in evaluation_ws_connections[task_id]:
            evaluation_ws_connections[task_id].remove(websocket)
            # 如果集合为空，删除整个键
            if not evaluation_ws_connections[task_id]:
                del evaluation_ws_connections[task_id]
                
        # 确保WebSocket关闭
        try:
            await websocket.close()
        except:
            pass

@app.post("/api/inference/tasks/{task_id}/toggle-share", response_model=InferenceTask)
async def toggle_task_share(
    task_id: int,
    share_data: dict,
    current_user: User = Depends(get_current_active_user)
):
    """切换推理任务的共享状态"""
    # 获取任务
    task = get_inference_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="推理任务不存在")
    
    # 检查权限
    if task.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="无权更新此推理任务")
    
    # 提取共享设置
    share_enabled = share_data.get("share_enabled")
    if share_enabled is None:
        raise HTTPException(status_code=400, detail="必须提供share_enabled参数")
    
    if not isinstance(share_enabled, bool):
        raise HTTPException(status_code=400, detail="share_enabled必须是布尔值")
        
    # 提取显示名称
    display_name = share_data.get("display_name", task.name)
    
    # 更新任务
    updated_task = update_inference_task(
        task_id=task_id,
        share_enabled=share_enabled,
        display_name=display_name
    )
    
    if not updated_task:
        raise HTTPException(status_code=500, detail="更新共享设置失败")
    
    logger.info(f"已切换推理任务共享状态: task_id={task_id}, share_enabled={share_enabled}")
    return updated_task



# 添加根路由和通配符路由处理前端请求
@app.get("/")
async def read_root():
    """返回前端页面"""
    return FileResponse("static/index.html")

@app.get("/{path:path}")
async def serve_frontend(path: str):
    """处理前端路由"""
    # 如果是API请求，交给后面的API处理
    if path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API endpoint not found")
        
    # 检查是否是静态资源文件
    static_path = os.path.join("static", path)
    if os.path.isfile(static_path):
        return FileResponse(static_path)
        
    # 所有其他请求返回前端入口页面
    return FileResponse("static/index.html")

if __name__ == "__main__":
    import uvicorn
    import sys
    import logging
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("backend.log")
        ]
    )
    
    # 显示系统信息
    import platform
    logging.info(f"操作系统: {platform.system()} {platform.release()}")
    logging.info(f"Python版本: {platform.python_version()}")
    
    # 检查huggingface_hub版本
    try:
        hf_version = importlib.metadata.version("huggingface_hub")
        logging.info(f"huggingface_hub版本: {hf_version}")
        if platform.system() == "Linux" and not hf_version.startswith("0.17") and not hf_version.startswith("0.18") and not hf_version.startswith("0.19"):
            logging.warning(f"当前huggingface_hub版本 {hf_version} 可能不支持某些功能。建议升级到0.17.0以上版本：pip install --upgrade huggingface_hub>=0.17.0")
    except Exception as e:
        logging.warning(f"无法检查huggingface_hub版本: {str(e)}")
    
    # 启动服务
    uvicorn.run(app, host="0.0.0.0", port=8000) 