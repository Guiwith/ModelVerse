import os
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from contextlib import contextmanager
from pathlib import Path
from passlib.context import CryptContext
import json
import asyncio

from models import (
    User, UserCreate, UserInDB, ProfileUpdate, 
    Resource, ResourceCreate, ResourceType, DownloadStatus, 
    TrainingTask, TrainingTaskCreate, TrainingStatus, TrainingLogEntry,
    InferenceTask, InferenceStatus,
    EvaluationTask, EvaluationTaskCreate, EvaluationStatus, EvaluationMetrics, EvaluationLogEntry
)

# 密码哈希工具
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 数据库文件名
DB_NAME = "modelverse.db"

def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """初始化数据库表结构"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 创建用户表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        hashed_password TEXT NOT NULL,
        display_name TEXT DEFAULT '',
        phone TEXT DEFAULT '',
        is_admin BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # 创建资源表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS resources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        repo_id TEXT NOT NULL,
        resource_type TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        status TEXT NOT NULL,
        progress REAL DEFAULT 0.0,
        size_mb REAL,
        local_path TEXT,
        error_message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    # 创建训练任务表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS training_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        base_model_id INTEGER NOT NULL,
        dataset_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        status TEXT NOT NULL,
        progress REAL DEFAULT 0.0,
        config_params TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        started_at TIMESTAMP,
        completed_at TIMESTAMP,
        error_message TEXT,
        output_model_path TEXT,
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (base_model_id) REFERENCES resources (id),
        FOREIGN KEY (dataset_id) REFERENCES resources (id)
    )
    ''')
    
    # 创建训练日志表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS training_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER NOT NULL,
        content TEXT NOT NULL,
        level TEXT DEFAULT 'INFO',
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (task_id) REFERENCES training_tasks (id)
    )
    ''')
    
    # 创建推理任务表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS inference_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        model_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        status TEXT NOT NULL,
        port INTEGER,
        api_base TEXT,
        process_id INTEGER,
        gpu_memory REAL,
        share_enabled BOOLEAN DEFAULT FALSE,
        display_name TEXT,
        tensor_parallel_size INTEGER DEFAULT 1,
        max_model_len INTEGER DEFAULT 4096,
        quantization TEXT,
        dtype TEXT DEFAULT 'auto',
        max_tokens INTEGER DEFAULT 2048,
        temperature REAL DEFAULT 0.7,
        top_p REAL DEFAULT 0.9,
        top_k INTEGER DEFAULT 50,
        repetition_penalty REAL DEFAULT 1.1,
        presence_penalty REAL DEFAULT 0.0,
        frequency_penalty REAL DEFAULT 0.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        started_at TIMESTAMP,
        stopped_at TIMESTAMP,
        error_message TEXT,
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (model_id) REFERENCES resources (id)
    )
    ''')
    
    # 创建评估任务表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS evaluation_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        model_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        benchmark_type TEXT NOT NULL,
        status TEXT NOT NULL,
        progress REAL DEFAULT 0.0,
        num_fewshot INTEGER DEFAULT 0,
        custom_dataset_path TEXT,
        metrics TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        started_at TIMESTAMP,
        completed_at TIMESTAMP,
        error_message TEXT,
        result_path TEXT,
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (model_id) REFERENCES resources (id)
    )
    ''')
    
    # 创建评估日志表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS evaluation_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER NOT NULL,
        content TEXT NOT NULL,
        level TEXT DEFAULT 'INFO',
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (task_id) REFERENCES evaluation_tasks (id)
    )
    ''')
    
    # 创建活跃下载任务表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS active_downloads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        resource_id INTEGER NOT NULL,
        pid INTEGER,
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (resource_id) REFERENCES resources (id)
    )
    ''')
    
    conn.commit()
    
    # 创建默认管理员用户（如果不存在）
    if not check_username_exists("admin"):
        admin_user = UserCreate(
            username="admin",
            email="admin@example.com", 
            password="admin123",
            is_admin=True
        )
        create_user(admin_user)
    
    conn.close()

# 密码相关函数
def verify_password(plain_password, hashed_password):
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    """获取密码哈希"""
    return pwd_context.hash(password)

# 用户管理函数
def create_user(user: UserCreate) -> User:
    """创建用户"""
    if check_username_exists(user.username):
        raise Exception("用户名已存在")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    hashed_password = get_password_hash(user.password)
    
    cursor.execute('''
    INSERT INTO users (username, email, hashed_password, display_name, phone, is_admin)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        user.username,
        user.email,
        hashed_password,
        "",  # display_name
        "",  # phone
        user.is_admin
    ))
    
    user_id = cursor.lastrowid
    conn.commit()
    
    # 获取创建的用户
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    
    return User(**dict(user_data))

def get_user_by_username(username: str) -> Optional[UserInDB]:
    """通过用户名获取用户"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    user_data = cursor.fetchone()
    conn.close()
    
    if user_data:
        return UserInDB(**dict(user_data))
    return None

def get_user_by_id(user_id: int) -> Optional[UserInDB]:
    """通过ID获取用户"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    
    if user_data:
        return UserInDB(**dict(user_data))
    return None

def check_username_exists(username: str) -> bool:
    """检查用户名是否存在"""
    return get_user_by_username(username) is not None

def authenticate_user(username: str, password: str) -> Optional[UserInDB]:
    """验证用户"""
    user = get_user_by_username(username)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user

def get_users() -> List[User]:
    """获取所有用户"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users ORDER BY created_at DESC')
    users_data = cursor.fetchall()
    conn.close()
    
    return [User(**dict(user)) for user in users_data]

def update_user_profile(user_id: int, profile_data: ProfileUpdate) -> User:
    """更新用户资料"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 构建更新字段
    update_fields = []
    params = []
    
    if profile_data.display_name is not None:
        update_fields.append("display_name = ?")
        params.append(profile_data.display_name)
    
    if profile_data.email is not None:
        update_fields.append("email = ?")
        params.append(profile_data.email)
    
    if profile_data.phone is not None:
        update_fields.append("phone = ?")
        params.append(profile_data.phone)
    
    if not update_fields:
        raise Exception("没有需要更新的字段")
    
    params.append(user_id)
    query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = ?"
    
    cursor.execute(query, params)
    conn.commit()
    
    # 获取更新后的用户
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    
    if user_data:
        return User(**dict(user_data))
    else:
        raise Exception("用户不存在")

def update_user_password(user_id: int, new_password: str) -> bool:
    """更新用户密码"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    hashed_password = get_password_hash(new_password)
    cursor.execute('UPDATE users SET hashed_password = ? WHERE id = ?', (hashed_password, user_id))
    updated = cursor.rowcount > 0
    
    conn.commit()
    conn.close()
    
    if not updated:
        raise Exception("用户不存在")
    
    return True

def delete_user_by_id(user_id: int) -> bool:
    """删除用户"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
    deleted = cursor.rowcount > 0
    
    conn.commit()
    conn.close()
    
    return deleted

# 资源管理函数
def create_resource(resource_data: ResourceCreate, user_id: int) -> Resource:
    """创建资源"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO resources (name, description, repo_id, resource_type, user_id, status)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        resource_data.name,
        resource_data.description,
        resource_data.repo_id,
        resource_data.resource_type,
        user_id,
        DownloadStatus.PENDING
    ))
    
    resource_id = cursor.lastrowid
    conn.commit()
    
    # 获取创建的资源
    cursor.execute('SELECT * FROM resources WHERE id = ?', (resource_id,))
    resource_data = cursor.fetchone()
    conn.close()
    
    return Resource(**dict(resource_data))

def get_resource(resource_id: int) -> Optional[Resource]:
    """获取单个资源"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM resources WHERE id = ?', (resource_id,))
    resource_data = cursor.fetchone()
    conn.close()
    
    if resource_data:
        return Resource(**dict(resource_data))
    return None

def get_all_resources() -> List[Resource]:
    """获取所有资源"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM resources ORDER BY created_at DESC')
    resources_data = cursor.fetchall()
    conn.close()
    
    return [Resource(**dict(resource)) for resource in resources_data]

def get_user_resources(user_id: int) -> List[Resource]:
    """获取用户资源"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM resources WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
    resources_data = cursor.fetchall()
    conn.close()
    
    return [Resource(**dict(resource)) for resource in resources_data]

def update_resource_status(resource_id: int, status: DownloadStatus, progress: float = None, 
                          error_message: str = None, local_path: str = None, size_mb: float = None) -> Optional[Resource]:
    """更新资源状态"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 构建更新字段
    update_fields = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
    params = [status]
    
    if progress is not None:
        update_fields.append("progress = ?")
        params.append(progress)
    
    if error_message is not None:
        update_fields.append("error_message = ?")
        params.append(error_message)
    
    if local_path is not None:
        update_fields.append("local_path = ?")
        params.append(local_path)
    
    if size_mb is not None:
        update_fields.append("size_mb = ?")
        params.append(size_mb)
    
    params.append(resource_id)
    query = f"UPDATE resources SET {', '.join(update_fields)} WHERE id = ?"
    
    cursor.execute(query, params)
    conn.commit()
    conn.close()
    
    # 获取更新后的资源
    updated_resource = get_resource(resource_id)
    
    # 发送WebSocket通知
    try:
        # 动态导入以避免循环导入
        from training_utils import broadcast_resource_update
        
        # 构建通知消息
        message = {
            "type": "resource_update",
            "resource_id": resource_id,
            "status": status,
        }
        
        if progress is not None:
            message["progress"] = progress
        if error_message is not None:
            message["error_message"] = error_message
        
        # 发送WebSocket通知，处理事件循环问题
        try:
            # 检查是否有运行中的事件循环
            loop = asyncio.get_running_loop()
            # 如果有运行中的事件循环，使用create_task
            loop.create_task(broadcast_resource_update(message))
        except RuntimeError:
            # 没有运行中的事件循环，在新线程中运行
            import threading
            
            def run_in_thread():
                try:
                    asyncio.run(broadcast_resource_update(message))
                except Exception as e:
                    print(f"线程中WebSocket通知失败: {e}")
            
            thread = threading.Thread(target=run_in_thread, daemon=True)
            thread.start()
            
    except Exception as e:
        # 如果WebSocket通知失败，记录错误但不影响主要功能
        print(f"发送WebSocket通知失败: {e}")
    
    return updated_resource

def delete_resource(resource_id: int) -> bool:
    """删除资源"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM resources WHERE id = ?', (resource_id,))
    deleted = cursor.rowcount > 0
    
    conn.commit()
    conn.close()
    
    return deleted

# 训练任务管理函数
def create_training_task(task_data: TrainingTaskCreate, user_id: int) -> TrainingTask:
    """创建训练任务"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    config_params_json = json.dumps(task_data.config_params) if task_data.config_params else None
    
    cursor.execute('''
    INSERT INTO training_tasks (name, base_model_id, dataset_id, user_id, status, config_params)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        task_data.name,
        task_data.base_model_id,
        task_data.dataset_id,
        user_id,
        TrainingStatus.PENDING,
        config_params_json
    ))
    
    task_id = cursor.lastrowid
    conn.commit()
    
    # 获取创建的任务
    cursor.execute('SELECT * FROM training_tasks WHERE id = ?', (task_id,))
    task_data = cursor.fetchone()
    conn.close()
    
    return TrainingTask(**dict(task_data))

def get_training_task(task_id: int) -> Optional[TrainingTask]:
    """获取训练任务"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM training_tasks WHERE id = ?', (task_id,))
    task_data = cursor.fetchone()
    conn.close()
    
    if task_data:
        return TrainingTask(**dict(task_data))
    return None

def get_all_training_tasks() -> List[TrainingTask]:
    """获取所有训练任务"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM training_tasks ORDER BY created_at DESC')
    tasks_data = cursor.fetchall()
    conn.close()
    
    return [TrainingTask(**dict(task)) for task in tasks_data]

def get_user_training_tasks(user_id: int) -> List[TrainingTask]:
    """获取用户训练任务"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM training_tasks WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
    tasks_data = cursor.fetchall()
    conn.close()
    
    return [TrainingTask(**dict(task)) for task in tasks_data]

def update_training_task(task_id: int, **kwargs) -> Optional[TrainingTask]:
    """更新训练任务"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 构建更新字段
    update_fields = []
    params = []
    
    for key, value in kwargs.items():
        if value is not None:
            if key == "config_params":
                update_fields.append(f"{key} = ?")
                params.append(json.dumps(value))
            else:
                update_fields.append(f"{key} = ?")
                params.append(value)
    
    if not update_fields:
        return get_training_task(task_id)
    
    params.append(task_id)
    query = f"UPDATE training_tasks SET {', '.join(update_fields)} WHERE id = ?"
    
    cursor.execute(query, params)
    conn.commit()
    conn.close()
    
    return get_training_task(task_id)

def delete_training_task(task_id: int) -> bool:
    """删除训练任务"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 删除相关日志
    cursor.execute('DELETE FROM training_logs WHERE task_id = ?', (task_id,))
    # 删除任务
    cursor.execute('DELETE FROM training_tasks WHERE id = ?', (task_id,))
    
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    return deleted

def add_training_log(task_id: int, content: str, level: str = "INFO"):
    """添加训练日志"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO training_logs (task_id, content, level)
    VALUES (?, ?, ?)
    ''', (task_id, content, level))
    
    conn.commit()
    conn.close()

def get_training_logs(task_id: int, limit: int = 100, offset: int = 0) -> List[Dict]:
    """获取训练日志"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT * FROM training_logs 
    WHERE task_id = ? 
    ORDER BY timestamp DESC 
    LIMIT ? OFFSET ?
    ''', (task_id, limit, offset))
    
    logs_data = cursor.fetchall()
    conn.close()
    
    return [dict(log) for log in logs_data]

def clear_training_logs(task_id: int) -> bool:
    """清除训练日志"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM training_logs WHERE task_id = ?', (task_id,))
    deleted = cursor.rowcount > 0
    
    conn.commit()
    conn.close()
    
    return deleted

# 推理任务管理函数
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
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO inference_tasks (
        name, model_id, user_id, status, share_enabled, display_name,
        tensor_parallel_size, max_model_len, quantization, dtype,
        max_tokens, temperature, top_p, top_k, repetition_penalty,
        presence_penalty, frequency_penalty
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        name, model_id, user_id, InferenceStatus.CREATING, share_enabled, display_name,
        tensor_parallel_size, max_model_len, quantization, dtype,
        max_tokens, temperature, top_p, top_k, repetition_penalty,
        presence_penalty, frequency_penalty
    ))
    
    task_id = cursor.lastrowid
    conn.commit()
    
    # 获取创建的任务
    cursor.execute('SELECT * FROM inference_tasks WHERE id = ?', (task_id,))
    task_data = cursor.fetchone()
    conn.close()
    
    if task_data:
        return InferenceTask(**dict(task_data))
    return None

def get_inference_task(task_id: int) -> Optional[InferenceTask]:
    """获取推理任务"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM inference_tasks WHERE id = ?', (task_id,))
    task_data = cursor.fetchone()
    conn.close()
    
    if task_data:
        return InferenceTask(**dict(task_data))
    return None

def get_all_inference_tasks() -> List[InferenceTask]:
    """获取所有推理任务"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM inference_tasks ORDER BY created_at DESC')
    tasks_data = cursor.fetchall()
    conn.close()
    
    return [InferenceTask(**dict(task)) for task in tasks_data]

def get_user_inference_tasks(user_id: int) -> List[InferenceTask]:
    """获取用户推理任务"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM inference_tasks WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
    tasks_data = cursor.fetchall()
    conn.close()
    
    return [InferenceTask(**dict(task)) for task in tasks_data]

def update_inference_task(task_id: int, **kwargs) -> Optional[InferenceTask]:
    """更新推理任务"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 构建更新字段
    update_fields = []
    params = []
    
    for key, value in kwargs.items():
        if value is not None:
            update_fields.append(f"{key} = ?")
            params.append(value)
    
    if not update_fields:
        return get_inference_task(task_id)
    
    params.append(task_id)
    query = f"UPDATE inference_tasks SET {', '.join(update_fields)} WHERE id = ?"
    
    cursor.execute(query, params)
    conn.commit()
    conn.close()
    
    return get_inference_task(task_id)

def delete_inference_task(task_id: int) -> bool:
    """删除推理任务"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM inference_tasks WHERE id = ?', (task_id,))
    deleted = cursor.rowcount > 0
    
    conn.commit()
    conn.close()
    
    return deleted

# 评估任务管理函数
def _process_evaluation_task_data(task_data) -> EvaluationTask:
    """处理评估任务数据，包括metrics字段的JSON反序列化"""
    task_dict = dict(task_data)
    # 处理metrics字段的JSON反序列化
    if task_dict.get('metrics'):
        try:
            metrics_data = json.loads(task_dict['metrics'])
            from models import EvaluationMetrics
            task_dict['metrics'] = EvaluationMetrics(**metrics_data)
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            print(f"解析metrics失败: {str(e)}")
            task_dict['metrics'] = None
    return EvaluationTask(**task_dict)

def create_evaluation_task(task_data: EvaluationTaskCreate, user_id: int) -> EvaluationTask:
    """创建评估任务"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO evaluation_tasks (name, model_id, user_id, benchmark_type, status, num_fewshot, custom_dataset_path)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        task_data.name,
        task_data.model_id,
        user_id,
        task_data.benchmark_type,
        EvaluationStatus.PENDING,
        task_data.num_fewshot,
        task_data.custom_dataset_path
    ))
    
    task_id = cursor.lastrowid
    conn.commit()
    
    # 获取创建的任务
    cursor.execute('SELECT * FROM evaluation_tasks WHERE id = ?', (task_id,))
    task_data = cursor.fetchone()
    conn.close()
    
    return EvaluationTask(**dict(task_data))

def get_evaluation_task(task_id: int) -> Optional[EvaluationTask]:
    """获取评估任务"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM evaluation_tasks WHERE id = ?', (task_id,))
    task_data = cursor.fetchone()
    conn.close()
    
    if task_data:
        return _process_evaluation_task_data(task_data)
    return None

def get_all_evaluation_tasks() -> List[EvaluationTask]:
    """获取所有评估任务"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM evaluation_tasks ORDER BY created_at DESC')
    tasks_data = cursor.fetchall()
    conn.close()
    
    return [_process_evaluation_task_data(task) for task in tasks_data]

def get_user_evaluation_tasks(user_id: int) -> List[EvaluationTask]:
    """获取用户评估任务"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM evaluation_tasks WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
    tasks_data = cursor.fetchall()
    conn.close()
    
    return [_process_evaluation_task_data(task) for task in tasks_data]

def update_evaluation_task(task_id: int, **kwargs) -> Optional[EvaluationTask]:
    """更新评估任务"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 构建更新字段
    update_fields = []
    params = []
    
    for key, value in kwargs.items():
        if value is not None:
            if key == "metrics":
                update_fields.append(f"{key} = ?")
                params.append(json.dumps(value))
            else:
                update_fields.append(f"{key} = ?")
                params.append(value)
    
    if not update_fields:
        return get_evaluation_task(task_id)
    
    params.append(task_id)
    query = f"UPDATE evaluation_tasks SET {', '.join(update_fields)} WHERE id = ?"
    
    cursor.execute(query, params)
    conn.commit()
    conn.close()
    
    return get_evaluation_task(task_id)

def delete_evaluation_task(task_id: int) -> bool:
    """删除评估任务"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 删除相关日志
    cursor.execute('DELETE FROM evaluation_logs WHERE task_id = ?', (task_id,))
    # 删除任务
    cursor.execute('DELETE FROM evaluation_tasks WHERE id = ?', (task_id,))
    
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    return deleted

def start_evaluation_task(task_id: int) -> Optional[EvaluationTask]:
    """开始评估任务"""
    # 更新任务状态
    task = update_evaluation_task(
        task_id,
        status=EvaluationStatus.RUNNING,
        started_at=datetime.now()
    )
    
    # 实际启动评估流程
    if task:
        try:
            import evaluation_utils
            # 将任务添加到运行中的任务字典
            evaluation_utils.running_evaluations[task_id] = True
            evaluation_utils.start_evaluation(task_id)
        except Exception as e:
            # 如果启动失败，更新状态为失败并清理运行状态
            import evaluation_utils
            if task_id in evaluation_utils.running_evaluations:
                del evaluation_utils.running_evaluations[task_id]
            task = update_evaluation_task(
                task_id,
                status=EvaluationStatus.FAILED,
                error_message=f"启动评估失败: {str(e)}",
                completed_at=datetime.now()
            )
    
    return task

def stop_evaluation_task(task_id: int) -> Optional[EvaluationTask]:
    """停止评估任务"""
    # 实际停止评估流程
    try:
        import evaluation_utils
        evaluation_utils.stop_evaluation(task_id)
    except Exception as e:
        print(f"停止评估流程失败: {str(e)}")
    
    # 更新任务状态
    return update_evaluation_task(
        task_id,
        status=EvaluationStatus.STOPPED,
        stopped_at=datetime.now()
    )

def add_evaluation_log(task_id: int, content: str, level: str = "INFO") -> EvaluationLogEntry:
    """添加评估日志"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO evaluation_logs (task_id, content, level)
    VALUES (?, ?, ?)
    ''', (task_id, content, level))
    
    log_id = cursor.lastrowid
    conn.commit()
    
    # 获取创建的日志
    cursor.execute('SELECT * FROM evaluation_logs WHERE id = ?', (log_id,))
    log_data = cursor.fetchone()
    conn.close()
    
    return EvaluationLogEntry(**dict(log_data))

def get_evaluation_logs(task_id: int, limit: int = 100, offset: int = 0) -> List[Dict]:
    """获取评估日志"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT * FROM evaluation_logs 
    WHERE task_id = ? 
    ORDER BY timestamp DESC 
    LIMIT ? OFFSET ?
    ''', (task_id, limit, offset))
    
    logs_data = cursor.fetchall()
    conn.close()
    
    return [dict(log) for log in logs_data]

def clear_evaluation_logs(task_id: int) -> bool:
    """清除评估日志"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM evaluation_logs WHERE task_id = ?', (task_id,))
    deleted = cursor.rowcount > 0
    
    conn.commit()
    conn.close()
    
    return deleted

# 下载任务管理函数
def register_download_task(resource_id: int, pid: int) -> int:
    """记录活跃下载任务"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO active_downloads (resource_id, pid)
    VALUES (?, ?)
    ''', (resource_id, pid))
    
    download_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return download_id

def remove_download_task(resource_id: int) -> None:
    """移除下载任务记录"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM active_downloads WHERE resource_id = ?', (resource_id,))
    conn.commit()
    conn.close()

def get_active_downloads() -> List[Dict[str, Any]]:
    """获取所有活跃下载任务"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT ad.*, r.name, r.repo_id, r.resource_type, r.user_id, r.progress, r.status, u.username
    FROM active_downloads ad
    JOIN resources r ON ad.resource_id = r.id
    JOIN users u ON r.user_id = u.id
    ORDER BY ad.started_at DESC
    ''')
    
    downloads = cursor.fetchall()
    conn.close()
    
    return [dict(download) for download in downloads]

def get_download_task(resource_id: int) -> Optional[Dict[str, Any]]:
    """获取资源的下载任务信息"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM active_downloads WHERE resource_id = ?', (resource_id,))
    task = cursor.fetchone()
    conn.close()
    
    return dict(task) if task else None

# 兼容性函数（保持与原database.py的API兼容）
def save_db():
    """保存数据库（SQLite自动保存，这里保持兼容性）"""
    pass 