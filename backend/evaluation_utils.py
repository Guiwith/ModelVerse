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
    },
    "mmlu_pro": {
        "name": "MMLU-Pro (增强版MMLU)",
        "hf_path": "QwenLM/MMLU-Pro",
        "description": "增强的MMLU，扩展了知识驱动的问题，整合了更具挑战性的推理问题，并将选项从四个扩展到十个",
        "size_mb": 25,
        "url": "https://huggingface.co/datasets/QwenLM/MMLU-Pro"
    },
    "hellaswag": {
        "name": "HellaSwag",
        "hf_path": "hellaswag",
        "description": "一个推理挑战数据集，要求模型从四个选项中选择最合理的情景续写",
        "size_mb": 35,
        "url": "https://huggingface.co/datasets/hellaswag"
    },
    "gsm8k": {
        "name": "GSM8K (年级学校数学8K)",
        "hf_path": "gsm8k",
        "description": "8.5K份高质量的英文小学数学应用题",
        "size_mb": 2,
        "url": "https://huggingface.co/datasets/gsm8k"
    },
    "truthfulqa": {
        "name": "TruthfulQA",
        "hf_path": "truthful_qa",
        "description": "测试模型产生真实回答（而非虚假信息）的能力",
        "size_mb": 1,
        "url": "https://huggingface.co/datasets/truthful_qa"
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
    
    # 创建临时脚本来下载数据集
    fd, script_path = tempfile.mkstemp(suffix='.py')
    os.close(fd)
    
    try:
        # 构建脚本内容
        script_content = f"""
import os
import sys
import json

# 设置缓存目录
os.environ["HF_DATASETS_CACHE"] = "{cache_dir}"
os.environ["TRANSFORMERS_CACHE"] = "{cache_dir}"
os.environ["HF_DATASETS_TRUST_REMOTE_CODE"] = "1"
os.environ["TRANSFORMERS_TRUST_REMOTE_CODE"] = "1"

# 如果使用镜像
{'os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"' if mirror else ''}

try:
    from datasets import load_dataset
    
    # 加载数据集（只下载元数据）
    print(f"开始下载数据集: {dataset_info['hf_path']}")
    dataset = load_dataset("{dataset_info['hf_path']}", trust_remote_code=True)
    
    # 实际获取部分数据，触发下载
    if isinstance(dataset, dict):
        for split_name, split_data in dataset.items():
            print(f"获取数据集{{dataset_info['hf_path']}}的{{split_name}}部分...")
            if hasattr(split_data, "take"):
                sample = split_data.take(1)
                print(f"加载了1个样本")
    else:
        print(f"获取数据集{{dataset_info['hf_path']}}的样本...")
        if hasattr(dataset, "take"):
            sample = dataset.take(1)
            print(f"加载了1个样本")
    
    print(f"数据集{dataset_info['hf_path']}已成功下载和缓存")
    sys.exit(0)
except Exception as e:
    print(f"下载数据集失败: {str(e)}")
    sys.exit(1)
"""
        
        # 写入脚本文件
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        # 执行脚本
        process = subprocess.Popen(
            [sys.executable, script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            error_msg = f"下载数据集{dataset_id}失败: {stderr}"
            logger.error(error_msg)
            return False, error_msg
        
        # 下载成功
        logger.info(f"数据集{dataset_id}下载成功")
        return True, f"数据集{dataset_id}已成功下载和缓存"
        
    finally:
        # 删除临时脚本
        try:
            os.remove(script_path)
        except:
            pass

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
            "max_new_tokens": 256,
            "temperature": 0.0,
            "do_sample": False
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
        
        # 提取常见指标
        if "average_accuracy" in results:
            metrics.accuracy = results["average_accuracy"]
        
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
        
        # 保存细节结果为自定义指标
        if "subject_results" in results and isinstance(results["subject_results"], dict):
            for subject, subject_results in results["subject_results"].items():
                if "accuracy" in subject_results:
                    metrics.custom_metrics[f"{subject}_accuracy"] = subject_results["accuracy"]
    
    except Exception as e:
        logger.error(f"解析结果文件失败: {str(e)}")
    
    return metrics

def select_evaluation_method(task: EvaluationTask) -> str:
    """
    根据任务类型选择评估方法
    
    Returns:
        评估方法的名称 (mmlu, mmlu_pro, etc.)
    """
    if task.benchmark_type == BenchmarkType.MMLU:
        return "mmlu"
    elif task.benchmark_type == BenchmarkType.MMLU_PRO:
        return "mmlu_pro"
    else:
        # 默认使用MMLU
        return "mmlu"

def run_huggingface_evaluation(task_id: int, model_path: str, output_dir: str, evaluation_method: str = "mmlu") -> Tuple[bool, str]:
    """使用Hugging Face的evaluate库进行评估"""
    try:
        # 记录开始信息
        add_evaluation_log(task_id, f"开始使用Hugging Face进行{evaluation_method}评估...")
        
        # 获取数据集缓存目录
        cache_dir = get_dataset_cache_path()
        
        # 选择评估脚本
        if evaluation_method == "mmlu":
            return run_mmlu_evaluation(task_id, model_path, output_dir, cache_dir)
        elif evaluation_method == "mmlu_pro":
            return run_mmlu_pro_evaluation(task_id, model_path, output_dir, cache_dir)
        else:
            add_evaluation_log(task_id, f"不支持的评估方法: {evaluation_method}", "ERROR")
            return False, f"不支持的评估方法: {evaluation_method}"
        
    except Exception as e:
        error_msg = f"Hugging Face评估异常: {str(e)}"
        add_evaluation_log(task_id, error_msg, "ERROR")
        import traceback
        add_evaluation_log(task_id, f"错误详情:\n{traceback.format_exc()}", "ERROR")
        return False, error_msg

def run_mmlu_evaluation(task_id: int, model_path: str, output_dir: str, cache_dir: str) -> Tuple[bool, str]:
    """运行MMLU评估"""
    try:
        # 创建评估脚本
        script_path = os.path.join(output_dir, "mmlu_evaluate.py")
        script_content = f"""#!/usr/bin/env python3
import os
import sys
import json
import traceback
import time

# 设置环境变量
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_DATASETS_TRUST_REMOTE_CODE"] = "1"
os.environ["TRANSFORMERS_TRUST_REMOTE_CODE"] = "1"
os.environ["HF_DATASETS_CACHE"] = "{cache_dir}"
os.environ["TRANSFORMERS_CACHE"] = "{cache_dir}"

try:
    # 导入必要的模块
    import torch
    from datasets import load_dataset
    from transformers import AutoModelForCausalLM, AutoTokenizer
    
    # 加载模型和分词器
    print("加载模型和分词器...")
    model_path = "{model_path}"
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
    
    # 辅助函数：生成答案
    def generate_answer(prompt, max_new_tokens=128):
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        with torch.no_grad():
            outputs = model.generate(
                inputs.input_ids,
                max_new_tokens=max_new_tokens,
                temperature=0.0,
                do_sample=False
            )
        response = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
        return response.strip()
    
    # 加载MMLU数据集
    print("加载MMLU数据集...")
    dataset = load_dataset("cais/mmlu", "all", trust_remote_code=True)
    
    # 获取多个MMLU子集
    subjects = list(dataset.keys())
    print(f"找到的MMLU科目: {{subjects}}")
    
    # 准备测试数据集
    test_datasets = {{}}
    for subject in subjects:
        if "test" in dataset[subject]:
            test_datasets[subject] = dataset[subject]["test"]
    
    # 格式化MMLU问题
    def format_mmlu_question(example):
        options = ["A", "B", "C", "D"]
        prompt = f"问题: {{example['question']}}\n\n"
        
        for i, option in enumerate(options):
            if i < len(example["choices"]):
                prompt += f"{{option}}. {{example['choices'][i]}}\n"
        
        prompt += "\n请从上述选项中选择一个最合适的答案。只需回答选项字母即可。"
        return prompt
    
    # 执行评估
    print("开始评估...")
    results = {{}}
    
    # 限制评估科目数量，避免过长时间
    max_subjects = 5
    subjects_to_evaluate = list(test_datasets.keys())[:max_subjects]
    
    for subject in subjects_to_evaluate:
        print(f"评估科目: {{subject}}")
        test_data = test_datasets[subject]
        
        # 限制每个科目的样本数
        max_samples = 20
        if len(test_data) > max_samples:
            sample_indices = list(range(len(test_data)))
            import random
            random.shuffle(sample_indices)
            sample_indices = sample_indices[:max_samples]
            test_data = test_data.select(sample_indices)
        
        correct = 0
        total = 0
        answers = []
        
        for i, example in enumerate(test_data):
            try:
                # 格式化问题
                prompt = format_mmlu_question(example)
                
                # 生成答案
                start_time = time.time()
                model_answer = generate_answer(prompt)
                end_time = time.time()
                
                # 提取选项字母
                first_letter = model_answer.strip()[0].upper() if model_answer.strip() else ""
                model_choice = first_letter if first_letter in ["A", "B", "C", "D"] else ""
                
                # 获取正确答案
                correct_answer = "ABCD"[example["answer"]]
                
                # 检查是否正确
                is_correct = model_choice == correct_answer
                if is_correct:
                    correct += 1
                total += 1
                
                # 记录答案
                answers.append({{
                    "question": example["question"],
                    "choices": example["choices"],
                    "model_response": model_answer,
                    "model_choice": model_choice,
                    "correct_answer": correct_answer,
                    "is_correct": is_correct,
                    "response_time": end_time - start_time
                }})
                
                print(f"样本 {{i+1}}/{{len(test_data)}}: {{correct}}/{{total}} 正确")
                
            except Exception as e:
                print(f"评估样本时出错: {{str(e)}}")
                traceback.print_exc()
        
        # 计算准确率
        accuracy = correct / total if total > 0 else 0
        
        # 保存结果
        results[subject] = {{
            "accuracy": accuracy,
            "correct": correct,
            "total": total,
            "answers": answers
        }}
        
        print(f"科目 {{subject}} 准确率: {{accuracy:.4f}} ({{correct}}/{{total}})")
    
    # 计算平均准确率
    accuracies = [results[subject]["accuracy"] for subject in results]
    avg_accuracy = sum(accuracies) / len(accuracies) if accuracies else 0
    
    # 保存总体结果
    overall_results = {{
        "average_accuracy": avg_accuracy,
        "benchmark": "MMLU",
        "subject_results": results
    }}
    
    # 保存结果到文件
    result_path = os.path.join("{output_dir}", "mmlu_results.json")
    with open(result_path, "w") as f:
        json.dump(overall_results, f, indent=2)
    
    print(f"评估完成，平均准确率: {{avg_accuracy:.4f}}")
    print(f"结果已保存到: {{result_path}}")
    
except Exception as e:
    print(f"评估失败: {{str(e)}}")
    traceback.print_exc(file=sys.stdout)
    sys.exit(1)
"""
        
        # 写入脚本文件
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        # 确保脚本有执行权限
        os.chmod(script_path, 0o755)
        
        # 创建临时日志文件
        log_file = os.path.join(output_dir, "mmlu_evaluation_log.txt")
        
        # 执行脚本
        add_evaluation_log(task_id, f"执行MMLU评估脚本: {script_path}")
        
        # 使用系统Python解释器执行脚本
        cmd = f"{sys.executable} {script_path} > {log_file} 2>&1"
        return_code = os.system(cmd)
        
        # 读取日志文件
        log_content = ""
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                log_content = f.read()
        
        # 记录日志
        if log_content:
            add_evaluation_log(task_id, f"MMLU评估日志:\n{log_content}")
        
        # 检查结果
        if return_code != 0:
            add_evaluation_log(task_id, f"MMLU评估失败，返回码: {return_code}", "ERROR")
            return False, "MMLU评估执行失败"
        
        # 检查结果文件
        result_path = os.path.join(output_dir, "mmlu_results.json")
        if not os.path.exists(result_path):
            add_evaluation_log(task_id, "MMLU评估完成，但未找到结果文件", "ERROR")
            return False, "未找到MMLU结果文件"
        
        # 解析结果
        with open(result_path, 'r') as f:
            results = json.load(f)
        
        # 记录结果摘要
        avg_accuracy = results.get("average_accuracy", 0)
        add_evaluation_log(task_id, f"MMLU评估成功完成，平均准确率: {avg_accuracy:.4f}")
        
        return True, result_path
        
    except Exception as e:
        error_msg = f"MMLU评估异常: {str(e)}"
        add_evaluation_log(task_id, error_msg, "ERROR")
        import traceback
        add_evaluation_log(task_id, f"错误详情:\n{traceback.format_exc()}", "ERROR")
        return False, error_msg

def run_mmlu_pro_evaluation(task_id: int, model_path: str, output_dir: str, cache_dir: str) -> Tuple[bool, str]:
    """运行MMLU-Pro评估"""
    try:
        # 创建评估脚本
        script_path = os.path.join(output_dir, "mmlu_pro_evaluate.py")
        script_content = f"""#!/usr/bin/env python3
import os
import sys
import json
import traceback
import time

# 设置环境变量
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_DATASETS_TRUST_REMOTE_CODE"] = "1"
os.environ["TRANSFORMERS_TRUST_REMOTE_CODE"] = "1"
os.environ["HF_DATASETS_CACHE"] = "{cache_dir}"
os.environ["TRANSFORMERS_CACHE"] = "{cache_dir}"

try:
    # 导入必要的模块
    import torch
    from datasets import load_dataset
    from transformers import AutoModelForCausalLM, AutoTokenizer
    
    # 加载模型和分词器
    print("加载模型和分词器...")
    model_path = "{model_path}"
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
    
    # 辅助函数：生成答案
    def generate_answer(prompt, max_new_tokens=128):
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        with torch.no_grad():
            outputs = model.generate(
                inputs.input_ids,
                max_new_tokens=max_new_tokens,
                temperature=0.0,
                do_sample=False
            )
        response = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
        return response.strip()
    
    # 加载MMLU-Pro数据集
    print("加载MMLU-Pro数据集...")
    dataset = load_dataset("QwenLM/MMLU-Pro", trust_remote_code=True)
    
    # 准备测试数据集
    if "test" in dataset:
        test_data = dataset["test"]
        print(f"找到MMLU-Pro测试集，共{{len(test_data)}}个样本")
    else:
        print("未找到MMLU-Pro测试集")
        sys.exit(1)
    
    # 获取科目列表
    subjects = set()
    for example in test_data:
        if "subject" in example:
            subjects.add(example["subject"])
    subjects = sorted(list(subjects))
    print(f"找到的MMLU-Pro科目: {{subjects}}")
    
    # 格式化MMLU-Pro问题
    def format_mmlu_pro_question(example):
        prompt = f"问题: {{example['question']}}\n\n"
        
        # MMLU-Pro可能有多于4个选项
        options = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
        for i, choice in enumerate(example["choices"]):
            if i < len(options):
                prompt += f"{{options[i]}}. {{choice}}\n"
        
        prompt += "\n请从上述选项中选择一个最合适的答案。只需回答选项字母即可。"
        return prompt
    
    # 执行评估
    print("开始评估...")
    subject_results = {{}}
    
    # 准备按科目分组的数据
    subject_data = {{}}
    for example in test_data:
        subject = example.get("subject", "Unknown")
        if subject not in subject_data:
            subject_data[subject] = []
        subject_data[subject].append(example)
    
    # 限制评估科目数量，避免过长时间
    max_subjects = 5
    subjects_to_evaluate = list(subject_data.keys())[:max_subjects]
    
    overall_correct = 0
    overall_total = 0
    
    for subject in subjects_to_evaluate:
        print(f"评估科目: {{subject}}")
        subject_examples = subject_data[subject]
        
        # 限制每个科目的样本数
        max_samples = 20
        if len(subject_examples) > max_samples:
            import random
            random.shuffle(subject_examples)
            subject_examples = subject_examples[:max_samples]
        
        correct = 0
        total = 0
        answers = []
        
        for i, example in enumerate(subject_examples):
            try:
                # 格式化问题
                prompt = format_mmlu_pro_question(example)
                
                # 生成答案
                start_time = time.time()
                model_answer = generate_answer(prompt)
                end_time = time.time()
                
                # 提取选项字母
                first_letter = model_answer.strip()[0].upper() if model_answer.strip() else ""
                options = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
                model_choice = first_letter if first_letter in options else ""
                
                # 获取正确答案
                correct_answer = example["answer"]
                
                # 检查是否正确
                is_correct = model_choice == correct_answer
                if is_correct:
                    correct += 1
                    overall_correct += 1
                total += 1
                overall_total += 1
                
                # 记录答案
                answers.append({{
                    "question": example["question"],
                    "choices": example["choices"],
                    "model_response": model_answer,
                    "model_choice": model_choice,
                    "correct_answer": correct_answer,
                    "is_correct": is_correct,
                    "response_time": end_time - start_time
                }})
                
                print(f"样本 {{i+1}}/{{len(subject_examples)}}: {{correct}}/{{total}} 正确")
                
            except Exception as e:
                print(f"评估样本时出错: {{str(e)}}")
                traceback.print_exc()
        
        # 计算准确率
        accuracy = correct / total if total > 0 else 0
        
        # 保存科目结果
        subject_results[subject] = {{
            "accuracy": accuracy,
            "correct": correct,
            "total": total,
            "answers": answers
        }}
        
        print(f"科目 {{subject}} 准确率: {{accuracy:.4f}} ({{correct}}/{{total}})")
    
    # 计算总体平均准确率
    overall_accuracy = overall_correct / overall_total if overall_total > 0 else 0
    
    # 计算科目间平均准确率
    subject_accuracies = [subject_results[subject]["accuracy"] for subject in subject_results]
    avg_accuracy = sum(subject_accuracies) / len(subject_accuracies) if subject_accuracies else 0
    
    # 保存总体结果
    overall_results = {{
        "average_accuracy": avg_accuracy,
        "overall_accuracy": overall_accuracy,
        "benchmark": "MMLU-Pro",
        "subjects_evaluated": len(subject_results),
        "total_samples": overall_total,
        "correct_samples": overall_correct,
        "subject_results": subject_results
    }}
    
    # 保存结果到文件
    result_path = os.path.join("{output_dir}", "mmlu_pro_results.json")
    with open(result_path, "w") as f:
        json.dump(overall_results, f, indent=2)
    
    print(f"评估完成，平均准确率: {{avg_accuracy:.4f}}，总体准确率: {{overall_accuracy:.4f}}")
    print(f"结果已保存到: {{result_path}}")
    
except Exception as e:
    print(f"评估失败: {{str(e)}}")
    traceback.print_exc(file=sys.stdout)
    sys.exit(1)
"""
        
        # 写入脚本文件
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        # 确保脚本有执行权限
        os.chmod(script_path, 0o755)
        
        # 创建临时日志文件
        log_file = os.path.join(output_dir, "mmlu_pro_evaluation_log.txt")
        
        # 执行脚本
        add_evaluation_log(task_id, f"执行MMLU-Pro评估脚本: {script_path}")
        
        # 使用系统Python解释器执行脚本
        cmd = f"{sys.executable} {script_path} > {log_file} 2>&1"
        return_code = os.system(cmd)
        
        # 读取日志文件
        log_content = ""
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                log_content = f.read()
        
        # 记录日志
        if log_content:
            add_evaluation_log(task_id, f"MMLU-Pro评估日志:\n{log_content}")
        
        # 检查结果
        if return_code != 0:
            add_evaluation_log(task_id, f"MMLU-Pro评估失败，返回码: {return_code}", "ERROR")
            return False, "MMLU-Pro评估执行失败"
        
        # 检查结果文件
        result_path = os.path.join(output_dir, "mmlu_pro_results.json")
        if not os.path.exists(result_path):
            add_evaluation_log(task_id, "MMLU-Pro评估完成，但未找到结果文件", "ERROR")
            return False, "未找到MMLU-Pro结果文件"
        
        # 解析结果
        with open(result_path, 'r') as f:
            results = json.load(f)
        
        # 记录结果摘要
        avg_accuracy = results.get("average_accuracy", 0)
        overall_accuracy = results.get("overall_accuracy", 0)
        add_evaluation_log(task_id, f"MMLU-Pro评估成功完成，平均准确率: {avg_accuracy:.4f}，总体准确率: {overall_accuracy:.4f}")
        
        return True, result_path
        
    except Exception as e:
        error_msg = f"MMLU-Pro评估异常: {str(e)}"
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
        success, result_or_error = run_huggingface_evaluation(task_id, model_path, output_dir, evaluation_method)
        
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
    benchmarks.append({"id": BenchmarkType.MMLU_PRO, "name": "增强版MMLU", "category": "问答和知识检索", "description": "增强的MMLU，扩展了知识驱动的问题，整合了更具挑战性的推理问题，并将选项从四个扩展到十个"})
    
    return benchmarks 

# 添加datetime JSON序列化支持的函数
def datetime_serializer(obj):
    """处理datetime的JSON序列化"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"类型 {type(obj)} 无法被序列化为JSON")

def add_evaluation_log(task_id: int, content: str, level: str = "INFO"):
    """添加评估日志"""
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
        # 不要直接调用异步函数，而是返回它给调用者处理
        # 这是不正确的: send_evaluation_log(task_id, json.dumps(log_entry))
        
        # 以下是一个解决方案：将WebSocket发送操作与日志添加分离
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # 如果没有事件循环，则创建一个新的
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # 使用事件循环的run_in_executor来在后台运行
        loop.run_in_executor(None, lambda: asyncio.run(send_evaluation_log(task_id, json.dumps(log_entry))))
    except Exception as e:
        logger.error(f"WebSocket评估日志异常: {str(e)}") 