export interface User {
  id: number;
  username: string;
  email: string;
  is_admin: boolean;
  created_at: string;
}

export interface UserCreate {
  username: string;
  email: string;
  password: string;
  is_admin: boolean;
}

export interface DashboardData {
  user_count: number;
  message?: string;
}

// Hugging Face resource types
export interface HFResource {
  id: string;
  modelId: string;
  name?: string;
  description?: string;
  downloads?: number;
  likes?: number;
  tags?: string[];
  lastModified?: string;
  author?: string;
  type: 'model' | 'dataset';
  size?: number;
  pipeline_tag?: string;
}

// 额外的Hugging Face模型详情
export interface HFModelDetails extends HFResource {
  framework?: string;
  license?: string;
  paperUrl?: string;
  githubUrl?: string;
  metrics?: Record<string, number>;
  languages?: string[];
  downloadStatus?: DownloadStatus;
  localPath?: string;
}

// 下载状态
export type DownloadStatus = 
  | 'not_downloaded' 
  | 'downloading' 
  | 'downloaded' 
  | 'error';

// 下载进度信息
export interface DownloadProgress {
  resourceId: string;
  progress: number;
  speed: number;
  eta: number;
  status: DownloadStatus;
  error?: string;
}

// 任务类型
export type TaskType = 
  | 'text-classification'
  | 'token-classification'
  | 'question-answering'
  | 'translation'
  | 'summarization'
  | 'text-generation'
  | 'fill-mask'
  | 'image-classification'
  | 'object-detection'
  | 'image-segmentation'
  | 'audio-classification'
  | 'automatic-speech-recognition'
  | 'other';

// 搜索过滤条件
export interface SearchFilters {
  taskType?: TaskType;
  modelType?: string;
  languages?: string[];
  datasets?: string[];
  license?: string;
  sortBy?: 'downloads' | 'likes' | 'date';
  order?: 'asc' | 'desc';
}

export interface SearchResult {
  items: HFResource[];
  totalCount: number;
}

export interface StorageInfo {
  totalSize: number;
  modelDirSize: number;
  datasetDirSize: number;
  availableSpace: number;
}

// Hugging Face API响应类型
export interface HFApiResponse<T> {
  data: T;
  success: boolean;
  message?: string;
  errors?: Record<string, string[]>;
}

// Hugging Face资源集合
export interface HFResourceCollection {
  models: HFResource[];
  datasets: HFResource[];
}

// Hugging Face模型参数
export interface HFModelParams {
  model_id: string;
  task_type: TaskType;
  framework?: string;
  revision?: string;
  quantization?: string;
}

// Hugging Face数据集参数
export interface HFDatasetParams {
  dataset_id: string;
  subset?: string;
  split?: string;
  revision?: string;
}

// Hugging Face搜索高级过滤条件
export interface HFAdvancedFilters extends SearchFilters {
  author?: string;
  minDownloads?: number;
  minLikes?: number;
  createdAfter?: string;
  updatedAfter?: string;
  excludeTags?: string[];
  includePrivate?: boolean;
  framework?: string[];
}

// Hugging Face精细任务类型
export interface HFTaskConfig {
  taskType: TaskType;
  supportedFrameworks: string[];
  requiredResources: {
    minRAM?: number;
    minGPU?: number;
    recommendedBatchSize?: number;
  };
  defaultHyperParams: Record<string, any>;
  metricKeys: string[];
} 