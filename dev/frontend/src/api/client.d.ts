import { AxiosInstance, AxiosResponse } from 'axios';

export const apiClient: AxiosInstance;

export const auth: {
  login: (username: string, password: string) => Promise<AxiosResponse<any>>;
  register: (userData: any) => Promise<AxiosResponse<any>>;
};

export const users: {
  getCurrentUser: () => Promise<AxiosResponse<any>>;
  updateProfile: (profileData: any) => Promise<AxiosResponse<any>>;
  changePassword: (passwordData: any) => Promise<AxiosResponse<any>>;
  getAllUsers: () => Promise<AxiosResponse<any>>;
};

export const resources: {
  getAll: () => Promise<AxiosResponse<any>>;
  create: (resourceData: any) => Promise<AxiosResponse<any>>;
  getById: (id: string | number) => Promise<AxiosResponse<any>>;
  download: (id: string | number, source?: string) => Promise<AxiosResponse<any>>;
  cancelDownload: (id: string | number) => Promise<AxiosResponse<any>>;
  retryDownload: (id: string | number, source?: string) => Promise<AxiosResponse<any>>;
  delete: (id: string | number) => Promise<AxiosResponse<any>>;
  getProgress: (id: string | number) => Promise<AxiosResponse<any>>;
};

export const checkServerStatus: () => Promise<AxiosResponse<any>>; 