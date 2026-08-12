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
  page_size: number;
}

export type UserRole = 'administrator' | 'operator' | 'viewer' | 'auditor';

export type Language = 'en' | 'ru' | 'kk';

// Keep in sync with the theme classes defined in styles/themes.css —
// this is the single source of truth for theme names, shared by the
// User model's `theme` field and ThemeContext's runtime theme state
// (previously two separate, incompatible enums bridged by an unsafe cast).
export type Theme = 'industrial' | 'neumorphism' | 'isometric' | 'glassmorphism' | 'blueprint';

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
//
// The backend has two genuinely different device shapes, not one — matches
// backend/devices/serializers.py::DeviceSerializer (list) vs
// ::DeviceDetailSerializer (detail), which nest vendor/device_type
// differently on purpose. Modeled as two types rather than one loose union,
// so each page gets the shape it actually receives instead of `as any`.

// List view — backend/devices/serializers.py::DeviceSerializer
export interface Device {
  id: number;
  name: string;
  ip_address: string;
  description: string;
  vendor: number;
  vendor_name: string;
  device_type: number;
  device_type_name: string;
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

// Detail view — backend/devices/serializers.py::DeviceDetailSerializer
// (nested vendor/device_type objects instead of id + *_name pair, plus
// custom_commands/backup_count/created_by_email which the list view omits)
export interface DeviceDetail {
  id: number;
  name: string;
  ip_address: string;
  description: string;
  vendor: Vendor;
  device_type: DeviceType;
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
  backup_count: number;
  backup_enabled: boolean;
  backup_schedule: string;
  custom_commands: string[];
  ssh_host_key_type: string;
  ssh_host_key_fingerprint: string;
  ssh_host_key_verified_at: string | null;
  ssh_host_key_pending_type: string;
  ssh_host_key_pending_fingerprint: string;
  ssh_host_key_pending_detected_at: string | null;
  has_pending_ssh_host_key: boolean;
  created_at: string;
  updated_at: string;
  created_by_email: string | null;
}

// The nested device reference backend/backups/serializers.py::BackupSerializer
// embeds via get_device() — deliberately not the same as Device/DeviceDetail
// above, it's its own smaller shape.
export interface BackupDeviceRef {
  id: number;
  name: string;
  ip_address: string;
  vendor: { id: number; name: string; slug: string } | null;
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

// Backup Types — matches backend/backups/serializers.py::BackupSerializer.
// `device` is a nested BackupDeviceRef (a SerializerMethodField on the
// backend), not a flat id — and there's no `output_log`/`triggered_by` in
// the list serializer's fields, only `triggered_by_email`.
export interface Backup {
  id: number;
  device: BackupDeviceRef | null;
  status: BackupStatus;
  size_bytes: number;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  success: boolean;
  error_message: string;
  backup_type: BackupType;
  triggered_by_email: string | null;
  created_at: string;
  has_changes: boolean;
  changes_summary: string;
}

export type BackupStatus = 'pending' | 'running' | 'success' | 'failed' | 'partial';

export type BackupType = 'manual' | 'scheduled' | 'automatic';

// Single-backup fetch — backend/backups/serializers.py::BackupDetailSerializer.
// Note `device` here is the *list-view* Device shape (nested DeviceSerializer),
// not BackupDeviceRef — the backend genuinely uses a bigger nested object on
// this endpoint than it does in the backup list.
export interface BackupDetail {
  id: number;
  device: Device | null;
  status: BackupStatus;
  backup_type: BackupType;
  size_bytes: number;
  configuration_hash: string;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  success: boolean;
  error_message: string;
  output_log: string;
  has_changes: boolean;
  changes_summary: string;
  triggered_by_email: string | null;
  created_at: string;
  configuration: string | null;
}

export type ScheduleFrequency = 'hourly' | 'daily' | 'weekly' | 'monthly';

// Matches backend/backups/serializers.py::BackupScheduleSerializer exactly.
// (Previously this described a `device: number` + `schedule_expression: string`
// shape that never existed on the backend — the actual model has always used
// frequency/run_time/run_days against a devices M2M. That shape had drifted
// into a locally-redeclared type in BackupSchedules.tsx instead; reconciled
// here so there's one definition again.)
export interface BackupSchedule {
  id: number;
  name: string;
  description: string;
  frequency: ScheduleFrequency;
  run_time: string | null;
  run_days: string;
  devices: number[];
  devices_count: number;
  is_active: boolean;
  last_run: string | null;
  next_run: string | null;
  total_runs: number;
  successful_runs: number;
  failed_runs: number;
  created_at: string;
  updated_at: string;
  created_by_email: string | null;
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

// Dashboard Types — matches backend/core/dashboard_views.py::dashboard_statistics
// exactly (field names are active_devices/inactive_devices, not
// online_devices/offline_devices, and there is no total_storage field).
export interface DashboardStats {
  total_devices: number;
  active_devices: number;
  inactive_devices: number;
  total_backups: number;
  successful_backups: number;
  failed_backups: number;
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
