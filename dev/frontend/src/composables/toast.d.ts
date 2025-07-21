import { Ref } from 'vue'

export interface Toast {
  id: number
  message: string
  type: string
  show: boolean
}

export interface UseToast {
  toasts: Ref<Toast[]>
  showToast: (message: string, type?: string, duration?: number) => number
  hideToast: (id: number) => void
}

export function useToast(): UseToast 