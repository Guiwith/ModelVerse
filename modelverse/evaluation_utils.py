import os
import json
import subprocess
import logging
import threading
import time
import yaml
import sys
import shutil
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Union
from models import EvaluationTask, EvaluationStatus, BenchmarkType, EvaluationMetrics
from database import get_evaluation_task, update_evaluation_task, add_evaluation_log, get_resource
import numpy as np
import random
import traceback
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from datasets import load_dataset

# 配置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 评估任务进行中的字典
running_evaluations = {}

# 评估配置目录
EVALUATION_CONFIGS_DIR = "evaluation_configs"
# 自定义数据集目录
DATASETS_DIR = "datasets"
# 评估结果目录
EVALUATION_RESULTS_DIR = "evaluation_results"
# 数据集缓存目录
HF_DATASETS_CACHE_DIR = "datasets_cache"

# 支持的数据集列表
SUPPORTED_DATASETS = {
    "mmlu": {
        "name": "MMLU (多任务语言理解基准测试)",
        "hf_path": "cais/mmlu",
        "description": "涵盖57个学科的多项选择题集合，包括人文学科、社会科学、STEM和其他领域",
        "size_mb": 15,
        "url": "https://huggingface.co/datasets/cais/mmlu"
    }
}

# 在配置部分添加默认配置常量
MMLU_EVALUATION_CONFIG = {
    "max_new_tokens": 32,
    "temperature": 0.01,
    "use_default_model_params": True,  # 是否优先使用模型自带参数
    "generation_params": {
        "temperature": 0.01,        # 低温度，减少随机性
        "top_p": 0.95,              # 稍微放宽筛选
        "do_sample": False,         # 关闭采样，使用贪婪解码
        "num_return_sequences": 1,
        "repetition_penalty": 1.2   # 增强对重复的惩罚
    }
}

def get_model_path_from_id(model_id: int) -> Optional[str]:
    """根据模型ID获取模型路径"""
    model_resource = get_resource(model_id)
    if not model_resource:
        return None
    
    if not model_resource.local_path:
        return None
    
    return model_resource.local_path

def get_dataset_cache_path() -> str:
    """获取数据集缓存目录的绝对路径"""
    current_dir = os.path.abspath(os.getcwd())
    cache_dir = os.path.join(current_dir, HF_DATASETS_CACHE_DIR)
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir

def download_dataset(dataset_id: str, mirror: bool = True) -> Tuple[bool, str]:
    """
    下载并缓存数据集
    
    Args:
        dataset_id: 数据集ID，必须在SUPPORTED_DATASETS中
        mirror: 是否使用国内镜像
        
    Returns:
        (成功状态, 消息)
    """
    if dataset_id not in SUPPORTED_DATASETS:
        return False, f"不支持的数据集: {dataset_id}"
    
    cache_dir = get_dataset_cache_path()
    dataset_info = SUPPORTED_DATASETS[dataset_id]
    
    try:
        # 设置环境变量
        os.environ["HF_DATASETS_CACHE"] = cache_dir
        os.environ["TRANSFORMERS_CACHE"] = cache_dir
        os.environ["HF_DATASETS_TRUST_REMOTE_CODE"] = "1"
        os.environ["TRANSFORMERS_TRUST_REMOTE_CODE"] = "1"
        
        # 如果使用镜像
        if mirror:
            os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
        
        # 使用datasets库加载数据集
        from datasets import load_dataset
        
        logger.info(f"开始下载数据集: {dataset_info['hf_path']}")
        
        # 加载数据集（会自动缓存）
        # 对于MMLU，使用'all'配置
        if dataset_id == "mmlu":
            dataset = load_dataset(dataset_info['hf_path'], "all", trust_remote_code=True)
        else:
            dataset = load_dataset(dataset_info['hf_path'], trust_remote_code=True)
        
        # 触发下载
        if isinstance(dataset, dict):
            for split_name, split_data in dataset.items():
                logger.info(f"获取数据集{dataset_info['hf_path']}的{split_name}部分")
                if hasattr(split_data, "take"):
                    sample = split_data.take(1)
        else:
            logger.info(f"获取数据集{dataset_info['hf_path']}的样本")
            if hasattr(dataset, "take"):
                sample = dataset.take(1)
        
        logger.info(f"数据集{dataset_info['hf_path']}已成功下载和缓存")
        return True, f"数据集{dataset_id}已成功下载和缓存"
    
    except Exception as e:
        error_msg = f"下载数据集{dataset_id}失败: {str(e)}"
        logger.error(error_msg)
        return False, error_msg

def list_cached_datasets() -> List[Dict[str, Any]]:
    """列出已缓存的数据集"""
    cache_dir = get_dataset_cache_path()
    cached_datasets = []
    
    for dataset_id, dataset_info in SUPPORTED_DATASETS.items():
        # 根据数据集ID检查缓存目录中是否存在相应的文件夹
        dataset_path = os.path.join(cache_dir, "datasets", dataset_info['hf_path'].replace('/', '--'))
        is_cached = os.path.exists(dataset_path)
        
        if is_cached:
            # 获取文件夹大小
            size_bytes = 0
            for path, dirs, files in os.walk(dataset_path):
                for f in files:
                    fp = os.path.join(path, f)
                    if os.path.exists(fp):
                        size_bytes += os.path.getsize(fp)
            
            # 计算以MB为单位的大小
            size_mb = size_bytes / (1024 * 1024)
            
            cached_datasets.append({
                "id": dataset_id,
                "name": dataset_info["name"],
                "hf_path": dataset_info["hf_path"],
                "description": dataset_info["description"],
                "size_mb": size_mb,
                "is_cached": is_cached
            })
    
    return cached_datasets

def clear_dataset_cache(dataset_id: Optional[str] = None) -> Tuple[bool, str]:
    """
    清理数据集缓存
    
    Args:
        dataset_id: 可选，指定要清理的数据集ID。如果为None，则清理所有缓存
        
    Returns:
        (成功状态, 消息)
    """
    cache_dir = get_dataset_cache_path()
    
    try:
        if dataset_id:
            # 清理指定数据集
            if dataset_id not in SUPPORTED_DATASETS:
                return False, f"不支持的数据集: {dataset_id}"
            
            dataset_info = SUPPORTED_DATASETS[dataset_id]
            dataset_path = os.path.join(cache_dir, "datasets", dataset_info['hf_path'].replace('/', '--'))
            
            if os.path.exists(dataset_path):
                shutil.rmtree(dataset_path)
                return True, f"数据集{dataset_id}缓存已清理"
            else:
                return False, f"数据集{dataset_id}未缓存"
        else:
            # 清理所有缓存
            if os.path.exists(cache_dir):
                shutil.rmtree(cache_dir)
                os.makedirs(cache_dir, exist_ok=True)
                return True, "所有数据集缓存已清理"
            else:
                return False, "缓存目录不存在"
    except Exception as e:
        error_msg = f"清理缓存失败: {str(e)}"
        logger.error(error_msg)
        return False, error_msg

def create_evaluation_config(task: EvaluationTask) -> Tuple[str, str, str]:
    """创建评估配置文件"""
    model_path = get_model_path_from_id(task.model_id)
    if not model_path:
        raise ValueError(f"未找到模型ID {task.model_id} 对应的本地路径")
    
    # 使用绝对路径
    current_dir = os.path.abspath(os.getcwd())
    
    # 确保配置目录存在
    config_dir = os.path.join(current_dir, EVALUATION_CONFIGS_DIR)
    os.makedirs(config_dir, exist_ok=True)
    
    # 创建配置文件的路径
    config_path = os.path.join(config_dir, f"task_{task.id}.json")
    
    # 创建输出目录
    output_dir = os.path.join(current_dir, EVALUATION_RESULTS_DIR, f"task_{task.id}_{int(time.time())}")
    os.makedirs(output_dir, exist_ok=True)
    
    # 创建评估配置
    config = {
        "model_path": model_path,
        "task_id": task.id,
        "task_name": task.name,
        "benchmark_type": task.benchmark_type,
        "output_dir": output_dir,
        "parameters": {
            # 基本生成参数
            "max_new_tokens": 32,
            "temperature": 0.01,
            "use_default_model_params": True,
            
            # 详细的生成参数（仅在use_default_model_params=False时使用）
            "generation_params": {
                "temperature": 0.01,      # 降低温度，减少随机性
                "top_p": 0.95,            # 稍微放宽筛选
                "do_sample": False,       # 关闭采样，使用贪婪解码
                "num_return_sequences": 1,
                "repetition_penalty": 1.2 # 增强对重复的惩罚
            }
        }
    }
    
    # 写入配置文件
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    # 添加日志
    add_evaluation_log(task.id, f"生成的评估配置内容:\n{json.dumps(config, indent=2)}")
    
    return config_path, output_dir, model_path

def parse_metrics_from_results(results_path: str) -> EvaluationMetrics:
    """从结果文件解析评估指标"""
    metrics = EvaluationMetrics()
    
    try:
        # 检查结果文件是否存在
        if not os.path.exists(results_path):
            logger.error(f"结果文件不存在: {results_path}")
            return metrics
            
        with open(results_path, 'r') as f:
            results = json.load(f)
        
        logger.info(f"开始解析评估结果，结果键: {list(results.keys())}")
        
        # 优先使用overall_accuracy（如果存在）
        if "overall_accuracy" in results:
            metrics.accuracy = results["overall_accuracy"]
            logger.info(f"使用overall_accuracy作为主准确率: {metrics.accuracy}")
        # 其次使用average_accuracy
        elif "average_accuracy" in results:
            metrics.accuracy = results["average_accuracy"]
            logger.info(f"使用average_accuracy作为主准确率: {metrics.accuracy}")
        
        # 提取其他可能的指标
        metrics_map = {
            "f1_score": "f1",
            "precision": "precision",
            "recall": "recall",
            "perplexity": "perplexity",
            "bleu": "bleu",
            "rouge": "rouge",
            "exact_match": "exact_match"
        }
        
        for metric_name, result_key in metrics_map.items():
            if result_key in results:
                setattr(metrics, metric_name, results[result_key])
                logger.info(f"解析到指标 {metric_name}: {getattr(metrics, metric_name)}")
        
        # 保存细节结果为自定义指标
        if "subject_results" in results and isinstance(results["subject_results"], dict):
            for subject, subject_results in results["subject_results"].items():
                if "accuracy" in subject_results:
                    metrics.custom_metrics[f"{subject}_accuracy"] = subject_results["accuracy"]
                    logger.info(f"解析到科目 {subject} 准确率: {subject_results['accuracy']}")
                
        
        # 添加总体评估指标
        if "total_correct" in results and "total_questions" in results:
            metrics.custom_metrics["total_correct"] = results["total_correct"]
            metrics.custom_metrics["total_questions"] = results["total_questions"]
            logger.info(f"解析到总体评估指标: {results['total_correct']}/{results['total_questions']}")
        
        # 不再添加未知率相关指标
    
    except Exception as e:
        logger.error(f"解析结果文件失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
    
    return metrics

def select_evaluation_method(task: EvaluationTask) -> str:
    """
    根据任务类型选择评估方法
    
    Returns:
        评估方法的名称 (mmlu)
    """
    if task.benchmark_type == BenchmarkType.MMLU:
        return "mmlu"
    else:
        # 默认使用MMLU
        return "mmlu"

def run_huggingface_evaluation(task_id: int, model_path: str, output_dir: str, evaluation_method: str = "mmlu", config: dict = None, max_retries=3, retry_delay=2) -> Tuple[bool, str]:
    """执行HuggingFace评估，包含重试机制和更好的错误处理"""
    logger.info(f"开始HuggingFace评估: 任务ID={task_id}, 模型路径={model_path}")
    
    # 导入必要的库
    import numpy as np
    import random as random_module  # 避免命名冲突
    import traceback
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    task = get_evaluation_task(task_id)
    if not task:
        raise ValueError(f"找不到评估任务: {task_id}")
    
    # 最终结果存储
    evaluation_results = {
        "subjects": {},
        "accuracy": 0.0,
        "total_samples": 0,
        "successful_samples": 0,
        "failed_samples": 0,
        "errors": []
    }
    
    # 设置随机种子以确保可重现性
    np.random.seed(42)
    random_module.seed(42)
    
    try:
        # 获取当前工作目录的绝对路径
        current_dir = os.path.abspath(os.getcwd())
        
        # 获取数据集缓存路径
        cache_dir = get_dataset_cache_path()
        
        # 不再检查本地数据集路径，直接使用run_mmlu_evaluation
        if evaluation_method == "mmlu":
            add_evaluation_log(task_id, f"开始使用HuggingFace数据集进行MMLU评估...")
            # 传递配置参数
            success, result_path = run_mmlu_evaluation(task_id, model_path, output_dir, cache_dir, config)
            return success, result_path
        else:
            error_msg = f"不支持的评估方法: {evaluation_method}"
            logger.error(error_msg)
            add_evaluation_log(task_id, {"status": "error", "message": error_msg})
            return False, error_msg
        
    except Exception as e:
        error_msg = f"评估过程发生严重错误: {str(e)}"
        logging.error(error_msg)
        logging.error(traceback.format_exc())
        add_evaluation_log(task_id, {
            "status": "error", 
            "message": error_msg,
            "traceback": traceback.format_exc(),
            "partial_results": evaluation_results
        })
        # 保存任何可能的部分结果
        if evaluation_results["subjects"]:
            try:
                with open(os.path.join(output_dir, "partial_results.json"), "w", encoding="utf-8") as f:
                    json.dump(evaluation_results, f, default=json_serializer, ensure_ascii=False, indent=2)
            except Exception as save_error:
                logging.error(f"保存部分结果时出错: {str(save_error)}")
        
        return False, error_msg

def run_mmlu_evaluation(task_id: int, model_path: str, output_dir: str, cache_dir: str, config: dict = None) -> Tuple[bool, str]:
    """直接在代码中运行MMLU评估，不创建单独的脚本"""
    try:
        # 导入所需模块
        import random as random_module  # 避免命名冲突
        import numpy as np
        import time
        import re
        
        # 加载评估配置
        if config is None:
            config = MMLU_EVALUATION_CONFIG
        
        add_evaluation_log(task_id, "开始MMLU评估...")
        add_evaluation_log(task_id, f"评估配置: {json.dumps(config, ensure_ascii=False)}")
        
        # 设置环境变量
        os.environ["TOKENIZERS_PARALLELISM"] = "false"
        os.environ["HF_DATASETS_TRUST_REMOTE_CODE"] = "1"
        os.environ["TRANSFORMERS_TRUST_REMOTE_CODE"] = "1"
        os.environ["HF_DATASETS_CACHE"] = cache_dir
        os.environ["TRANSFORMERS_CACHE"] = cache_dir
        
        # 设置随机种子
        random_module.seed(42)
        np.random.seed(42)
        
        # 导入必要的库
        from datasets import load_dataset
        from transformers import AutoModelForCausalLM, AutoTokenizer
        
        # 加载模型和分词器
        add_evaluation_log(task_id, "加载模型和分词器...")
        
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.bfloat16,
            device_map="auto",
            trust_remote_code=True
        )
        
        tokenizer = AutoTokenizer.from_pretrained(
            model_path,
            use_fast=True,
            trust_remote_code=True
        )
        
        # 格式化MMLU问题
        def format_mmlu_question(example):
            options = ["A", "B", "C", "D"]
            # 使用英文提示词
            prompt = f"The following is a multiple-choice question. Please read carefully and select the correct answer.\n\nQuestion: {example['question']}\n\n"
            
            # 清晰地呈现选项
            for i, option in enumerate(options):
                if i < len(example["choices"]):
                    prompt += f"{option}. {example['choices'][i]}\n"
            
            # 更明确的英文指导
            prompt += "\nPlease select the most appropriate answer from options A, B, C, or D.\n"
            prompt += "Your answer should only contain the option letter, for example: A or B or C or D.\n"
            prompt += "Answer: "
            return prompt
        
        # 辅助函数：生成答案
        def generate_answer(prompt, max_new_tokens=None):
            if max_new_tokens is None:
                max_new_tokens = config.get("max_new_tokens", 32)
                
            # 减少冗余日志输出，不再显示提示词内容
            add_evaluation_log(task_id, "正在生成答案...", "DEBUG")
            
            try:
                # 准备输入
                inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
                
                # 准备生成参数
                generation_params = {}
                
                # 如果配置了使用模型自带参数，则优先使用模型推荐的参数
                if config.get("use_default_model_params", True) and hasattr(model, "generation_config"):
                    add_evaluation_log(task_id, "使用模型自带参数进行生成", "DEBUG")
                    # 只添加必要参数，其他使用模型默认值
                    generation_params["input_ids"] = inputs.input_ids
                    generation_params["max_new_tokens"] = max_new_tokens
                    # 可以选择性覆盖某些参数
                    if "temperature" in config:
                        generation_params["temperature"] = config.get("temperature")
                else:
                    # 使用自定义的参数配置
                    add_evaluation_log(task_id, "使用自定义参数进行生成", "DEBUG")
                    generation_params = {
                        "input_ids": inputs.input_ids,
                        "max_new_tokens": max_new_tokens,
                        **config.get("generation_params", {})
                    }
                
                # 执行生成
                with torch.no_grad():
                    outputs = model.generate(**generation_params)
                
                # 解码输出
                response = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
                
                # 过滤掉异常响应（全是分号或重复字符）
                response = response.strip()
                
                # 检测异常模式（更全面的检测）
                is_abnormal = False
                
                # 检查分号过多
                if response.count(';') > 5:
                    is_abnormal = True
                    add_evaluation_log(task_id, f"检测到过多分号: '{response}'", "WARNING")
                
                # 检查重复字符
                if len(set(response)) < min(3, len(response)/2) and len(response) > 3:
                    is_abnormal = True
                    add_evaluation_log(task_id, f"检测到重复字符: '{response}'", "WARNING")
                
                # 检查空格、标点过多
                punctuation_count = sum(1 for c in response if c in '.,;:!?，。；：！？')
                if punctuation_count > len(response) * 0.5 and len(response) > 5:
                    is_abnormal = True
                    add_evaluation_log(task_id, f"检测到过多标点: '{response}'", "WARNING")
                
                # 如果检测到异常，应用应急策略
                if is_abnormal:
                    # 不再使用随机选择
                    add_evaluation_log(task_id, f"检测到异常回答，标记为未知", "WARNING")
                    return "未知"
                
                # 打印完整回答用于调试
                add_evaluation_log(task_id, f"模型回答：{response}", "INFO")
                
                return response
                
            except Exception as e:
                add_evaluation_log(task_id, f"生成答案异常: {str(e)}", "ERROR")
                import traceback
                add_evaluation_log(task_id, f"生成异常详情:\n{traceback.format_exc()}", "ERROR")
                # 出错时返回空字符串
                return ""
        
        # 加载MMLU数据集
        add_evaluation_log(task_id, "加载MMLU数据集...")
        dataset = load_dataset("cais/mmlu", "all", trust_remote_code=True)
        
        # 获取多个MMLU子集
        subjects = list(dataset.keys())
        add_evaluation_log(task_id, f"找到的MMLU科目: {subjects}")
        
        # 准备测试数据集
        test_datasets = {}
        if 'test' in subjects:  # 如果test是一个子集
            # 检查test是否包含多个科目
            if hasattr(dataset['test'], 'features') and 'subject' in dataset['test'].features:
                # 按主题分组
                grouped = dataset['test'].to_pandas().groupby('subject')
                for subject, group in grouped:
                    # 将pandas dataframe转换回datasets格式
                    from datasets import Dataset
                    test_datasets[subject] = Dataset.from_pandas(group)
                    add_evaluation_log(task_id, f"从test中找到科目: {subject}, 样本数: {len(test_datasets[subject])}")
            else:
                # test本身就是一个测试集
                test_datasets['general'] = dataset['test']
                add_evaluation_log(task_id, f"使用整个test集作为通用测试集，样本数: {len(test_datasets['general'])}")
        else:
            # 查找所有包含test的子集
            for subject in subjects:
                if isinstance(dataset[subject], dict) and 'test' in dataset[subject]:
                    test_datasets[subject] = dataset[subject]['test']
                    add_evaluation_log(task_id, f"找到科目测试集: {subject}, 样本数: {len(test_datasets[subject])}")
        
        if not test_datasets:
            error_msg = "没有找到任何测试数据集"
            add_evaluation_log(task_id, error_msg, "ERROR")
            return False, error_msg
            
        add_evaluation_log(task_id, f"总共找到 {len(test_datasets)} 个测试数据集")
        
        # 执行评估
        add_evaluation_log(task_id, "开始评估...")
        results = {}
        
        # 确定要评估的科目数量，如果科目较少，全部评估
        max_subjects = min(5, len(test_datasets))
        subjects_to_evaluate = list(test_datasets.keys())[:max_subjects]
        add_evaluation_log(task_id, f"将评估 {max_subjects} 个科目: {', '.join(subjects_to_evaluate)}")
        
        for subject_idx, subject in enumerate(subjects_to_evaluate):
            add_evaluation_log(task_id, f"开始评估科目 ({subject_idx+1}/{max_subjects}): {subject}")
            test_data = test_datasets[subject]
            
            # 限制每个科目的样本数，确保至少评估几个样本
            min_samples = 5  # 至少评估5个样本
            max_samples = 20
            samples_to_evaluate = min(max(min_samples, len(test_data) // 4), max_samples, len(test_data))
            
            if len(test_data) > samples_to_evaluate:
                sample_indices = list(range(len(test_data)))
                random_module.seed(42)  # 使用固定种子以确保可重复性
                random_module.shuffle(sample_indices)
                sample_indices = sample_indices[:samples_to_evaluate]
                test_data = test_data.select(sample_indices)
            
            add_evaluation_log(task_id, f"科目 '{subject}' 将评估 {len(test_data)} 个样本")
            
            # 创建科目评估保护层
            try:
                correct = 0
                total = 0
                answers = []
                errors_count = 0
                
                for i, example in enumerate(test_data):
                    # 每个样本都有独立的异常处理
                    try:
                        # 检查样本格式
                        required_fields = ['question', 'choices', 'answer']
                        missing_fields = [f for f in required_fields if f not in example or example[f] is None]
                        
                        if missing_fields:
                            add_evaluation_log(task_id, f"样本 {i+1} 缺少必要字段: {missing_fields}，跳过", "WARNING")
                            continue
                        
                        # 验证answer是整数且在合法范围内
                        if not isinstance(example['answer'], int) or example['answer'] < 0 or example['answer'] >= len(example['choices']):
                            add_evaluation_log(task_id, f"样本 {i+1} 的答案 {example['answer']} 不合法，跳过", "WARNING")
                            continue
                        
                        # 格式化问题
                        prompt = format_mmlu_question(example)
                        
                        # 生成答案
                        start_time = time.time()
                        add_evaluation_log(task_id, f"问题：{prompt[:100]}...", "INFO")
                        model_answer = generate_answer(prompt)
                        end_time = time.time()
                        
                        # 改进提取选项字母的逻辑
                        model_choice = ""
                        
                        # 首先尝试直接从开头获取单个字母答案（最理想情况）
                        first_char = model_answer.strip()[0:1] if model_answer.strip() else ""
                        if first_char in "ABCD":
                            model_choice = first_char
                            add_evaluation_log(task_id, f"直接提取到选项: {model_choice}", "INFO")
                        else:
                            # 1. 先查找形如"答案：X"的模式
                            answer_format = re.search(r'答案[：:]\s*([A-D])', model_answer)
                            if answer_format:
                                model_choice = answer_format.group(1)
                                add_evaluation_log(task_id, f"找到标准格式答案: {model_choice}", "DEBUG")
                            else:
                                # 2. 查找"我选择X"或"我的答案是X"
                                answer_phrase = re.search(r'我[的选]*(选择|答案)[是为：:]\s*([A-D])', model_answer)
                                if answer_phrase:
                                    model_choice = answer_phrase.group(2)
                                    add_evaluation_log(task_id, f"找到答案短语: {model_choice}", "DEBUG")
                                else:
                                    # 3. 尝试找出回答中的A、B、C或D（单独的字母）
                                    option_match = re.search(r'\b([A-D])\b', model_answer)
                                    if option_match:
                                        model_choice = option_match.group(1)
                                        add_evaluation_log(task_id, f"找到独立选项: {model_choice}", "DEBUG")
                                    else:
                                        # 4. 尝试找出回答中包含的任何A、B、C或D字母
                                        all_options = re.findall(r'[A-D]', model_answer)
                                        if all_options:
                                            # 选择第一个找到的选项
                                            model_choice = all_options[0]
                                            add_evaluation_log(task_id, f"找到任意字母选项: {model_choice}", "DEBUG")
                        
                        # 5. 如果还是没找到，检查是否有"选项A"这样的短语
                        if not model_choice:
                            option_phrases = ["选项A", "选项B", "选项C", "选项D", 
                                             "答案A", "答案B", "答案C", "答案D",
                                             "选择A", "选择B", "选择C", "选择D"]
                            for idx, phrase in enumerate(option_phrases):
                                if phrase in model_answer:
                                    model_choice = "ABCD"[idx % 4]
                                    add_evaluation_log(task_id, f"找到选项短语: {phrase}", "DEBUG")
                                    break
                        
                        # 如果仍然没找到，尝试最后的方法
                        if not model_choice and model_answer:
                            # 6. 尝试对前3个字符进行特别分析
                            first_chars = model_answer[:3].upper()
                            for c in first_chars:
                                if c in "ABCD":
                                    model_choice = c
                                    add_evaluation_log(task_id, f"从前3个字符找到选项: {model_choice}", "DEBUG")
                                    break
                            
                            # 7. 如果依然没找到，统计各选项出现次数
                            if not model_choice:
                                counts = {opt: model_answer.count(opt) for opt in "ABCD"}
                                if any(counts.values()):
                                    most_common = max(counts.items(), key=lambda x: x[1])
                                    if most_common[1] > 0:
                                        model_choice = most_common[0]
                                        add_evaluation_log(task_id, f"通过出现频率选择: {model_choice}", "DEBUG")
                        
                        # 如果最终没有找到任何选项，记录日志
                        if not model_choice:
                            add_evaluation_log(task_id, "未能从回答中提取选项", "WARNING")
                            # 不再随机选择，而是标记为未知
                            model_choice = "未知"
                            add_evaluation_log(task_id, f"无法提取选项，标记为: {model_choice}", "WARNING")
                        
                        # 获取正确答案
                        correct_answer = "ABCD"[example["answer"]]
                        
                        # 检查是否正确（未知的情况视为错误）
                        is_correct = model_choice == correct_answer
                        if model_choice == "未知":
                            is_correct = False
                            add_evaluation_log(task_id, f"因无法确定答案，视为错误", "WARNING")
                        
                        if is_correct:
                            correct += 1
                        total += 1
                        
                        # 记录答案
                        answers.append({
                            "question": example["question"],
                            "choices": example["choices"],
                            "model_response": model_answer,
                            "model_choice": model_choice,
                            "correct_answer": correct_answer,
                            "is_correct": is_correct,
                            "response_time": end_time - start_time
                        })
                        
                        add_evaluation_log(task_id, f"科目 '{subject}' - 样本 {i+1}/{len(test_data)}: 选择[{model_choice}]，正确答案[{correct_answer}]，{'✓正确' if is_correct else '✗错误'}")
                        
                        # 更新任务进度
                        subjects_done = subjects_to_evaluate.index(subject)
                        samples_done = i + 1
                        total_subjects = len(subjects_to_evaluate)
                        total_samples = len(test_data)
                        overall_progress = (subjects_done / total_subjects) + (samples_done / total_samples / total_subjects)
                        update_evaluation_task(task_id=task_id, progress=overall_progress)
                        
                    except Exception as e:
                        # 单个样本异常不应该影响整个科目评估
                        errors_count += 1
                        add_evaluation_log(task_id, f"评估样本 {i+1} 时出错: {str(e)}", "ERROR")
                        import traceback
                        add_evaluation_log(task_id, f"错误详情:\n{traceback.format_exc()}", "ERROR")
                        
                        # 如果连续错误太多，跳出循环
                        if errors_count >= 5:
                            add_evaluation_log(task_id, f"连续出现{errors_count}个错误，跳过剩余样本", "ERROR")
                            break
                
                # 计算准确率
                accuracy = correct / total if total > 0 else 0
                
                # 统计未知答案数量
                unknown_count = sum(1 for a in answers if a.get("model_choice") == "未知")
                unknown_rate = unknown_count / total if total > 0 else 0
                
                # 保存结果
                results[subject] = {
                    "accuracy": accuracy,
                    "correct": correct,
                    "total": total,
                    "unknown_count": unknown_count,
                    "unknown_rate": unknown_rate,
                    "answers": answers
                }
                
                add_evaluation_log(task_id, f"科目 '{subject}' 评估完成: 准确率 {accuracy:.4f} ({correct}/{total}), 未知答案率 {unknown_rate:.4f} ({unknown_count}/{total})")
            
            except Exception as e:
                # 即使整个科目评估失败，也记录错误并继续下一个科目
                add_evaluation_log(task_id, f"评估科目 '{subject}' 时出现严重错误: {str(e)}", "ERROR")
                import traceback
                add_evaluation_log(task_id, f"科目错误详情:\n{traceback.format_exc()}", "ERROR")
        
        # 计算平均准确率
        if results:
            accuracies = [results[subject]["accuracy"] for subject in results]
            avg_accuracy = sum(accuracies) / len(accuracies) if accuracies else 0
            
            total_correct = sum(results[subject]["correct"] for subject in results)
            total_questions = sum(results[subject]["total"] for subject in results)
            overall_accuracy = total_correct / total_questions if total_questions > 0 else 0
            
            add_evaluation_log(task_id, f"整体评估结果: 平均科目准确率 {avg_accuracy:.4f}, 总体准确率 {overall_accuracy:.4f} ({total_correct}/{total_questions})")
        else:
            avg_accuracy = 0.0
            add_evaluation_log(task_id, f"未能完成任何科目评估，平均准确率为0", "WARNING")
        
        # 保存总体结果
        overall_results = {
            "average_accuracy": avg_accuracy,
            "benchmark": "MMLU",
            "subject_results": results
        }
        
        if len(results) > 0:
            # 计算总体指标
            total_correct = sum(results[subject]["correct"] for subject in results)
            total_questions = sum(results[subject]["total"] for subject in results)
            overall_accuracy = total_correct / total_questions if total_questions > 0 else 0
            
            # 计算总体未知率
            total_unknown = sum(results[subject]["unknown_count"] for subject in results)
            unknown_rate = total_unknown / total_questions if total_questions > 0 else 0
            
            # 添加总体指标
            overall_results["total_correct"] = total_correct
            overall_results["total_questions"] = total_questions
            overall_results["overall_accuracy"] = overall_accuracy
            overall_results["total_unknown"] = total_unknown
            overall_results["unknown_rate"] = unknown_rate
            
            add_evaluation_log(task_id, f"总体未知答案率: {unknown_rate:.4f} ({total_unknown}/{total_questions})")
        
        # 保存结果到文件
        result_path = os.path.join(output_dir, "mmlu_results.json")
        with open(result_path, "w") as f:
            json.dump(overall_results, f, indent=2)
        
        add_evaluation_log(task_id, f"评估完成，结果已保存到: {result_path}")
        
        # 解析指标更新任务
        try:
            metrics = parse_metrics_from_results(result_path)
            add_evaluation_log(task_id, f"解析指标完成: 准确率={metrics.accuracy}")
            
            # 将指标对象转换为字典以便序列化
            metrics_dict = json.loads(json.dumps(metrics, default=json_serializer))
            
            # 记录更详细的指标信息
            if metrics.accuracy is not None:
                add_evaluation_log(task_id, f"最终评估准确率: {metrics.accuracy:.4f} ({metrics.custom_metrics.get('total_correct', 0)}/{metrics.custom_metrics.get('total_questions', 0)})")
            
            # 记录每个科目的准确率
            for key, value in metrics.custom_metrics.items():
                if key.endswith("_accuracy"):
                    subject = key.replace("_accuracy", "")
                    add_evaluation_log(task_id, f"科目 '{subject}' 准确率: {value:.4f}")
            
            # 更新任务指标 - 使用经过序列化处理的字典形式
            update_evaluation_task(
                task_id=task_id,
                metrics_dict=metrics_dict  # 直接使用序列化后的字典
            )
        except Exception as e:
            add_evaluation_log(task_id, f"解析指标失败: {str(e)}", "ERROR")
            import traceback
            add_evaluation_log(task_id, f"详细错误: {traceback.format_exc()}", "ERROR")
        
        return True, result_path
        
    except Exception as e:
        error_msg = f"MMLU评估异常: {str(e)}"
        add_evaluation_log(task_id, error_msg, "ERROR")
        import traceback
        add_evaluation_log(task_id, f"错误详情:\n{traceback.format_exc()}", "ERROR")
        return False, error_msg

def run_evaluation(task_id: int):
    """
    运行评估任务 - 使用Hugging Face评估
    """
    # 获取任务详情
    task = get_evaluation_task(task_id)
    if not task:
        logger.error(f"评估任务不存在: {task_id}")
        return
    
    # 更新任务状态为"运行中"
    task = update_evaluation_task(
        task_id=task_id,
        status=EvaluationStatus.RUNNING,
        started_at=datetime.now()
    )
    
    # 将任务添加到运行中的任务字典
    running_evaluations[task_id] = True
    
    try:
        # 记录开始信息
        add_evaluation_log(task_id, f"开始评估任务: {task.name}")
        
        # 创建评估配置
        config_path, output_dir, model_path = create_evaluation_config(task)
        add_evaluation_log(task_id, f"已创建评估配置文件: {config_path}")
        add_evaluation_log(task_id, f"模型路径: {model_path}")
        
        # 从评估配置中加载生成参数
        evaluation_config = None
        try:
            with open(config_path, 'r') as f:
                config_data = json.load(f)
                # 提取生成参数配置
                if 'parameters' in config_data:
                    evaluation_config = {
                        "max_new_tokens": config_data['parameters'].get('max_new_tokens', 32),
                        "temperature": config_data['parameters'].get('temperature', 0.01),
                        "use_default_model_params": config_data['parameters'].get('use_default_model_params', True),
                        "generation_params": config_data['parameters'].get('generation_params', {})
                    }
                    add_evaluation_log(task_id, f"从配置文件加载参数: {json.dumps(evaluation_config, default=json_serializer, ensure_ascii=False)}")
        except Exception as e:
            add_evaluation_log(task_id, f"加载配置文件失败，将使用默认参数: {str(e)}", "WARNING")
            evaluation_config = MMLU_EVALUATION_CONFIG
        
        # 添加诊断信息
        import sys
        add_evaluation_log(task_id, f"Python版本: {sys.version}")
        add_evaluation_log(task_id, f"Python路径: {sys.executable}")
        
        # 选择评估方法
        evaluation_method = select_evaluation_method(task)
        add_evaluation_log(task_id, f"选择的评估方法: {evaluation_method}")
        
        # 确保数据集已下载
        add_evaluation_log(task_id, f"检查{evaluation_method}数据集...")
        success, message = download_dataset(evaluation_method)
        if success:
            add_evaluation_log(task_id, f"数据集准备: {message}")
        else:
            add_evaluation_log(task_id, f"数据集准备失败: {message}", "WARNING")
            # 即使数据集准备失败，也继续评估，因为评估脚本会自动下载
        
        # 使用Hugging Face评估
        add_evaluation_log(task_id, f"使用Hugging Face进行{evaluation_method}评估...")
        success, result_or_error = run_huggingface_evaluation(
            task_id, 
            model_path, 
            output_dir, 
            evaluation_method,
            config=evaluation_config
        )
        
        if success:
            # 评估成功
            add_evaluation_log(task_id, f"Hugging Face {evaluation_method}评估成功完成")
            
            # 更新任务状态
            update_evaluation_task(
                task_id=task_id,
                status=EvaluationStatus.COMPLETED,
                progress=1.0,
                result_path=output_dir,
                completed_at=datetime.now()
            )
        else:
            # 评估失败
            add_evaluation_log(task_id, f"Hugging Face {evaluation_method}评估失败: {result_or_error}", "ERROR")
            
            # 更新任务状态
            update_evaluation_task(
                task_id=task_id,
                status=EvaluationStatus.FAILED,
                error_message=result_or_error,
                completed_at=datetime.now()
            )
            
    except Exception as e:
        logger.exception(f"评估任务执行异常: {str(e)}")
        add_evaluation_log(task_id, f"评估任务执行异常: {str(e)}", "ERROR")
        update_evaluation_task(
            task_id=task_id,
            status=EvaluationStatus.FAILED,
            error_message=str(e),
            completed_at=datetime.now()
        )
    
    finally:
        # 从运行中的任务字典中移除
        if task_id in running_evaluations:
            del running_evaluations[task_id]

def start_evaluation(task_id: int):
    """
    在后台启动评估任务
    """
    threading.Thread(target=run_evaluation, args=(task_id,), daemon=True).start()

def stop_evaluation(task_id: int) -> bool:
    """
    停止正在运行的评估任务
    """
    if task_id in running_evaluations:
        del running_evaluations[task_id]
        return True
    return False

def delete_evaluation_task_config(task_id: int) -> bool:
    """
    删除评估任务的配置文件
    """
    try:
        config_path = f"{EVALUATION_CONFIGS_DIR}/task_{task_id}.json"
        if os.path.exists(config_path):
            os.remove(config_path)
            logger.info(f"已删除评估配置文件: {config_path}")
        return True
    except Exception as e:
        logger.error(f"删除评估配置文件失败: {str(e)}")
        return False

def get_available_benchmarks() -> List[Dict[str, Any]]:
    """
    获取可用的基准测试列表
    """
    benchmarks = []
    
    # 问答和知识检索
    benchmarks.append({"id": BenchmarkType.MMLU, "name": "大规模多任务语言理解", "category": "问答和知识检索", "description": "多项选择题基准，涵盖小学数学、美国历史、计算机科学、法律等领域"})
    
    return benchmarks

# 添加datetime JSON序列化支持的函数
def datetime_serializer(obj):
    """处理datetime的JSON序列化"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"类型 {type(obj)} 无法被序列化为JSON")

def add_evaluation_log(task_id: int, content: str, level: str = "INFO"):
    """添加评估日志"""
    # 处理content为字典的情况
    if isinstance(content, dict):
        content = json.dumps(content, ensure_ascii=False)
        
    # 创建日志条目
    log_entry = {
        "task_id": task_id,
        "timestamp": datetime.now().isoformat(),  # 直接存储为ISO格式字符串
        "content": content,
        "level": level
    }
    
    # 添加到数据库
    from database import add_evaluation_log as db_add_log
    db_add_log(task_id, content, level)
    
    # 发送WebSocket消息
    try:
        from main import send_evaluation_log
        
        # 使用asyncio运行异步函数
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # 如果没有事件循环，则创建一个新的
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # 使用事件循环的run_in_executor来在后台运行
        # 使用自定义的JSON序列化函数处理特殊类型
        loop.run_in_executor(None, lambda: asyncio.run(send_evaluation_log(task_id, json.dumps(log_entry, default=json_serializer))))
    except Exception as e:
        logger.error(f"WebSocket评估日志异常: {str(e)}")

# 扩展JSON序列化函数，处理更多类型
def json_serializer(obj):
    """自定义JSON序列化函数，处理各种类型的对象"""
    if isinstance(obj, EvaluationMetrics):
        # 特殊处理评估指标对象
        metrics_dict = {
            "accuracy": obj.accuracy,
            "f1_score": obj.f1_score,
            "precision": obj.precision,
            "recall": obj.recall, 
            "perplexity": obj.perplexity,
            "bleu": obj.bleu,
            "rouge": obj.rouge,
            "exact_match": obj.exact_match,
            "custom_metrics": obj.custom_metrics
        }
        return metrics_dict
    elif hasattr(obj, '__dict__'):
        return obj.__dict__
    elif isinstance(obj, datetime.datetime):
        return obj.isoformat()
    elif isinstance(obj, Exception):
        return str(obj)
    elif isinstance(obj, (np.int32, np.int64)):
        return int(obj)
    elif isinstance(obj, (np.float32, np.float64)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (set, frozenset)):
        return list(obj)
    elif isinstance(obj, bytes):
        return obj.decode('utf-8', errors='replace')
    else:
        # 对于其他无法处理的类型，尝试转换为字符串
        try:
            return str(obj)
        except:
            return f"<不可序列化的对象: {type(obj).__name__}>" 