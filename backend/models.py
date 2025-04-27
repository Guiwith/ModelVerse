from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class UserBase(BaseModel):
    username: str
    email: Optional[str] = None
    is_admin: bool = False

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    disabled: bool = False
    created_at: datetime
    
    class Config:
        from_attributes = True

class UserInDB(User):
    hashed_password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    is_admin: bool = False

class UserRegister(BaseModel):
    username: str
    password: str
    captcha: str
    captcha_id: str
    
class ProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    
class PasswordChange(BaseModel):
    current_password: str
    new_password: str

# 模型和数据集相关的数据模型
class ResourceType(str, Enum):
    MODEL = "MODEL"
    DATASET = "DATASET"

class DownloadStatus(str, Enum):
    PENDING = "PENDING"
    DOWNLOADING = "DOWNLOADING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class ResourceCreate(BaseModel):
    name: str = Field(..., description="资源名称")
    description: Optional[str] = Field(None, description="资源描述")
    repo_id: str = Field(..., description="仓库ID，例如：'facebook/opt-350m'")
    resource_type: ResourceType = Field(..., description="资源类型: model或dataset")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "OPT-350M",
                "description": "Facebook的开源大语言模型",
                "repo_id": "facebook/opt-350m",
                "resource_type": "model"
            }
        }

class Resource(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    repo_id: str
    resource_type: ResourceType
    user_id: int
    status: DownloadStatus
    progress: float = 0.0
    size_mb: Optional[float] = None
    local_path: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class MirrorSource(str, Enum):
    OFFICIAL = "OFFICIAL"
    MODELSCOPE = "MODELSCOPE"
    MIRROR_CN = "MIRROR_CN"

class DownloadRequest(BaseModel):
    source: MirrorSource = MirrorSource.OFFICIAL

class DownloadProgress(BaseModel):
    resource_id: int
    status: DownloadStatus
    progress: float
    message: Optional[str] = None

# 训练相关的数据模型
class TrainingStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    STOPPED = "STOPPED"

class ModelConfigCreate(BaseModel):
    max_length: int = 2048
    torch_dtype_str: str = "bfloat16"
    attn_implementation: str = "sdpa"
    load_pretrained_weights: bool = True
    trust_remote_code: bool = True

class DataConfigCreate(BaseModel):
    target_col: str = "prompt"

class TrainingParamsCreate(BaseModel):
    trainer_type: str = "TRL_SFT"
    save_final_model: bool = True
    save_steps: int = 100
    max_steps: int = 10
    per_device_train_batch_size: int = 4
    gradient_accumulation_steps: int = 4
    ddp_find_unused_parameters: bool = False
    optimizer: str = "adamw_torch"
    learning_rate: float = 2.0e-05
    compile: bool = False
    dataloader_num_workers: str = "auto"
    dataloader_prefetch_factor: int = 32
    seed: int = 192847
    use_deterministic: bool = True
    logging_steps: int = 5
    log_model_summary: bool = False
    empty_device_cache_steps: int = 50
    include_performance_metrics: bool = True

class TrainingConfigCreate(BaseModel):
    model: ModelConfigCreate
    data: DataConfigCreate
    training: TrainingParamsCreate

class TrainingTaskCreate(BaseModel):
    name: str
    base_model_id: int
    dataset_id: int
    config_params: Dict[str, Any] = Field(default_factory=dict)

class TrainingTask(BaseModel):
    id: int
    name: str
    base_model_id: int
    dataset_id: int
    user_id: int
    status: TrainingStatus
    progress: float = 0.0
    config_path: Optional[str] = None
    output_path: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    config_params: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        from_attributes = True

class TrainingLogEntry(BaseModel):
    task_id: int
    timestamp: datetime
    content: str
    level: str = "INFO"

class InferenceStatus(str, Enum):
    """推理任务状态"""
    CREATING = "CREATING"  # 创建中
    RUNNING = "RUNNING"    # 运行中
    STOPPED = "STOPPED"    # 已停止
    FAILED = "FAILED"      # 失败

class InferenceTask(BaseModel):
    """推理任务模型"""
    id: Optional[int] = None
    name: str
    model_id: int
    user_id: int
    status: InferenceStatus = InferenceStatus.CREATING
    port: Optional[int] = None
    api_base: Optional[str] = None
    process_id: Optional[int] = None
    gpu_memory: Optional[float] = None  # 显存占用（GB）
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    # 分享功能
    share_enabled: bool = False
    display_name: Optional[str] = None
    
    # vLLM参数
    tensor_parallel_size: int = 1
    max_model_len: int = 4096
    quantization: Optional[str] = None  # awq, gptq, None
    dtype: str = "auto"
    
    # 推理参数
    max_tokens: int = 2048
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 50
    repetition_penalty: float = 1.1
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0
    
    model_config = {
        'from_attributes': True,
        'protected_namespaces': ()
    }
        
class InferenceTaskCreate(BaseModel):
    """创建推理任务请求"""
    name: str
    model_id: int
    share_enabled: Optional[bool] = False
    display_name: Optional[str] = None
    tensor_parallel_size: Optional[int] = 1
    max_model_len: Optional[int] = 4096
    quantization: Optional[str] = None
    dtype: Optional[str] = "auto"
    max_tokens: Optional[int] = 2048
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.9
    top_k: Optional[int] = 50
    repetition_penalty: Optional[float] = 1.1
    presence_penalty: Optional[float] = 0.0
    frequency_penalty: Optional[float] = 0.0
    
    model_config = {'protected_namespaces': ()}

class InferenceTaskUpdate(BaseModel):
    """更新推理任务请求"""
    status: Optional[InferenceStatus] = None
    port: Optional[int] = None
    api_base: Optional[str] = None
    process_id: Optional[int] = None
    gpu_memory: Optional[float] = None
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    error_message: Optional[str] = None
    share_enabled: Optional[bool] = None
    display_name: Optional[str] = None
    
    # 推理参数
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    repetition_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    
class Message(BaseModel):
    """聊天消息"""
    role: str  # "user" 或 "assistant"
    content: str
    
class ChatRequest(BaseModel):
    """聊天请求"""
    messages: List[Message]
    task_id: int
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None
    repetition_penalty: Optional[float] = None
    
class ChatResponse(BaseModel):
    """聊天响应"""
    message: Message
    task_id: int
    
class GPUInfo(BaseModel):
    """GPU信息"""
    id: int
    name: str
    memory_total: float  # GB
    memory_used: float   # GB
    memory_free: float   # GB

# 评估相关的数据模型
class EvaluationStatus(str, Enum):
    """评估任务状态"""
    PENDING = "PENDING"    # 等待中
    RUNNING = "RUNNING"    # 运行中
    COMPLETED = "COMPLETED"  # 已完成
    FAILED = "FAILED"      # 失败
    STOPPED = "STOPPED"    # 已停止

class BenchmarkType(str, Enum):
    """基准测试类型"""
    # 问答和知识检索
    BOOLQ = "boolq"                  # 布尔问题
    TRIVIAQA = "triviaqa"            # 琐事问答
    COQA = "coqa"                    # 对话式问答
    NATURAL_QUESTIONS = "nq_open"    # 自然问题
    SQUADV2 = "squadv2"              # Stanford问答数据集V2
    GPQA = "gpqa"                    # Google-Proof Q&A
    ARC_CHALLENGE = "arc_challenge"  # AI2推理挑战
    MMLU = "mmlu"                    # 大规模多任务语言理解
    MMLU_PRO = "mmlu_pro"            # 增强版MMLU
    TRUTHFUL_QA = "truthful_qa"      # 真实问答
    
    # 常识和逻辑推理
    HELLASWAG = "hellaswag"          # 常识推理
    PIQA = "piqa"                    # 物理常识推理
    WINOGRANDE = "winogrande"        # 推断代词引用

    # 语言理解
    WIC = "wic"                      # 上下文中的词汇
    RTE = "rte"                      # 文本蕴含识别
    LAMBADA = "lambada"              # 语言建模扩展到话语方面
    
    # 数学和数值推理
    MATH = "leaderboard_math_hard"   # 数学能力测试
    GSM8K = "gsm8k"                  # 小学水平数学问题
    
    # 自定义测试
    CUSTOM = "custom"                # 自定义测试

class EvaluationMetrics(BaseModel):
    """评估指标"""
    accuracy: Optional[float] = None
    f1_score: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    perplexity: Optional[float] = None
    bleu: Optional[float] = None
    rouge: Optional[float] = None
    exact_match: Optional[float] = None
    custom_metrics: Dict[str, Any] = Field(default_factory=dict)

class EvaluationTaskCreate(BaseModel):
    """创建评估任务请求"""
    name: str
    model_id: int
    benchmark_type: BenchmarkType
    num_fewshot: Optional[int] = 0
    custom_dataset_path: Optional[str] = None  # 仅当benchmark_type为CUSTOM时使用
    
    model_config = {'protected_namespaces': ()}

class EvaluationTask(BaseModel):
    """评估任务模型"""
    id: int
    name: str
    model_id: int
    user_id: int
    benchmark_type: BenchmarkType
    num_fewshot: int = 0
    custom_dataset_path: Optional[str] = None
    status: EvaluationStatus = EvaluationStatus.PENDING
    progress: float = 0.0
    metrics: Optional[EvaluationMetrics] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    result_path: Optional[str] = None  # 评估结果路径
    
    model_config = {
        'from_attributes': True,
        'protected_namespaces': ()
    }

class EvaluationLogEntry(BaseModel):
    """评估日志条目"""
    task_id: int
    timestamp: datetime
    content: str
    level: str = "INFO" 