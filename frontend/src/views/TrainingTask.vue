<template>
  <!-- No changes to template section -->
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

const deleteTask = async (taskId) => {
  if (!confirm(`确定要删除任务 #${taskId}? 这将永久删除所有相关文件和目录。`)) {
    return
  }
  
  try {
    loading.value = true
    const response = await training.deleteTask(taskId)
    
    // 显示删除结果，包括清理的文件
    const result = response.data
    let message = `任务删除成功!`
    
    if (result.cleaned_files && result.cleaned_files.length > 0) {
      message += `\n\n已清理以下文件:\n${result.cleaned_files.join('\n')}`
    }
    
    if (result.errors && result.errors.length > 0) {
      message += `\n\n清理过程中出现以下错误:\n${result.errors.join('\n')}`
    }
    
    ElMessage({
      message,
      type: 'success',
      duration: 5000
    })
    
    // 从列表中移除
    fetchTaskList()
  } catch (error) {
    ElMessage.error(`删除失败: ${error.response?.data?.detail || error.message}`)
  } finally {
    loading.value = false
  }
}
</script> 