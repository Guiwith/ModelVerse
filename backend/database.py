import os
import json
import logging
from datetime import datetime
from pathlib import Path
from passlib.context import CryptContext
from models import User, UserCreate, UserInDB, ProfileUpdate, Resource, ResourceCreate, DownloadStatus, ResourceType, TrainingTask, TrainingTaskCreate, TrainingStatus, TrainingLogEntry, InferenceTask, InferenceStatus, EvaluationTask, EvaluationTaskCreate, EvaluationStatus, EvaluationMetrics, EvaluationLogEntry, BenchmarkType
from typing import List, Optional, Dict, Any, Union, Tuple

logger = logging.getLogger(__name__)

# 密码哈希工具
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 数据库文件路径
DB_PATH = Path("./db.json")

# 用户数据
users_db = []

# 模型和数据集
resources_db = []

# 训练任务相关数据
training_tasks_db = []
training_logs_db = []

# 推理任务相关数据
inference_tasks_db = []

# 评估任务相关数据
evaluation_tasks_db = []
evaluation_logs_db = []

# 初始化数据库
def init_db():
    global users_db, resources_db, training_tasks_db, training_logs_db, inference_tasks_db, evaluation_tasks_db, evaluation_logs_db
    
    # 如果数据库文件存在则加载，否则创建默认管理员
    if os.path.exists(DB_PATH):
        try:
            with open(DB_PATH, "r") as f:
                data = json.load(f)
                # 修复数据加载错误：确保data是字典类型而不是列表
                if isinstance(data, dict):
                    users_db = data.get("users", [])
                    resources_db = data.get("resources", [])
                    training_tasks_db = data.get("training_tasks", [])
                    training_logs_db = data.get("training_logs", [])
                    inference_tasks_db = data.get("inference_tasks", [])
                    evaluation_tasks_db = data.get("evaluation_tasks", [])
                    evaluation_logs_db = data.get("evaluation_logs", [])
                else:
                    print("数据库格式错误：数据不是字典类型")
                    users_db = []
                    resources_db = []
                    training_tasks_db = []
                    training_logs_db = []
                    inference_tasks_db = []
                    evaluation_tasks_db = []
                    evaluation_logs_db = []
        except Exception as e:
            print(f"加载数据库失败: {str(e)}")
            users_db = []
            resources_db = []
            training_tasks_db = []
            training_logs_db = []
            inference_tasks_db = []
            evaluation_tasks_db = []
            evaluation_logs_db = []
    
    # 如果没有用户，创建默认管理员用户
    if not users_db:
        admin = UserCreate(
            username="admin",
            email="admin@example.com",
            password="admin123",
            is_admin=True
        )
        create_user(admin)
        save_db()

# 保存数据库
def save_db():
    with open(DB_PATH, "w") as f:
        json.dump({
            "users": users_db,
            "resources": resources_db,
            "training_tasks": training_tasks_db,
            "training_logs": training_logs_db[:1000],  # 只保存最近的1000条日志
            "inference_tasks": inference_tasks_db[:1000],  # 只保存最近的1000条推理任务
            "evaluation_tasks": evaluation_tasks_db,
            "evaluation_logs": evaluation_logs_db[:1000],  # 只保存最近的1000条评估日志
        }, f, default=str)

# 验证密码
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# 获取密码哈希
def get_password_hash(password):
    return pwd_context.hash(password)

# 创建用户
def create_user(user: UserCreate):
    # 检查用户名是否已存在
    if check_username_exists(user.username):
        raise Exception("用户名已存在")
    
    # 生成用户ID
    user_id = len(users_db) + 1
    
    # 哈希密码
    hashed_password = get_password_hash(user.password)
    
    # 创建用户对象
    user_dict = user.dict()
    user_dict.update({
        "id": user_id,
        "created_at": datetime.now(),
        "hashed_password": hashed_password,
        "display_name": "",  # 添加默认的个人资料字段
        "phone": ""
    })
    del user_dict["password"]
    
    # 添加到数据库
    users_db.append(user_dict)
    save_db()
    
    # 返回用户对象
    return User(**user_dict)

# 通过用户名获取用户
def get_user_by_username(username: str):
    for user in users_db:
        if user["username"] == username:
            return UserInDB(**user)
    return None

# 通过ID获取用户
def get_user_by_id(user_id: int):
    for user in users_db:
        if user["id"] == user_id:
            return UserInDB(**user)
    return None

# 检查用户名是否存在
def check_username_exists(username: str) -> bool:
    return get_user_by_username(username) is not None

# 验证用户
def authenticate_user(username: str, password: str):
    user = get_user_by_username(username)
    if not user or not verify_password(password, user.hashed_password):
        return False
    return user

# 更新用户个人资料
def update_user_profile(user_id: int, profile_data: ProfileUpdate):
    # 查找用户
    for i, user in enumerate(users_db):
        if user["id"] == user_id:
            # 更新字段
            if profile_data.display_name is not None:
                users_db[i]["display_name"] = profile_data.display_name
            if profile_data.email is not None:
                users_db[i]["email"] = profile_data.email
            if profile_data.phone is not None:
                users_db[i]["phone"] = profile_data.phone
            
            # 保存数据库
            save_db()
            
            # 返回更新后的用户
            return User(**users_db[i])
    
    # 如果没找到用户
    raise Exception("用户不存在")

# 更新用户密码
def update_user_password(user_id: int, new_password: str):
    # 查找用户
    for i, user in enumerate(users_db):
        if user["id"] == user_id:
            # 更新密码
            users_db[i]["hashed_password"] = get_password_hash(new_password)
            
            # 保存数据库
            save_db()
            return True
    
    # 如果没找到用户
    raise Exception("用户不存在")

# 模型和数据集管理相关函数
# 创建新的资源记录
def create_resource(resource_data: ResourceCreate, user_id: int) -> Resource:
    # 生成资源ID
    resource_id = len(resources_db) + 1
    
    # 创建时间
    created_at = datetime.now()
    
    # 创建资源对象
    resource_dict = resource_data.dict()
    resource_dict.update({
        "id": resource_id,
        "user_id": user_id,
        "status": DownloadStatus.PENDING,
        "progress": 0,
        "local_path": None,
        "error_message": None,
        "created_at": created_at,
        "updated_at": created_at,
        "size_mb": None
    })
    
    # 添加到数据库
    resources_db.append(resource_dict)
    save_db()
    
    # 返回资源对象
    return Resource(**resource_dict)

# 更新资源状态
def update_resource_status(resource_id: int, status: DownloadStatus, progress: float = None, 
                            error_message: str = None, local_path: str = None, size_mb: float = None):
    # 查找资源
    for i, resource in enumerate(resources_db):
        if resource["id"] == resource_id:
            # 更新字段
            resources_db[i]["status"] = status
            resources_db[i]["updated_at"] = datetime.now()
            
            if progress is not None:
                resources_db[i]["progress"] = progress
            
            if error_message is not None:
                resources_db[i]["error_message"] = error_message
            
            if local_path is not None:
                resources_db[i]["local_path"] = local_path
                
            if size_mb is not None:
                resources_db[i]["size_mb"] = size_mb
            
            # 保存数据库
            save_db()
            
            # 返回更新后的资源
            return Resource(**resources_db[i])
    
    # 如果没找到资源
    raise Exception("资源不存在")

# 获取所有资源
def get_all_resources():
    return [Resource(**resource) for resource in resources_db]

# 获取用户资源
def get_user_resources(user_id: int):
    return [Resource(**resource) for resource in resources_db if resource["user_id"] == user_id]

# 获取资源详情
def get_resource(resource_id: int):
    for resource in resources_db:
        if resource["id"] == resource_id:
            return Resource(**resource)
    return None

# 删除资源
def delete_resource(resource_id: int):
    global resources_db
    for i, resource in enumerate(resources_db):
        if resource["id"] == resource_id:
            del resources_db[i]
            save_db()
            return True
    return False

# 获取所有用户
def get_users():
    return [User(**user) for user in users_db]

# 训练任务管理功能
def create_training_task(task_data: TrainingTaskCreate, user_id: int) -> TrainingTask:
    """创建新的训练任务"""
    global training_tasks_db
    
    # 生成任务ID
    task_id = len(training_tasks_db) + 1
    
    # 创建任务对象
    task_dict = task_data.dict()
    task_dict.update({
        "id": task_id,
        "user_id": user_id,
        "status": TrainingStatus.PENDING,
        "progress": 0.0,
        "created_at": datetime.now(),
        "config_path": None,
        "output_path": None
    })
    
    # 添加到数据库
    training_tasks_db.append(task_dict)
    save_db()
    
    # 返回任务对象
    return TrainingTask(**task_dict)

def get_all_training_tasks() -> List[TrainingTask]:
    """获取所有训练任务"""
    return [TrainingTask(**task) for task in training_tasks_db]

def get_user_training_tasks(user_id: int) -> List[TrainingTask]:
    """获取用户的训练任务"""
    return [TrainingTask(**task) for task in training_tasks_db if task["user_id"] == user_id]

def get_training_task(task_id: int) -> Optional[TrainingTask]:
    """获取单个训练任务"""
    for task in training_tasks_db:
        if task["id"] == task_id:
            return TrainingTask(**task)
    return None

def update_training_task(task_id: int, **kwargs) -> Optional[TrainingTask]:
    """更新训练任务状态"""
    for i, task in enumerate(training_tasks_db):
        if task["id"] == task_id:
            # 更新字段
            for key, value in kwargs.items():
                if key in task:
                    training_tasks_db[i][key] = value
            
            # 保存数据库
            save_db()
            
            # 返回更新后的任务
            return TrainingTask(**training_tasks_db[i])
    
    return None

def delete_training_task(task_id: int) -> bool:
    """删除训练任务"""
    global training_tasks_db
    for i, task in enumerate(training_tasks_db):
        if task["id"] == task_id:
            del training_tasks_db[i]
            save_db()
            return True
    return False

def add_training_log(task_id: int, content: str, level: str = "INFO"):
    """添加训练日志"""
    global training_logs_db
    
    # 获取最新的数据
    init_db()
    
    # 创建新的日志项
    log_entry = TrainingLogEntry(
        task_id=task_id,
        content=content,
        level=level,
        timestamp=datetime.now().isoformat()
    )
    
    # 限制每个任务的最大日志数量为500
    task_logs = [log for log in training_logs_db if log["task_id"] == task_id]
    if len(task_logs) >= 500:
        # 如果超过500条，删除最早的日志
        oldest_logs = sorted(task_logs, key=lambda x: x["timestamp"])[:len(task_logs) - 499]
        training_logs_db = [log for log in training_logs_db if log["task_id"] != task_id or log not in oldest_logs]
    
    # 添加新日志
    training_logs_db.append(log_entry.dict())
    
    # 每10条日志保存一次数据库
    if len(training_logs_db) % 10 == 0:
        save_db()

def get_training_logs(task_id: int, limit: int = 100, offset: int = 0) -> List[Dict]:
    """获取训练任务的日志"""
    # 过滤并统一时间戳格式
    filtered_logs = []
    for log in training_logs_db:
        if log["task_id"] == task_id:
            log_copy = log.copy()
            # 确保时间戳是字符串
            if isinstance(log_copy["timestamp"], datetime):
                log_copy["timestamp"] = log_copy["timestamp"].isoformat()
            filtered_logs.append(log_copy)
    
    # 按时间戳逆序排序 (最新的在前面)
    logs = sorted(
        filtered_logs,
        key=lambda x: x["timestamp"],
        reverse=True
    )
    
    # 应用分页
    if offset < len(logs):
        return logs[offset:offset + limit]
    return []

def clear_training_logs(task_id: int) -> bool:
    """清除指定任务的所有日志"""
    global training_logs_db
    
    # 记录原始日志数量
    original_count = len(training_logs_db)
    
    # 过滤掉指定任务的日志
    training_logs_db = [log for log in training_logs_db if log["task_id"] != task_id]
    
    # 计算删除的日志数量
    removed_count = original_count - len(training_logs_db)
    
    # 立即保存数据库，确保持久化
    save_db()
    
    # 强制从磁盘重新加载数据库，确保清除生效
    init_db()
    
    print(f"已清除任务 {task_id} 的日志，共 {removed_count} 条")
    return True

# ========== 推理任务操作 ==========

def create_inference_task(
    name: str,
    model_id: int,
    user_id: int,
    share_enabled: bool = False,
    display_name: Optional[str] = None,
    tensor_parallel_size: int = 1,
    max_model_len: int = 4096,
    quantization: Optional[str] = None,
    dtype: str = "auto",
    max_tokens: int = 2048,
    temperature: float = 0.7,
    top_p: float = 0.9,
    top_k: int = 50,
    repetition_penalty: float = 1.1,
    presence_penalty: float = 0.0,
    frequency_penalty: float = 0.0
) -> Optional[InferenceTask]:
    """创建推理任务"""
    # 检查模型是否存在
    model = get_resource(resource_id=model_id)
    if not model or model.resource_type != ResourceType.MODEL:
        logger.error(f"模型不存在或类型错误: {model_id}")
        return None
    
    # 检查用户是否存在
    user = get_user_by_id(user_id)
    if not user:
        logger.error(f"用户不存在: {user_id}")
        return None
    
    # 生成任务ID
    task_id = len(inference_tasks_db) + 1
    
    # 创建任务
    task = InferenceTask(
        id=task_id,
        name=name,
        model_id=model_id,
        user_id=user_id,
        status=InferenceStatus.CREATING,
        created_at=datetime.now(),
        share_enabled=share_enabled,
        display_name=display_name,
        tensor_parallel_size=tensor_parallel_size,
        max_model_len=max_model_len,
        quantization=quantization,
        dtype=dtype,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
        repetition_penalty=repetition_penalty,
        presence_penalty=presence_penalty,
        frequency_penalty=frequency_penalty
    )
    
    # 添加到数据库
    inference_tasks_db.append(task.dict())
    save_db()
    
    return task

def get_inference_task(task_id: int) -> Optional[InferenceTask]:
    """获取推理任务"""
    for task_data in inference_tasks_db:
        if task_data["id"] == task_id:
            return InferenceTask(**task_data)
    return None

def get_all_inference_tasks() -> List[InferenceTask]:
    """获取所有推理任务"""
    return [InferenceTask(**task_data) for task_data in inference_tasks_db]

def get_user_inference_tasks(user_id: int) -> List[InferenceTask]:
    """获取用户的推理任务"""
    return [InferenceTask(**task_data) for task_data in inference_tasks_db if task_data["user_id"] == user_id]

def update_inference_task(
    task_id: int,
    status: Optional[InferenceStatus] = None,
    port: Optional[int] = None,
    api_base: Optional[str] = None,
    process_id: Optional[int] = None,
    gpu_memory: Optional[float] = None,
    started_at: Optional[datetime] = None,
    stopped_at: Optional[datetime] = None,
    error_message: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
    top_k: Optional[int] = None,
    repetition_penalty: Optional[float] = None,
    presence_penalty: Optional[float] = None,
    frequency_penalty: Optional[float] = None,
    share_enabled: Optional[bool] = None,
    display_name: Optional[str] = None
) -> Optional[InferenceTask]:
    """更新推理任务"""
    for i, task_data in enumerate(inference_tasks_db):
        if task_data["id"] == task_id:
            # 更新状态
            if status is not None:
                task_data["status"] = status
            
            # 更新端口和API基础URL
            if port is not None:
                task_data["port"] = port
            if api_base is not None:
                task_data["api_base"] = api_base
            if process_id is not None:
                task_data["process_id"] = process_id
            if gpu_memory is not None:
                task_data["gpu_memory"] = gpu_memory
            
            # 更新时间戳
            if started_at is not None:
                task_data["started_at"] = started_at.isoformat()
            if stopped_at is not None:
                task_data["stopped_at"] = stopped_at.isoformat()
            
            # 更新错误信息
            if error_message is not None:
                task_data["error_message"] = error_message
            
            # 更新共享设置
            if share_enabled is not None:
                task_data["share_enabled"] = share_enabled
            if display_name is not None:
                task_data["display_name"] = display_name
            
            # 更新推理参数
            if max_tokens is not None:
                task_data["max_tokens"] = max_tokens
            if temperature is not None:
                task_data["temperature"] = temperature
            if top_p is not None:
                task_data["top_p"] = top_p
            if top_k is not None:
                task_data["top_k"] = top_k
            if repetition_penalty is not None:
                task_data["repetition_penalty"] = repetition_penalty
            if presence_penalty is not None:
                task_data["presence_penalty"] = presence_penalty
            if frequency_penalty is not None:
                task_data["frequency_penalty"] = frequency_penalty
            
            # 保存数据库
            inference_tasks_db[i] = task_data
            save_db()
            
            return InferenceTask(**task_data)
    
    return None

def delete_inference_task(task_id: int) -> bool:
    """删除推理任务"""
    for i, task_data in enumerate(inference_tasks_db):
        if task_data["id"] == task_id:
            inference_tasks_db.pop(i)
            save_db()
            return True
    return False

# ========== 评估任务操作 ==========

def create_evaluation_task(
    task_data: EvaluationTaskCreate, 
    user_id: int
) -> EvaluationTask:
    """
    创建新的评估任务
    """
    # 生成任务ID
    task_id = len(evaluation_tasks_db) + 1
    
    # 创建任务对象
    task_dict = task_data.dict()
    task_dict.update({
        "id": task_id,
        "user_id": user_id,
        "status": EvaluationStatus.PENDING,
        "progress": 0.0,
        "metrics": None,
        "created_at": datetime.now(),
        "started_at": None,
        "completed_at": None,
        "error_message": None
    })
    
    # 添加到数据库
    evaluation_tasks_db.append(task_dict)
    save_db()
    
    # 返回任务对象
    return EvaluationTask(**task_dict)

def get_all_evaluation_tasks() -> List[EvaluationTask]:
    """获取所有评估任务"""
    return [EvaluationTask(**task) for task in evaluation_tasks_db]

def get_user_evaluation_tasks(user_id: int) -> List[EvaluationTask]:
    """获取用户的评估任务"""
    return [EvaluationTask(**task) for task in evaluation_tasks_db if task["user_id"] == user_id]

def get_evaluation_task(task_id: int) -> Optional[EvaluationTask]:
    """通过ID获取评估任务"""
    for task in evaluation_tasks_db:
        if task["id"] == task_id:
            return EvaluationTask(**task)
    return None

def update_evaluation_task(
    task_id: int,
    status: Optional[EvaluationStatus] = None,
    progress: Optional[float] = None,
    metrics: Optional[EvaluationMetrics] = None,
    started_at: Optional[datetime] = None,
    completed_at: Optional[datetime] = None,
    error_message: Optional[str] = None,
    result_path: Optional[str] = None
) -> Optional[EvaluationTask]:
    """更新评估任务状态"""
    # 查找任务
    for i, task in enumerate(evaluation_tasks_db):
        if task["id"] == task_id:
            # 更新状态
            if status is not None:
                evaluation_tasks_db[i]["status"] = status
            
            if progress is not None:
                evaluation_tasks_db[i]["progress"] = progress
            
            if metrics is not None:
                if isinstance(metrics, dict):
                    evaluation_tasks_db[i]["metrics"] = metrics
                else:
                    evaluation_tasks_db[i]["metrics"] = metrics.dict()
            
            if started_at is not None:
                evaluation_tasks_db[i]["started_at"] = started_at
            
            if completed_at is not None:
                evaluation_tasks_db[i]["completed_at"] = completed_at
            
            if error_message is not None:
                evaluation_tasks_db[i]["error_message"] = error_message
                
            if result_path is not None:
                evaluation_tasks_db[i]["result_path"] = result_path
            
            # 保存数据库
            save_db()
            
            # 返回更新后的任务
            return EvaluationTask(**evaluation_tasks_db[i])
    
    # 如果没找到任务
    return None

def delete_evaluation_task(task_id: int) -> bool:
    """删除评估任务"""
    global evaluation_tasks_db
    
    # 找到并移除任务
    for i, task in enumerate(evaluation_tasks_db):
        if task["id"] == task_id:
            evaluation_tasks_db.pop(i)
            save_db()
            
            # 删除评估配置文件
            from evaluation_utils import delete_evaluation_task_config
            delete_evaluation_task_config(task_id)
            
            return True
    
    return False

def start_evaluation_task(task_id: int) -> Optional[EvaluationTask]:
    """启动评估任务"""
    # 获取任务
    task = get_evaluation_task(task_id)
    if not task:
        return None
    
    # 更新任务状态
    updated_task = update_evaluation_task(
        task_id=task_id,
        status=EvaluationStatus.PENDING,
        progress=0.0,
        started_at=datetime.now(),
        completed_at=None,
        error_message=None
    )
    
    # 启动评估任务
    from evaluation_utils import start_evaluation
    start_evaluation(task_id)
    
    return updated_task

def stop_evaluation_task(task_id: int) -> Optional[EvaluationTask]:
    """停止评估任务"""
    # 获取任务
    task = get_evaluation_task(task_id)
    if not task:
        return None
    
    # 停止评估
    from evaluation_utils import stop_evaluation
    stop_evaluation(task_id)
    
    # 更新任务状态
    updated_task = update_evaluation_task(
        task_id=task_id,
        status=EvaluationStatus.STOPPED
    )
    
    return updated_task

def add_evaluation_log(
    task_id: int,
    content: str,
    level: str = "INFO"
) -> EvaluationLogEntry:
    """添加评估日志"""
    # 创建日志条目
    log_entry = {
        "task_id": task_id,
        "timestamp": datetime.now().isoformat(),  # 存储为ISO格式字符串
        "content": content,
        "level": level
    }
    
    # 添加到数据库
    evaluation_logs_db.append(log_entry)
    
    # 如果日志太多，保留最新的10000条
    if len(evaluation_logs_db) > 10000:
        evaluation_logs_db.pop(0)
    
    # 隔一段时间保存一次，避免频繁写入
    if len(evaluation_logs_db) % 100 == 0:
        save_db()

def get_evaluation_logs(task_id: int, limit: int = 100, offset: int = 0) -> List[Dict]:
    """获取评估日志"""
    # 过滤出任务的日志
    task_logs = [log for log in evaluation_logs_db if log["task_id"] == task_id]
    
    # 统一时间戳格式（确保所有时间戳都是字符串类型）
    for log in task_logs:
        if isinstance(log["timestamp"], datetime):
            log["timestamp"] = log["timestamp"].isoformat()
    
    # 按时间排序
    task_logs.sort(key=lambda x: x["timestamp"], reverse=True)
    
    # 应用分页
    paginated_logs = task_logs[offset:offset + limit]
    
    return paginated_logs

def clear_evaluation_logs(task_id: int) -> bool:
    """清除评估日志"""
    global evaluation_logs_db
    
    # 移除任务的日志
    evaluation_logs_db = [log for log in evaluation_logs_db if log["task_id"] != task_id]
    save_db()
    
    return True 