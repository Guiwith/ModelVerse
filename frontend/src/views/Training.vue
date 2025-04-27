<template>
  <div class="training-page">
    <div class="page-header">
      <h1>模型训练</h1>
      <p class="subtitle">管理您的训练任务并基于现有模型创建新模型</p>
    </div>

    <div class="actions-bar">
      <button class="btn btn-primary" @click="showCreateDialog = true">
        <span class="material-icons">add</span> 创建训练任务
      </button>
    </div>

    <div v-if="loading" class="loading-container">
      <div class="loader"></div>
      <p>加载训练任务...</p>
    </div>

    <div v-else-if="error" class="error-message">
      <span class="material-icons">error</span>
      <p>{{ error }}</p>
      <button class="btn btn-outline" @click="loadTasks">重试</button>
    </div>

    <div v-else-if="tasks.length === 0" class="empty-state">
      <span class="material-icons">model_training</span>
      <h3>暂无训练任务</h3>
      <p>创建一个新的训练任务来开始模型训练</p>
      <button class="btn btn-primary" @click="showCreateDialog = true">创建训练任务</button>
    </div>

    <div v-else class="tasks-grid">
      <div v-for="task in tasks" :key="task.id" class="task-card">
        <div class="task-header">
          <h3 class="task-name">{{ task.name }}</h3>
          <span class="task-status" :class="getStatusClass(task.status)">
            {{ getStatusText(task.status) }}
          </span>
        </div>

        <div class="task-info">
          <div class="info-item">
            <span class="material-icons">model_training</span>
            <span>基础模型: {{ getResourceName(task.base_model_id) }}</span>
          </div>
          <div class="info-item">
            <span class="material-icons">dataset</span>
            <span>数据集: {{ getResourceName(task.dataset_id) }}</span>
          </div>
          <div class="info-item">
            <span class="material-icons">calendar_today</span>
            <span>创建时间: {{ formatDate(task.created_at) }}</span>
          </div>
        </div>

        <div v-if="task.status === 'RUNNING'" class="progress-bar">
          <div class="progress-fill" :style="{ width: `${task.progress * 100}%` }"></div>
          <span class="progress-text">{{ Math.round(task.progress * 100) }}%</span>
        </div>

        <div class="task-actions">
          <router-link :to="`/training/${task.id}`" class="btn btn-primary">
            <span class="material-icons">visibility</span> 查看详情
          </router-link>
          <button 
            v-if="task.status === 'PENDING'" 
            class="btn btn-success" 
            @click="startTask(task.id)">
            <span class="material-icons">play_arrow</span> 开始训练
          </button>
          <button 
            v-if="task.status === 'RUNNING'" 
            class="btn btn-danger" 
            @click="stopTask(task.id)">
            <span class="material-icons">stop</span> 停止训练
          </button>
          <button
            v-if="task.status !== 'RUNNING'"
            class="btn btn-danger"
            @click="deleteTask(task.id)">
            <span class="material-icons">delete</span> 删除
          </button>
        </div>
      </div>
    </div>

    <!-- 创建训练任务对话框 -->
    <div v-if="showCreateDialog" class="modal-overlay">
      <div class="modal-dialog">
        <div class="modal-header">
          <h2>创建训练任务</h2>
          <button class="btn-close" @click="showCreateDialog = false">
            <span class="material-icons">close</span>
          </button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label for="taskName">任务名称</label>
            <input 
              type="text" 
              id="taskName" 
              v-model="newTask.name" 
              class="form-control" 
              placeholder="例如：trained_mymodel"
              required
            >
          </div>
          
          <div class="form-group">
            <label for="baseModel">基础模型</label>
            <select 
              id="baseModel" 
              v-model="newTask.base_model_id" 
              class="form-control"
              required
            >
              <option disabled value="">选择基础模型</option>
              <option v-for="model in availableModels" :key="model.id" :value="model.id">
                {{ model.name }} ({{ model.repo_id }})
              </option>
            </select>
          </div>
          
          <div class="form-group">
            <label for="dataset">训练数据集</label>
            <select 
              id="dataset" 
              v-model="newTask.dataset_id" 
              class="form-control"
              required
            >
              <option disabled value="">选择数据集</option>
              <option v-for="dataset in availableDatasets" :key="dataset.id" :value="dataset.id">
                {{ dataset.name }} ({{ dataset.repo_id }})
              </option>
            </select>
          </div>
          
          <div class="form-group">
            <label>高级配置</label>
            <div class="advanced-config">
              <div class="config-section">
                <h4>模型配置</h4>
                <div class="config-item">
                  <label>最大序列长度</label>
                  <input type="number" v-model="config.model.model_max_length" class="form-control" />
                </div>
                <div class="config-item">
                  <label>数据类型</label>
                  <select v-model="config.model.torch_dtype_str" class="form-control">
                    <option value="float32">float32</option>
                    <option value="float16">float16</option>
                    <option value="bfloat16">bfloat16</option>
                  </select>
                </div>
                <div class="config-item">
                  <label>注意力实现</label>
                  <select v-model="config.model.attn_implementation" class="form-control">
                    <option value="sdpa">sdpa</option>
                    <option value="eager">eager</option>
                    <option value="flash_attention_2">flash_attention_2</option>
                  </select>
                </div>
                <div class="config-item">
                  <label>加载预训练权重</label>
                  <input type="checkbox" v-model="config.model.load_pretrained_weights" class="form-check" />
                </div>
                <div class="config-item">
                  <label>信任远程代码</label>
                  <input type="checkbox" v-model="config.model.trust_remote_code" class="form-check" />
                </div>
                <div class="config-item">
                  <label>启用Liger内核</label>
                  <input type="checkbox" v-model="config.model.enable_liger_kernel" class="form-check" />
                </div>
              </div>
              
              <div class="config-section">
                <h4>数据配置</h4>
                <div class="config-item">
                  <label>目标列名</label>
                  <input type="text" v-model="config.data.target_col" class="form-control" />
                </div>
              </div>
              
              <div class="config-section">
                <h4>训练配置</h4>
                <div class="config-item">
                  <label>训练类型</label>
                  <select v-model="config.training_type" class="form-control" @change="updateTrainerType">
                    <option value="SFT">SFT (监督微调)</option>
                    <option value="DPO">DPO (直接偏好优化)</option>
                    <option value="PRETRAIN">预训练</option>
                    <option value="FSDP">FSDP (全分片数据并行)</option>
                    <option value="FSDP_LORA">FSDP+LoRA</option>
                    <option value="DDP">DDP (分布式数据并行)</option>
                    <option value="LONGCTX">长上下文训练</option>
                  </select>
                </div>
                
                <!-- 长上下文训练选项 -->
                <div v-if="config.training_type === 'LONGCTX'" class="config-section nested-section">
                  <h5>长上下文训练设置</h5>
                  <div class="config-item">
                    <label>上下文长度</label>
                    <input type="number" v-model="config.model.model_max_length" class="form-control" />
                  </div>
                  <div class="config-item">
                    <label>启用Liger内核</label>
                    <input type="checkbox" v-model="config.model.enable_liger_kernel" class="form-check" />
                  </div>
                </div>
                
                <!-- FSDP配置 -->
                <div v-if="['FSDP', 'FSDP_LORA'].includes(config.training_type)" class="config-section nested-section">
                  <h5>FSDP设置</h5>
                  <div class="config-item">
                    <label>分片策略</label>
                    <select v-model="config.fsdp.sharding_strategy" class="form-control">
                      <option value="FULL_SHARD">FULL_SHARD</option>
                      <option value="HYBRID_SHARD">HYBRID_SHARD</option>
                      <option value="SHARD_GRAD_OP">SHARD_GRAD_OP</option>
                    </select>
                  </div>
                  <div class="config-item">
                    <label>启用前向预取</label>
                    <input type="checkbox" v-model="config.fsdp.forward_prefetch" class="form-check" />
                  </div>
                  <div class="config-item">
                    <label>Transformer层类</label>
                    <input type="text" v-model="config.fsdp.transformer_layer_cls" class="form-control" />
                  </div>
                </div>
                
                <!-- LoRA配置 -->
                <div v-if="config.training_type === 'FSDP_LORA'" class="config-section nested-section">
                  <h5>LoRA设置</h5>
                  <div class="config-item">
                    <label>LoRA秩(r)</label>
                    <input type="number" v-model="config.peft.lora_r" class="form-control" />
                  </div>
                  <div class="config-item">
                    <label>LoRA缩放(alpha)</label>
                    <input type="number" v-model="config.peft.lora_alpha" class="form-control" />
                  </div>
                  <div class="config-item">
                    <label>LoRA丢弃率</label>
                    <input type="number" v-model="config.peft.lora_dropout" step="0.01" class="form-control" />
                  </div>
                </div>
                
                <!-- 预训练特定配置 -->
                <div v-if="config.training_type === 'PRETRAIN'" class="config-section nested-section">
                  <h5>预训练设置</h5>
                  <div class="config-item">
                    <label>学习率调度器</label>
                    <select v-model="config.training.lr_scheduler_type" class="form-control">
                      <option value="cosine">cosine</option>
                      <option value="cosine_with_min_lr">cosine_with_min_lr</option>
                      <option value="linear">linear</option>
                    </select>
                  </div>
                  <div class="config-item">
                    <label>预热步数</label>
                    <input type="number" v-model="config.training.warmup_steps" class="form-control" />
                  </div>
                  <div class="config-item">
                    <label>权重衰减</label>
                    <input type="number" v-model="config.training.weight_decay" step="0.01" class="form-control" />
                  </div>
                </div>
                
                <div class="config-item">
                  <label>保存最终模型</label>
                  <input type="checkbox" v-model="config.training.save_final_model" class="form-check" />
                </div>
                <div class="config-item">
                  <label>保存步数</label>
                  <input type="number" v-model="config.training.save_steps" class="form-control" />
                </div>
                <div class="config-item">
                  <label>最大步数</label>
                  <input type="number" v-model="config.training.max_steps" class="form-control" />
                </div>
                <div class="config-item">
                  <label>每设备批处理大小</label>
                  <input type="number" v-model="config.training.per_device_train_batch_size" class="form-control" />
                </div>
                <div class="config-item">
                  <label>梯度累积步数</label>
                  <input type="number" v-model="config.training.gradient_accumulation_steps" class="form-control" />
                </div>
                <div class="config-item">
                  <label>DDP未使用参数</label>
                  <input type="checkbox" v-model="config.training.ddp_find_unused_parameters" class="form-check" />
                </div>
                <div class="config-item">
                  <label>优化器</label>
                  <select v-model="config.training.optimizer" class="form-control">
                    <option value="adamw_torch">adamw_torch</option>
                    <option value="adamw_hf">adamw_hf</option>
                    <option value="paged_adamw_32bit">paged_adamw_32bit</option>
                    <option value="paged_adamw_8bit">paged_adamw_8bit</option>
                  </select>
                </div>
                <div class="config-item">
                  <label>学习率</label>
                  <input type="number" v-model="config.training.learning_rate" step="0.00001" class="form-control" />
                </div>
                <div class="config-item">
                  <label>编译</label>
                  <input type="checkbox" v-model="config.training.compile" class="form-check" />
                </div>
                <div class="config-item">
                  <label>数据加载器工作进程数</label>
                  <input type="text" v-model="config.training.dataloader_num_workers" class="form-control" />
                </div>
                <div class="config-item">
                  <label>数据加载器预取因子</label>
                  <input type="number" v-model="config.training.dataloader_prefetch_factor" class="form-control" />
                </div>
                <div class="config-item">
                  <label>随机种子</label>
                  <input type="number" v-model="config.training.seed" class="form-control" />
                </div>
                <div class="config-item">
                  <label>使用确定性</label>
                  <input type="checkbox" v-model="config.training.use_deterministic" class="form-check" />
                </div>
                <div class="config-item">
                  <label>日志步数</label>
                  <input type="number" v-model="config.training.logging_steps" class="form-control" />
                </div>
                <div class="config-item">
                  <label>记录模型摘要</label>
                  <input type="checkbox" v-model="config.training.log_model_summary" class="form-check" />
                </div>
                <div class="config-item">
                  <label>清空设备缓存步数</label>
                  <input type="number" v-model="config.training.empty_device_cache_steps" class="form-control" />
                </div>
                <div class="config-item">
                  <label>包含性能指标</label>
                  <input type="checkbox" v-model="config.training.include_performance_metrics" class="form-check" />
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-outline" @click="showCreateDialog = false">取消</button>
          <button 
            class="btn btn-primary" 
            @click="createTask"
            :disabled="!isFormValid"
          >创建</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { apiClient } from '../api/client'
// @ts-ignore
import { useToast } from '../composables/toast'

export default {
  name: 'Training',
  setup() {
    const { showToast } = useToast()
    
    const tasks = ref<any[]>([])
    const loading = ref(true)
    const error = ref<string | null>(null)
    const showCreateDialog = ref(false)
    const availableModels = ref<any[]>([])
    const availableDatasets = ref<any[]>([])
    const allResources = ref<Record<string|number, string>>({})
    
    // 新任务表单
    const newTask = ref({
      name: '',
      base_model_id: '',
      dataset_id: '',
    })
    
    // 训练配置
    const config = ref({
      model: {
        model_max_length: 2048,
        torch_dtype_str: "bfloat16",
        attn_implementation: "sdpa",
        load_pretrained_weights: true,
        trust_remote_code: true,
        enable_liger_kernel: false
      },
      data: {
        target_col: "prompt"
      },
      training: {
        trainer_type: "TRL_SFT",
        save_final_model: true,
        save_steps: 100,
        max_steps: 10,
        per_device_train_batch_size: 4,
        gradient_accumulation_steps: 4,
        ddp_find_unused_parameters: false,
        optimizer: "adamw_torch",
        learning_rate: 2.0e-05,
        compile: false,
        dataloader_num_workers: "auto",
        dataloader_prefetch_factor: 32,
        seed: 192847,
        use_deterministic: true,
        logging_steps: 5,
        log_model_summary: false,
        empty_device_cache_steps: 50,
        include_performance_metrics: true,
        lr_scheduler_type: "cosine",
        warmup_steps: 500,
        weight_decay: 0.01
      },
      training_type: 'SFT',
      fsdp: {
        sharding_strategy: 'HYBRID_SHARD',
        forward_prefetch: true,
        transformer_layer_cls: 'LlamaDecoderLayer'
      },
      peft: {
        lora_r: 8,
        lora_alpha: 16,
        lora_dropout: 0.0
      }
    })
    
    // 表单验证
    const isFormValid = computed(() => {
      return newTask.value.name && 
             newTask.value.base_model_id && 
             newTask.value.dataset_id
    })
    
    // 加载训练任务
    const loadTasks = async () => {
      loading.value = true
      error.value = null
      
      try {
        const response = await apiClient.get('/api/training/tasks')
        tasks.value = Array.isArray(response.data) ? response.data : []
      } catch (err) {
        console.error('加载训练任务失败:', err)
        showToast('加载训练任务失败', 'error')
        error.value = '无法加载训练任务，请检查网络连接'
      } finally {
        loading.value = false
      }
    }
    
    // 加载可用资源
    const loadAvailableResources = async () => {
      try {
        // 加载基础模型
        const modelsResponse = await apiClient.get('/api/training/available-models')
        availableModels.value = Array.isArray(modelsResponse.data) ? modelsResponse.data : []
        
        // 加载数据集
        const datasetsResponse = await apiClient.get('/api/training/available-datasets')
        availableDatasets.value = Array.isArray(datasetsResponse.data) ? datasetsResponse.data : []
        
        // 建立资源ID到名称的映射
        const resourcesList = [...availableModels.value, ...availableDatasets.value]
        resourcesList.forEach(resource => {
          allResources.value[resource.id] = resource.name
        })
      } catch (err) {
        console.error('加载可用资源失败:', err)
        showToast('加载可用资源失败', 'error')
        error.value = '无法加载可用资源，请检查网络连接'
      }
    }
    
    // 加载默认配置
    const loadDefaultConfig = async () => {
      try {
        const response = await apiClient.get('/api/training/default-config')
        config.value = response.data as typeof config.value
        
        // 将默认值复制到新任务表单
        resetConfig()
      } catch (err) {
        console.error('加载默认配置失败:', err)
        showToast('加载默认配置失败', 'error')
        error.value = '无法加载默认配置，请检查网络连接'
      }
    }
    
    // 重置配置为默认值
    const resetConfig = () => {
      if (config.value) {
        // 复制默认配置到当前配置
        Object.keys(config.value).forEach(key => {
          if (typeof config.value[key] === 'object') {
            config.value[key] = { ...config.value[key] }
          }
        })
      }
    }
    
    // 创建训练任务
    const createTask = async () => {
      try {
        // 准备任务数据
        const taskData = {
          name: newTask.value.name,
          base_model_id: Number(newTask.value.base_model_id),
          dataset_id: Number(newTask.value.dataset_id),
          config_params: {
            model: config.value.model,
            data: config.value.data,
            training: config.value.training
          }
        }
        
        // 发送请求
        await apiClient.post('/api/training/tasks', taskData)
        
        // 关闭对话框并重新加载任务
        showCreateDialog.value = false
        await loadTasks()
        
        // 重置表单
        newTask.value = {
          name: '',
          base_model_id: '',
          dataset_id: '',
        }
        
        showToast('训练任务创建成功', 'success')
      } catch (err) {
        console.error('创建训练任务失败:', err)
        showToast(`创建训练任务失败: ${err.response?.data?.detail || '未知错误'}`, 'error')
      }
    }
    
    // 开始训练任务
    const startTask = async (taskId) => {
      try {
        await apiClient.post(`/api/training/tasks/${taskId}/start`)
        showToast('训练任务已启动', 'success')
        await loadTasks() // 刷新任务列表
      } catch (err) {
        console.error('开始训练任务失败:', err)
        showToast(`开始训练任务失败: ${err.response?.data?.detail || '未知错误'}`, 'error')
      }
    }
    
    // 停止训练任务
    const stopTask = async (taskId) => {
      if (confirm('确定要停止此训练任务吗？')) {
        try {
          await apiClient.post(`/api/training/tasks/${taskId}/stop`)
          showToast('训练任务已停止', 'success')
          await loadTasks() // 刷新任务列表
        } catch (err) {
          console.error('停止训练任务失败:', err)
          showToast(`停止训练任务失败: ${err.response?.data?.detail || '未知错误'}`, 'error')
        }
      }
    }
    
    // 删除训练任务
    const deleteTask = async (taskId) => {
      if (!confirm(`确定要删除任务 #${taskId}? 这将永久删除所有相关文件和目录，包括：
- 训练配置文件
- 训练输出目录
- 训练日志数据
      
此操作不可恢复!`)) {
        return
      }
      
      try {
        loading.value = true
        const response = await apiClient.delete(`/api/training/tasks/${taskId}`)
        
        // 显示删除结果
        showToast('训练任务已删除', 'success')
        
        // 重新加载任务列表
        loadTasks()
      } catch (error) {
        console.error('删除训练任务失败:', error)
        showToast(`删除失败: ${error.response?.data?.detail || error.message}`, 'error')
      } finally {
        loading.value = false
      }
    }
    
    // 获取资源名称
    const getResourceName = (resourceId) => {
      return allResources.value[resourceId] || `资源#${resourceId}`
    }
    
    // 格式化日期
    const formatDate = (dateString) => {
      if (!dateString) return ''
      const date = new Date(dateString)
      return date.toLocaleString()
    }
    
    // 获取状态文本
    const getStatusText = (status) => {
      const statusMap = {
        'PENDING': '等待中',
        'RUNNING': '运行中',
        'COMPLETED': '已完成',
        'FAILED': '失败',
        'STOPPED': '已停止'
      }
      return statusMap[status] || status
    }
    
    // 获取状态样式类
    const getStatusClass = (status) => {
      const classMap = {
        'PENDING': 'status-pending',
        'RUNNING': 'status-running',
        'COMPLETED': 'status-completed',
        'FAILED': 'status-failed',
        'STOPPED': 'status-stopped'
      }
      return classMap[status] || ''
    }
    
    // 更新训练器类型
    const updateTrainerType = () => {
      switch(config.value.training_type) {
        case 'DPO':
          config.value.training.trainer_type = 'TRL_DPO'
          break;
        case 'SFT':
        case 'FSDP':
        case 'FSDP_LORA':
        case 'DDP':
        case 'LONGCTX':
        case 'PRETRAIN':
          config.value.training.trainer_type = 'TRL_SFT'
          break;
        default:
          config.value.training.trainer_type = 'TRL_SFT'
      }
    }
    
    // 组件挂载时加载数据
    onMounted(() => {
      loadTasks()
      loadAvailableResources()
      loadDefaultConfig()
      updateTrainerType()
    })
    
    return {
      tasks,
      loading,
      error,
      showCreateDialog,
      availableModels,
      availableDatasets,
      allResources,
      newTask,
      config,
      isFormValid,
      
      loadTasks,
      loadAvailableResources,
      createTask,
      startTask,
      stopTask,
      deleteTask,
      formatDate,
      getResourceName,
      getStatusText,
      getStatusClass,
      updateTrainerType
    }
  }
}
</script>

<style scoped>
.training-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.page-header {
  margin-bottom: 24px;
}

.page-header h1 {
  font-size: 28px;
  margin-bottom: 8px;
}

.subtitle {
  color: var(--text-secondary);
  font-size: 16px;
}

.actions-bar {
  margin-bottom: 24px;
}

.tasks-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: 24px;
}

.task-card {
  background-color: var(--bg-card);
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  padding: 16px;
  transition: transform 0.2s, box-shadow 0.2s;
}

.task-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.task-name {
  font-size: 18px;
  margin: 0;
}

.task-status {
  display: inline-block;
  padding: 4px 8px;
  border-radius: 16px;
  font-size: 12px;
  font-weight: 500;
}

.status-pending {
  background-color: #fff8e1;
  color: #ff9e80;
}

.status-running {
  background-color: #e3f2fd;
  color: #2196f3;
}

.status-completed {
  background-color: #e8f5e9;
  color: #4caf50;
}

.status-failed {
  background-color: #ffebee;
  color: #f44336;
}

.status-stopped {
  background-color: #f5f5f5;
  color: #9e9e9e;
}

.task-info {
  margin-bottom: 16px;
}

.info-item {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
  color: var(--text-secondary);
}

.info-item .material-icons {
  font-size: 18px;
  margin-right: 8px;
}

.progress-bar {
  height: 8px;
  background-color: var(--bg-card-secondary);
  border-radius: 4px;
  margin-bottom: 16px;
  position: relative;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background-color: #2196f3;
  transition: width 0.3s;
}

.progress-text {
  position: absolute;
  right: 0;
  top: -18px;
  font-size: 12px;
  color: #2196f3;
}

.task-actions {
  display: flex;
  gap: 8px;
}

/* 按钮样式 */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 8px 16px;
  font-size: 14px;
  font-weight: 500;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s, transform 0.1s;
  border: none;
  gap: 8px;
}

.btn:hover {
  transform: translateY(-1px);
}

.btn:active {
  transform: translateY(0);
}

.btn-primary {
  background-color: #ff9e80;
  color: white;
  border: 1px solid transparent;
}

.btn-primary:hover {
  background-color: #ff9e80;
  filter: brightness(1.1);
}

[data-theme="dark"] .btn-primary {
  background-color: #ff9e80;
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.btn-outline {
  background-color: transparent;
  color: var(--primary, #1976d2);
  border: 1px solid var(--primary, #1976d2);
}

.btn-outline:hover {
  background-color: rgba(var(--primary-rgb, '25, 118, 210'), 0.05);
}

[data-theme="dark"] .btn-outline {
  color: var(--primary, #1976d2);
  border: 1px solid var(--primary, #1976d2);
}

.btn-warning {
  background-color: #ff9e80;
  color: white;
  border: 1px solid transparent;
}

.btn-warning:hover {
  background-color: #ff9e80;
  filter: brightness(1.1);
}

[data-theme="dark"] .btn-warning {
  background-color: #ff9e80;
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.btn-success {
  background-color: #4CAF50;
  color: white;
}

[data-theme="dark"] .btn-success {
  background-color: #4CAF50;
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.btn-danger {
  background-color: #F44336;
  color: white;
}

[data-theme="dark"] .btn-danger {
  background-color: #F44336;
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.loading-container, .empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 60px 0;
  text-align: center;
}

.loader {
  border: 4px solid var(--bg-card-secondary);
  border-top: 4px solid var(--primary);
  border-radius: 50%;
  width: 40px;
  height: 40px;
  animation: spin 1s linear infinite;
  margin-bottom: 16px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.empty-state .material-icons {
  font-size: 48px;
  color: var(--text-tertiary);
  margin-bottom: 16px;
}

.empty-state h3 {
  font-size: 20px;
  margin-bottom: 8px;
}

.empty-state p {
  color: var(--text-secondary);
  margin-bottom: 20px;
}

.error-message {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40px 20px;
  color: #f44336;
  text-align: center;
}

.error-message .material-icons {
  font-size: 48px;
  margin-bottom: 16px;
}

/* 创建任务对话框 */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-dialog {
  background-color: var(--bg-card);
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  width: 100%;
  max-width: 600px;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
}

.modal-header h2 {
  font-size: 20px;
  margin: 0;
}

.btn-close {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 24px;
  color: var(--text-tertiary);
}

.modal-body {
  padding: 20px;
}

.modal-footer {
  padding: 16px 20px;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  border-top: 1px solid var(--border-color);
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
}

.form-control {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  background-color: var(--bg-card);
  color: var(--text-primary);
  font-size: 14px;
  transition: all 0.2s ease;
}

.form-control:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 2px rgba(var(--primary-rgb), 0.1);
}

.form-control::placeholder {
  color: var(--text-secondary);
  opacity: 0.7;
}

select.form-control {
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 8px center;
  background-size: 16px;
  padding-right: 32px;
  cursor: pointer;
}

select.form-control option {
  background-color: var(--bg-card);
  color: var(--text-primary);
  padding: 8px;
}

select.form-control:focus option:checked {
  background-color: var(--primary);
  color: var(--text-on-primary);
}

select.form-control option:hover {
  background-color: var(--bg-card-secondary);
}

/* 高级配置 */
.advanced-config {
  background-color: var(--bg-card-secondary);
  border-radius: 6px;
  padding: 16px;
  margin-top: 8px;
}

.config-section {
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-color);
}

.config-section:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}

.config-section h4 {
  margin-top: 0;
  margin-bottom: 12px;
  font-size: 16px;
  color: var(--text-secondary);
}

.config-items {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 16px;
}

.config-item {
  margin-bottom: 12px;
}

.config-item label {
  display: block;
  margin-bottom: 4px;
  font-size: 14px;
  color: var(--text-secondary);
}

.form-check {
  margin-top: 8px;
  width: 18px;
  height: 18px;
  cursor: pointer;
}

/* 添加嵌套配置部分的样式 */
.nested-section {
  margin-top: 10px;
  margin-left: 15px;
  padding: 10px;
  border-left: 2px solid var(--primary-light);
  background-color: var(--bg-card-secondary);
  border-radius: 0 4px 4px 0;
}

.nested-section h5 {
  font-size: 14px;
  margin-top: 0;
  margin-bottom: 10px;
  color: var(--primary);
}

@media (max-width: 768px) {
  .tasks-grid {
    grid-template-columns: 1fr;
  }

  .task-actions {
    flex-direction: column;
  }
  
  .config-items {
    grid-template-columns: 1fr;
  }
}
</style> 