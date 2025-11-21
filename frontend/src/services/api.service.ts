/**
 * API Service Layer
 * Handles all HTTP requests with automatic JWT token management
 * This ensures proper authentication for frontend-backend communication
 */

import axios, { AxiosInstance, AxiosRequestConfig, AxiosError } from 'axios';

// API Base URL
const API_BASE_URL = process.env.REACT_APP_API_URL || '/api/v1';

// Token storage keys
const ACCESS_TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';

/**
 * Create axios instance with base configuration
 */
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 seconds
});

/**
 * Request interceptor - Add JWT token to every request
 */
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);

    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

/**
 * Response interceptor - Handle token refresh on 401 errors
 */
let isRefreshing = false;
let failedQueue: any[] = [];

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });

  failedQueue = [];
};

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest: any = error.config;

    // Handle 401 Unauthorized
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        // Queue the request if token is being refreshed
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            return apiClient(originalRequest);
          })
          .catch((err) => {
            return Promise.reject(err);
          });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);

      if (!refreshToken) {
        // No refresh token, redirect to login
        clearTokens();
        window.location.href = '/login';
        return Promise.reject(error);
      }

      try {
        // Attempt to refresh the token
        const response = await axios.post(`${API_BASE_URL}/token/refresh/`, {
          refresh: refreshToken,
        });

        const { access, refresh } = response.data;

        // Save new tokens
        localStorage.setItem(ACCESS_TOKEN_KEY, access);
        if (refresh) {
          localStorage.setItem(REFRESH_TOKEN_KEY, refresh);
        }

        // Update the original request with new token
        originalRequest.headers.Authorization = `Bearer ${access}`;

        processQueue(null, access);
        isRefreshing = false;

        // Retry the original request
        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        isRefreshing = false;

        // Refresh failed, redirect to login
        clearTokens();
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

/**
 * Token management functions
 */
export const setTokens = (access: string, refresh: string) => {
  localStorage.setItem(ACCESS_TOKEN_KEY, access);
  localStorage.setItem(REFRESH_TOKEN_KEY, refresh);

  // Set cookie for WebSocket authentication (SameSite=Lax for CSRF protection)
  // Note: Not using Secure flag since this is for local network (HTTP)
  document.cookie = `access_token=${access}; path=/; SameSite=Lax`;
};

export const getAccessToken = (): string | null => {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
};

export const getRefreshToken = (): string | null => {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
};

export const clearTokens = () => {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);

  // Clear cookie (set expiry in the past)
  document.cookie = 'access_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT';
};

export const isAuthenticated = (): boolean => {
  return !!getAccessToken();
};

/**
 * API Service
 */
class APIService {
  /**
   * Authentication endpoints
   */
  auth = {
    login: async (email: string, password: string, twoFactorToken?: string) => {
      const response = await apiClient.post('/token/', {
        email,
        password,
        two_factor_token: twoFactorToken,
      });
      return response.data;
    },

    register: async (userData: any) => {
      const response = await apiClient.post('/auth/register/', userData);
      return response.data;
    },

    logout: async () => {
      const refreshToken = getRefreshToken();
      const response = await apiClient.post('/auth/logout/', {
        refresh: refreshToken,
      });
      clearTokens();
      return response.data;
    },

    refreshToken: async () => {
      const refreshToken = getRefreshToken();
      const response = await apiClient.post('/token/refresh/', {
        refresh: refreshToken,
      });
      return response.data;
    },
  };

  /**
   * User endpoints
   */
  users = {
    getMe: async () => {
      const response = await apiClient.get('/users/me/');
      return response.data;
    },

    updateProfile: async (data: any) => {
      const response = await apiClient.patch('/users/update_profile/', data);
      return response.data;
    },

    changePassword: async (oldPassword: string, newPassword: string, newPasswordConfirm: string) => {
      const response = await apiClient.post('/users/change_password/', {
        old_password: oldPassword,
        new_password: newPassword,
        new_password_confirm: newPasswordConfirm,
      });
      return response.data;
    },

    enable2FA: async () => {
      const response = await apiClient.post('/users/enable_2fa/');
      return response.data;
    },

    verify2FA: async (token: string) => {
      const response = await apiClient.post('/users/verify_2fa/', { token });
      return response.data;
    },

    disable2FA: async (password: string) => {
      const response = await apiClient.post('/users/disable_2fa/', { password });
      return response.data;
    },

    list: async (params?: any) => {
      const response = await apiClient.get('/users/', { params });
      return response.data;
    },

    get: async (id: number) => {
      const response = await apiClient.get(`/users/${id}/`);
      return response.data;
    },

    create: async (data: any) => {
      const response = await apiClient.post('/users/', data);
      return response.data;
    },

    update: async (id: number, data: any) => {
      const response = await apiClient.patch(`/users/${id}/`, data);
      return response.data;
    },

    delete: async (id: number) => {
      const response = await apiClient.delete(`/users/${id}/`);
      return response.data;
    },
  };

  /**
   * Audit logs endpoints
   */
  auditLogs = {
    list: async (params?: any) => {
      const response = await apiClient.get('/audit-logs/', { params });
      return response.data;
    },

    get: async (id: number) => {
      const response = await apiClient.get(`/audit-logs/${id}/`);
      return response.data;
    },
  };

  /**
   * Dashboard endpoints
   */
  dashboard = {
    getStatistics: async () => {
      const response = await apiClient.get('/dashboard/statistics/');
      return response.data;
    },

    getBackupTrend: async (days: number = 7) => {
      const response = await apiClient.get('/dashboard/backup-trend/', { params: { days } });
      return response.data;
    },

    getRecentBackups: async (limit: number = 10) => {
      const response = await apiClient.get('/dashboard/recent-backups/', { params: { limit } });
      return response.data;
    },
  };

  /**
   * Vendors endpoints
   */
  vendors = {
    list: async (params?: any) => {
      const response = await apiClient.get('/devices/vendors/', { params });
      return response.data;
    },

    get: async (id: number) => {
      const response = await apiClient.get(`/devices/vendors/${id}/`);
      return response.data;
    },

    create: async (data: any) => {
      const response = await apiClient.post('/devices/vendors/', data);
      return response.data;
    },

    update: async (id: number, data: any) => {
      const response = await apiClient.patch(`/devices/vendors/${id}/`, data);
      return response.data;
    },

    delete: async (id: number) => {
      const response = await apiClient.delete(`/devices/vendors/${id}/`);
      return response.data;
    },
  };

  /**
   * Device Types endpoints
   */
  deviceTypes = {
    list: async (params?: any) => {
      const response = await apiClient.get('/devices/device-types/', { params });
      return response.data;
    },

    get: async (id: number) => {
      const response = await apiClient.get(`/devices/device-types/${id}/`);
      return response.data;
    },

    create: async (data: any) => {
      const response = await apiClient.post('/devices/device-types/', data);
      return response.data;
    },

    update: async (id: number, data: any) => {
      const response = await apiClient.patch(`/devices/device-types/${id}/`, data);
      return response.data;
    },

    delete: async (id: number) => {
      const response = await apiClient.delete(`/devices/device-types/${id}/`);
      return response.data;
    },
  };

  /**
   * Devices endpoints
   */
  devices = {
    list: async (params?: any) => {
      const response = await apiClient.get('/devices/devices/', { params });
      return response.data;
    },

    get: async (id: number) => {
      const response = await apiClient.get(`/devices/devices/${id}/`);
      return response.data;
    },

    create: async (data: any) => {
      const response = await apiClient.post('/devices/devices/', data);
      return response.data;
    },

    update: async (id: number, data: any) => {
      const response = await apiClient.patch(`/devices/devices/${id}/`, data);
      return response.data;
    },

    delete: async (id: number) => {
      const response = await apiClient.delete(`/devices/devices/${id}/`);
      return response.data;
    },

    testConnection: async (id: number) => {
      const response = await apiClient.post(`/devices/devices/${id}/test_connection/`);
      return response.data;
    },

    backupNow: async (id: number) => {
      const response = await apiClient.post(`/devices/devices/${id}/backup_now/`);
      return response.data;
    },

    statistics: async () => {
      const response = await apiClient.get('/devices/devices/statistics/');
      return response.data;
    },

    csvTemplate: async (lang: string) => {
      const response = await apiClient.get(`/devices/devices/csv_template/?lang=${lang}`, {
        responseType: 'blob',
      });
      return response;
    },

    csvPreview: async (file: File) => {
      const formData = new FormData();
      formData.append('file', file);
      const response = await apiClient.post('/devices/devices/csv_preview/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return response.data;
    },

    csvImport: async (file: File, options: { skip_duplicates?: boolean; update_existing?: boolean }) => {
      const formData = new FormData();
      formData.append('file', file);
      if (options.skip_duplicates !== undefined) {
        formData.append('skip_duplicates', String(options.skip_duplicates));
      }
      if (options.update_existing !== undefined) {
        formData.append('update_existing', String(options.update_existing));
      }
      const response = await apiClient.post('/devices/devices/csv_import/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return response.data;
    },
  };

  /**
   * Backups endpoints
   */
  backups = {
    list: async (params?: any) => {
      const response = await apiClient.get('/backups/backups/', { params });
      return response.data;
    },

    get: async (id: number) => {
      const response = await apiClient.get(`/backups/backups/${id}/`);
      return response.data;
    },

    getConfiguration: async (id: number) => {
      const response = await apiClient.get(`/backups/backups/${id}/configuration/`);
      return response.data;
    },

    download: async (id: number) => {
      const response = await apiClient.get(`/backups/backups/${id}/download/`, {
        responseType: 'blob',
      });
      return response.data;
    },

    compare: async (id1: number, id2: number) => {
      const response = await apiClient.get(`/backups/backups/${id1}/compare/${id2}/`);
      return response.data;
    },

    delete: async (id: number) => {
      const response = await apiClient.delete(`/backups/backups/${id}/`);
      return response.data;
    },

    getGrouped: async (groupBy: 'date' | 'vendor' | 'device_type' = 'date', params?: any) => {
      const response = await apiClient.get('/backups/backups/grouped/', {
        params: { ...params, group_by: groupBy }
      });
      return response.data;
    },

    downloadMultiple: async (backupIds: number[]) => {
      const response = await apiClient.post('/backups/backups/download_multiple/',
        { backup_ids: backupIds },
        { responseType: 'blob' }
      );
      return response.data;
    },

    searchConfigs: async (query: string, options?: { caseSensitive?: boolean; regex?: boolean }) => {
      const response = await apiClient.get('/backups/backups/search_configs/', {
        params: {
          q: query,
          case_sensitive: options?.caseSensitive || false,
          regex: options?.regex || false,
        }
      });
      return response.data;
    },
  };

  /**
   * Backup Schedules endpoints
   */
  backupSchedules = {
    list: async (params?: any) => {
      const response = await apiClient.get('/backups/schedules/', { params });
      return response.data;
    },

    get: async (id: number) => {
      const response = await apiClient.get(`/backups/schedules/${id}/`);
      return response.data;
    },

    create: async (data: any) => {
      const response = await apiClient.post('/backups/schedules/', data);
      return response.data;
    },

    update: async (id: number, data: any) => {
      const response = await apiClient.patch(`/backups/schedules/${id}/`, data);
      return response.data;
    },

    delete: async (id: number) => {
      const response = await apiClient.delete(`/backups/schedules/${id}/`);
      return response.data;
    },

    toggleActive: async (id: number) => {
      const response = await apiClient.post(`/backups/schedules/${id}/toggle_active/`);
      return response.data;
    },

    runNow: async (id: number) => {
      const response = await apiClient.post(`/backups/schedules/${id}/run_now/`);
      return response.data;
    },
  };

  retentionPolicies = {
    list: async (params?: any) => {
      const response = await apiClient.get('/backups/retention-policies/', { params });
      return response.data;
    },

    get: async (id: number) => {
      const response = await apiClient.get(`/backups/retention-policies/${id}/`);
      return response.data;
    },

    create: async (data: any) => {
      const response = await apiClient.post('/backups/retention-policies/', data);
      return response.data;
    },

    update: async (id: number, data: any) => {
      const response = await apiClient.patch(`/backups/retention-policies/${id}/`, data);
      return response.data;
    },

    delete: async (id: number) => {
      const response = await apiClient.delete(`/backups/retention-policies/${id}/`);
      return response.data;
    },

    applyNow: async (id: number) => {
      const response = await apiClient.post(`/backups/retention-policies/${id}/apply_now/`);
      return response.data;
    },
  };

  /**
   * System Settings endpoints (admin only)
   */
  systemSettings = {
    get: async () => {
      const response = await apiClient.get('/settings/system/');
      return response.data;
    },

    update: async (data: any) => {
      const response = await apiClient.post('/settings/system/update/', data);
      return response.data;
    },

    testEmail: async (email: string) => {
      const response = await apiClient.post('/settings/test-email/', { email });
      return response.data;
    },

    testTelegram: async (botToken: string, chatId: string) => {
      const response = await apiClient.post('/settings/test-telegram/', {
        bot_token: botToken,
        chat_id: chatId,
      });
      return response.data;
    },
  };

  /**
   * Generic request methods
   */
  get = async (url: string, config?: AxiosRequestConfig) => {
    const response = await apiClient.get(url, config);
    return response.data;
  };

  post = async (url: string, data?: any, config?: AxiosRequestConfig) => {
    const response = await apiClient.post(url, data, config);
    return response.data;
  };

  put = async (url: string, data?: any, config?: AxiosRequestConfig) => {
    const response = await apiClient.put(url, data, config);
    return response.data;
  };

  patch = async (url: string, data?: any, config?: AxiosRequestConfig) => {
    const response = await apiClient.patch(url, data, config);
    return response.data;
  };

  delete = async (url: string, config?: AxiosRequestConfig) => {
    const response = await apiClient.delete(url, config);
    return response.data;
  };

  request = async (method: string, url: string, data?: any, config?: AxiosRequestConfig) => {
    const response = await apiClient.request({ method, url, data, ...config });
    return response.data;
  };
}

// Export singleton instance
export default new APIService();

// Export axios instance for advanced usage
export { apiClient };
