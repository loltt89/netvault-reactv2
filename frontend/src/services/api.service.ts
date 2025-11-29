/**
 * API Service Layer
 * Handles all HTTP requests with automatic JWT token management
 * Tokens are stored in HttpOnly cookies (secure) with in-memory fallback
 */

import axios, { AxiosInstance, AxiosRequestConfig, AxiosError } from 'axios';

// API Base URL
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

// In-memory token storage (access token only, refresh is in HttpOnly cookie)
let accessToken: string | null = null;

/**
 * Create axios instance with base configuration
 */
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
  withCredentials: true, // Send cookies with requests
});

/**
 * Request interceptor - Add JWT token to every request
 */
apiClient.interceptors.request.use(
  (config) => {
    // Use in-memory token if available (for backward compatibility)
    if (accessToken) {
      config.headers.Authorization = `Bearer ${accessToken}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

/**
 * Response interceptor - Handle token refresh on 401 errors
 * Uses promise-based queue to prevent race conditions when multiple requests fail simultaneously
 */
let isRefreshing = false;
let refreshPromise: Promise<string> | null = null;

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest: any = error.config;

    // Handle 401 Unauthorized
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      if (isRefreshing && refreshPromise) {
        // Another request is already refreshing the token, wait for it
        try {
          const newToken = await refreshPromise;
          if (newToken) {
            originalRequest.headers.Authorization = `Bearer ${newToken}`;
          }
          return apiClient(originalRequest);
        } catch (refreshError) {
          return Promise.reject(refreshError);
        }
      }

      // Start refresh process
      isRefreshing = true;
      refreshPromise = (async () => {
        try {
          // Attempt to refresh using HttpOnly cookie (no body needed)
          const response = await axios.post(
            `${API_BASE_URL}/token/refresh/`,
            {},
            { withCredentials: true }
          );

          const { access } = response.data;

          // Save new access token in memory
          accessToken = access;

          return access;
        } catch (refreshError) {
          // Refresh failed, clear tokens
          clearTokens();
          // Only redirect to login if not already on login page (prevent infinite loop)
          if (window.location.pathname !== '/login') {
            window.location.href = '/login';
          }
          throw refreshError;
        } finally {
          isRefreshing = false;
          refreshPromise = null;
        }
      })();

      try {
        const newToken = await refreshPromise;
        if (newToken) {
          originalRequest.headers.Authorization = `Bearer ${newToken}`;
        }
        return apiClient(originalRequest);
      } catch (refreshError) {
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

/**
 * Token management functions
 */
export const setTokens = (access: string, _refresh?: string) => {
  // Store access token in memory (not localStorage for XSS protection)
  accessToken = access;
  // Refresh token is handled by HttpOnly cookie set by server
};

export const getAccessToken = (): string | null => {
  return accessToken;
};

export const getRefreshToken = (): string | null => {
  // Refresh token is in HttpOnly cookie, not accessible from JS
  return null;
};

export const clearTokens = () => {
  accessToken = null;
  // Cookies will be cleared by server on logout
};

export const isAuthenticated = (): boolean => {
  return !!accessToken;
};

/**
 * CRUD Service Factory
 * Creates reusable CRUD methods for resources to avoid code duplication
 */
interface CrudService {
  list: (params?: any) => Promise<any>;
  get: (id: number) => Promise<any>;
  create: (data: any) => Promise<any>;
  update: (id: number, data: any) => Promise<any>;
  delete: (id: number) => Promise<any>;
}

function createCrudService(resource: string): CrudService {
  return {
    list: async (params?: any) => {
      const response = await apiClient.get(`/${resource}/`, { params });
      return response.data;
    },

    get: async (id: number) => {
      const response = await apiClient.get(`/${resource}/${id}/`);
      return response.data;
    },

    create: async (data: any) => {
      const response = await apiClient.post(`/${resource}/`, data);
      return response.data;
    },

    update: async (id: number, data: any) => {
      const response = await apiClient.patch(`/${resource}/${id}/`, data);
      return response.data;
    },

    delete: async (id: number) => {
      const response = await apiClient.delete(`/${resource}/${id}/`);
      return response.data;
    },
  };
}

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
      // Store access token in memory
      if (response.data.access) {
        accessToken = response.data.access;
      }
      return response.data;
    },

    register: async (userData: any) => {
      const response = await apiClient.post('/auth/register/', userData);
      // Store access token in memory
      if (response.data.access) {
        accessToken = response.data.access;
      }
      return response.data;
    },

    logout: async () => {
      try {
        const response = await apiClient.post('/auth/logout/', {});
        return response.data;
      } finally {
        clearTokens();
      }
    },

    refreshToken: async () => {
      const response = await apiClient.post('/token/refresh/', {});
      if (response.data.access) {
        accessToken = response.data.access;
      }
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
  vendors = createCrudService('devices/vendors');

  /**
   * Device Types endpoints
   */
  deviceTypes = createCrudService('devices/device-types');

  /**
   * Devices endpoints
   */
  devices = {
    // Standard CRUD operations (via factory)
    ...createCrudService('devices/devices'),

    // Custom device-specific endpoints
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
    // Standard CRUD operations (via factory)
    ...createCrudService('backups/schedules'),

    // Custom schedule-specific endpoints
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
    // Standard CRUD operations (via factory)
    ...createCrudService('backups/retention-policies'),

    // Custom retention policy-specific endpoint
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
