/**
 * TypeScript Type Definitions
 * Ensures type safety across frontend-backend communication
 */

// User Types
export interface User {
  id: number;
  email: string;
  username: string;
  first_name: string;
  last_name: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  two_factor_enabled: boolean;
  is_ldap_user: boolean;
  date_joined: string;
  last_login: string | null;
  preferred_language: Language;
  theme: Theme;
}

export type UserRole = 'administrator' | 'operator' | 'viewer' | 'auditor';

export type Language = 'en' | 'ru' | 'kk';

export type Theme = 'light' | 'dark_blue' | 'teal_light' | 'deep_dark';

export interface LoginCredentials {
  email: string;
  password: string;
  two_factor_token?: string;
}

export interface RegisterData {
  email: string;
  username: string;
  password: string;
  password_confirm: string;
  first_name?: string;
  last_name?: string;
  preferred_language?: Language;
  theme?: Theme;
}

export interface AuthResponse {
  user: User;
  access: string;
  refresh: string;
}

export interface TokenPair {
  access: string;
  refresh: string;
}

// Audit Log Types
export interface AuditLog {
  id: number;
  user: number;
  user_email: string;
  action: AuditAction;
  resource_type: string;
  resource_id: number | null;
  resource_name: string;
  description: string;
  ip_address: string | null;
  user_agent: string;
  timestamp: string;
  success: boolean;
  error_message: string;
}

export type AuditAction = 'login' | 'logout' | 'create' | 'update' | 'delete' | 'backup' | 'restore' | 'download' | 'view';

// Device Types
export interface Device {
  id: number;
  name: string;
  ip_address: string;
  description: string;
  vendor: Vendor | number;
  vendor_name?: string;
  device_type: DeviceType | number;
  device_type_name?: string;
  protocol: Protocol;
  port: number;
  username: string;
  location: string;
  tags: string[];
  criticality: Criticality;
  status: DeviceStatus;
  last_seen: string | null;
  last_backup: string | null;
  backup_status: string;
  backup_enabled: boolean;
  backup_schedule: string;
  created_at: string;
  updated_at: string;
}

export interface Vendor {
  id: number;
  name: string;
  slug: string;
  description: string;
  logo_url: string;
  is_predefined: boolean;
  backup_commands: string[];
  created_at: string;
  updated_at: string;
}

export interface DeviceType {
  id: number;
  name: string;
  slug: string;
  description: string;
  icon: string;
}

export type Protocol = 'ssh' | 'telnet';

export type Criticality = 'low' | 'medium' | 'high' | 'critical';

export type DeviceStatus = 'online' | 'offline' | 'unknown';

// Backup Types
export interface Backup {
  id: number;
  device: number;
  device_name?: string;
  status: BackupStatus;
  size_bytes: number;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  success: boolean;
  error_message: string;
  output_log: string;
  backup_type: BackupType;
  triggered_by: number | null;
  created_at: string;
  has_changes: boolean;
  changes_summary: string;
}

export type BackupStatus = 'pending' | 'running' | 'success' | 'failed' | 'partial';

export type BackupType = 'manual' | 'scheduled' | 'automatic';

export interface BackupSchedule {
  id: number;
  device: number;
  name: string;
  description: string;
  schedule_expression: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  last_run: string | null;
  next_run: string | null;
  total_runs: number;
  successful_runs: number;
  failed_runs: number;
}

export interface BackupDiff {
  id: number;
  backup_new: number;
  backup_old: number;
  diff_content: string;
  additions: number;
  deletions: number;
  modifications: number;
  created_at: string;
}

// Notification Types
export interface NotificationRule {
  id: number;
  name: string;
  description: string;
  trigger: NotificationTrigger;
  channel: NotificationChannel;
  is_active: boolean;
  email_recipients: string[];
  telegram_chat_ids: string[];
  webhook_url: string;
  device_filters: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export type NotificationTrigger = 'backup_failed' | 'backup_success' | 'device_offline' | 'config_changed' | 'critical_change';

export type NotificationChannel = 'email' | 'telegram' | 'webhook';

export interface Notification {
  id: number;
  rule: number | null;
  status: NotificationStatus;
  title: string;
  message: string;
  channel: string;
  recipient: string;
  sent_at: string | null;
  error_message: string;
  created_at: string;
}

export type NotificationStatus = 'pending' | 'sent' | 'failed';

// Dashboard Types
export interface DashboardStats {
  total_devices: number;
  online_devices: number;
  offline_devices: number;
  total_backups: number;
  successful_backups: number;
  failed_backups: number;
  total_storage: number;
  last_24h_backups: number;
}

export interface BackupChart {
  date: string;
  successful: number;
  failed: number;
}

// API Response Types
export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface ApiError {
  detail?: string;
  [key: string]: any;
}

// Form Types
export interface ChangePasswordForm {
  old_password: string;
  new_password: string;
  new_password_confirm: string;
}

export interface DeviceForm {
  name: string;
  ip_address: string;
  description: string;
  vendor: number;
  device_type: number;
  protocol: Protocol;
  port: number;
  username: string;
  password: string;
  enable_password?: string;
  location: string;
  tags: string[];
  criticality: Criticality;
  backup_enabled: boolean;
  backup_schedule: string;
}

// Context Types
export interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string, twoFactorToken?: string) => Promise<void>;
  logout: () => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  updateProfile: (data: Partial<User>) => Promise<void>;
  refreshUser: () => Promise<void>;
}

export interface ThemeContextType {
  theme: Theme;
  setTheme: (theme: Theme) => void;
}

export interface LanguageContextType {
  language: Language;
  setLanguage: (language: Language) => void;
  t: (key: string) => string;
}

// Utility Types
export interface SelectOption {
  value: string | number;
  label: string;
}

export interface TableColumn<T> {
  key: keyof T | string;
  label: string;
  sortable?: boolean;
  render?: (item: T) => React.ReactNode;
}

export interface TableProps<T> {
  data: T[];
  columns: TableColumn<T>[];
  loading?: boolean;
  onRowClick?: (item: T) => void;
  pagination?: {
    page: number;
    pageSize: number;
    total: number;
    onChange: (page: number, pageSize: number) => void;
  };
}
