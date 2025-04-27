import os
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from contextlib import contextmanager

from models import RegisterRequest, UserResponse, User, UserRole, LoginRequest, ResourceCreate, ResourceType, DownloadStatus

def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect('modelverse.db')
    conn.row_factory = sqlite3.Row
    return conn

# 数据库初始化和连接
def init_db():
    # 创建数据库连接
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 创建用户表...
    # ... existing code ...
    
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
        created_at TIMESTAMP NOT NULL,
        updated_at TIMESTAMP NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    # 创建活跃下载任务表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS active_downloads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        resource_id INTEGER NOT NULL,
        pid INTEGER,
        started_at TIMESTAMP NOT NULL,
        FOREIGN KEY (resource_id) REFERENCES resources (id)
    )
    ''')
    
    conn.commit()

# 资源相关操作
def create_resource(resource: ResourceCreate, user_id: int) -> int:
    """创建新资源"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    now = datetime.now()
    cursor.execute(
        '''INSERT INTO resources (name, description, repo_id, resource_type, user_id, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (
            resource.name,
            resource.description,
            resource.repo_id,
            resource.resource_type,
            user_id,
            DownloadStatus.PENDING,
            now,
            now
        )
    )
    resource_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return resource_id

def get_resource(resource_id: int) -> Dict[str, Any]:
    """获取单个资源信息"""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM resources WHERE id = ?', (resource_id,))
    resource = cursor.fetchone()
    
    conn.close()
    return dict(resource) if resource else None

def get_resources_by_user(user_id: int) -> List[Dict[str, Any]]:
    """获取用户所有的资源"""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM resources WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
    resources = cursor.fetchall()
    
    conn.close()
    return [dict(resource) for resource in resources]

def get_all_resources() -> List[Dict[str, Any]]:
    """获取所有资源(管理员用)"""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT r.*, u.username as username FROM resources r JOIN users u ON r.user_id = u.id ORDER BY r.created_at DESC')
    resources = cursor.fetchall()
    
    conn.close()
    return [dict(resource) for resource in resources]

def update_resource_status(resource_id: int, status: DownloadStatus, progress: float = None, size_mb: float = None, 
                           local_path: str = None, error_message: str = None) -> None:
    """更新资源状态"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    set_clauses = ["status = ?", "updated_at = ?"]
    params = [status, datetime.now()]
    
    if progress is not None:
        set_clauses.append("progress = ?")
        params.append(progress)
    
    if size_mb is not None:
        set_clauses.append("size_mb = ?")
        params.append(size_mb)
    
    if local_path is not None:
        set_clauses.append("local_path = ?")
        params.append(local_path)
    
    if error_message is not None:
        set_clauses.append("error_message = ?")
        params.append(error_message)
    
    query = f"UPDATE resources SET {', '.join(set_clauses)} WHERE id = ?"
    params.append(resource_id)
    
    cursor.execute(query, params)
    conn.commit()
    conn.close()

def delete_resource(resource_id: int) -> bool:
    """删除资源"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM resources WHERE id = ?', (resource_id,))
    deleted = cursor.rowcount > 0
    
    conn.commit()
    conn.close()
    return deleted

# 下载任务操作
def register_download_task(resource_id: int, pid: int) -> int:
    """记录活跃下载任务"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        'INSERT INTO active_downloads (resource_id, pid, started_at) VALUES (?, ?, ?)',
        (resource_id, pid, datetime.now())
    )
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
    conn.row_factory = sqlite3.Row
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

def get_download_task(resource_id: int) -> Dict[str, Any]:
    """获取资源的下载任务信息"""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM active_downloads WHERE resource_id = ?', (resource_id,))
    task = cursor.fetchone()
    
    conn.close()
    return dict(task) if task else None 