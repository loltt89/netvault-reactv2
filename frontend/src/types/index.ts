/**
 * TypeScript Type Definitions
 * Ensures type safety across frontend-backend communication
 */

// Shared "which devices" shape — backend/core/device_filters.py.
// {"tags": ["core"], "criticality": ["high", "critical"], ...}: each key's
// value is a single string or a list of acceptable values. Used identically
// by NotificationRule.device_filters, CompliancePolicy.device_filters, and
// User.device_scope — one type, not three copies of `Record<string, any>`.
export type DeviceFilters = Record<string, string | string[]>;

// Vendor.backup_commands / Device.custom_commands — both backend
// JSONFields default to an empty list ([]) but, once configured, hold a
// dict validated by devices/serializers.py::validate_backup_commands
// (backup: string, optional setup/config_start/config_end/skip_patterns/
// logout: string[], enable_mode/exec_mode: boolean, exec_wrapper:
// string) — a genuinely different shape from the empty-list default, not
// modeled as a discriminated union here since nothing in the frontend
// inspects individual keys (only Object.keys/JSON.stringify/JSON.parse
// round-trips in the settings UI) — just "some object", which is still
// meaningfully more accurate than the `string[]` this used to claim.
export type BackupCommandsConfig = Record<string, unknown>;

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
  webauthn_credential_count: number;
  is_ldap_user: boolean;
  is_saml_user: boolean;
  date_joined: string;
  last_login: string | null;
  preferred_language: Language;
  theme: Theme;
  page_size: number;
  device_scope: DeviceFilters;
}

// A registered passkey — backend/accounts/models.py::WebAuthnCredential.
// credential_id/public_key never leave the server (see
// WebAuthnCredentialSerializer), so they're deliberately not here.
export interface WebAuthnCredential {
  id: number;
  name: string;
  transports: string[];
  created_at: string;
  last_used_at: string | null;
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

// The refresh token is deliberately NOT part of this response — it only
// ever lives in the HttpOnly cookie the backend sets alongside it (see
// accounts/views.py's CustomTokenObtainPairView), never in JS-readable
// JSON.
export interface AuthResponse {
  user: User;
  access: string;
}

export interface TokenPair {
  access: string;
  refresh: string;
}

// backend/accounts/views.py::CustomTokenObtainPairView.post — the 400
// response body when a second factor is required but wasn't supplied yet.
// webauthn_options is a JSON *string* (webauthn_service.
// build_authentication_options returns `webauthn.options_to_json(...)`,
// typed `-> str`) — the caller must JSON.parse() it into
// PublicKeyCredentialRequestOptionsJSON before passing it to
// startAuthentication(), which LoginPage.tsx already does.
export interface TwoFactorRequiredResponse {
  two_factor_required: true;
  message: string;
  totp_available: boolean;
  webauthn_options?: string;
}

// backend/accounts/views.py::UserViewSet.webauthn_register_begin.
// Same JSON-string caveat as TwoFactorRequiredResponse.webauthn_options —
// build_registration_options is also typed `-> str`.
export interface WebAuthnRegisterBeginResponse {
  options: string;
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
  custom_commands: BackupCommandsConfig | never[];
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
  backup_commands: BackupCommandsConfig | never[];
  created_at: string;
  updated_at: string;
}

export interface DeviceType {
  id: number;
  name: string;
  slug: string;
  description: string;
  icon: string;
  is_predefined: boolean;
}

// backend/devices/views.py::DeviceViewSet.test_connection
export interface TestConnectionResult {
  success: boolean;
  message: string;
  device_id: number;
  device_name: string;
  status?: DeviceStatus;
  locked?: boolean;
}

// backend/devices/views.py::DeviceViewSet.backup_now
export interface BackupNowResult {
  success: boolean;
  message: string;
  device_id: number;
  task_id: string;
}

// backend/devices/views.py::DeviceViewSet.approve_ssh_host_key
export interface ApproveSshHostKeyResult {
  success: boolean;
  ssh_host_key_type: string;
  ssh_host_key_fingerprint: string;
}

// backend/devices/views.py: bulk_backup_now / bulk_tag_edit / bulk_delete
export interface BulkBackupNowResult {
  success: boolean;
  triggered_count: number;
  triggered: { device_id: number; device_name: string; task_id: string }[];
  not_found_ids: number[];
}

export interface BulkTagEditResult {
  success: boolean;
  updated_count: number;
  updated: { device_id: number; device_name: string; tags: string[] }[];
  not_found_ids: number[];
}

export interface BulkDeleteResult {
  success: boolean;
  deleted_count: number;
  deleted_devices: { id: number; name: string; ip_address: string }[];
  not_found_ids: number[];
}

// backend/devices/views.py::DeviceViewSet.csv_preview
export interface CsvPreviewRow {
  row_number: number;
  data: Record<string, string>;
  errors: string[];
  warnings: string[];
  valid: boolean;
}

export interface CsvPreviewResult {
  total_rows: number;
  valid_rows: number;
  duplicate_rows: number;
  error_rows: number;
  rows: CsvPreviewRow[];
  vendors: string[];
  device_types: string[];
}

// backend/devices/views.py::DeviceViewSet.csv_import
export interface CsvImportResult {
  success: boolean;
  created: number;
  updated: number;
  skipped: number;
  errors: string[];
}

// What create/update actually return — backend/devices/serializers.py::
// DeviceCreateSerializer's fields, a third shape distinct from both Device
// (list) and DeviceDetail (retrieve): vendor/device_type are raw ids (not
// nested objects, not *_name pairs), and there's no status/last_seen/
// last_backup/backup_status/vendor_name/device_type_name at all.
export interface DeviceCreateResponse {
  id: number;
  name: string;
  ip_address: string;
  description: string;
  vendor: number;
  device_type: number;
  protocol: Protocol;
  port: number;
  username: string;
  location: string;
  tags: string[];
  criticality: Criticality;
  backup_enabled: boolean;
  backup_schedule: string;
  custom_commands: BackupCommandsConfig | never[];
  created_at: string;
  updated_at: string;
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

// Matches backend/backups/serializers.py::BackupRetentionPolicySerializer
export interface BackupRetentionPolicy {
  id: number;
  name: string;
  description: string;
  keep_last_n: number;
  keep_daily: number;
  keep_weekly: number;
  keep_monthly: number;
  is_active: boolean;
  auto_delete: boolean;
  devices: number[];
  devices_count: number;
  created_at: string;
  updated_at: string;
}

// backend/backups/tasks.py::apply_retention_policy's result dict, spread
// into BackupRetentionPolicyViewSet.apply_now's response alongside
// success/message/policy_id.
export interface RetentionApplyResult {
  success: boolean;
  message: string;
  policy_id: number;
  devices_processed: number;
  deleted_count: number;
  kept_count: number;
}

// backend/backups/views.py::BackupViewSet.grouped
export interface BackupGroup {
  group: string;
  count: number;
  backups: Backup[];
  total_size: number;
}

export interface BackupGroupedResponse {
  group_by: 'date' | 'vendor' | 'device_type';
  groups: BackupGroup[];
  total_groups: number;
  total_backups: number;
  truncated: boolean;
}

// backend/backups/views.py::BackupViewSet.compare
export interface BackupCompareResult {
  backup1: Backup;
  backup2: Backup;
  diff: string;
}

// backend/backups/views.py::BackupViewSet.search_configs
export interface ConfigSearchMatch {
  line_number: number;
  line: string;
  context: string;
}

export interface ConfigSearchResult {
  device_id: number;
  device_name: string;
  device_ip: string;
  vendor: string | null;
  backup_id: number;
  backup_date: string;
  match_count: number;
  matches: ConfigSearchMatch[];
}

export interface ConfigSearchResponse {
  query: string;
  total_devices: number;
  total_matches: number;
  results: ConfigSearchResult[];
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

// System Settings — matches backend/core/system_settings_views.py's
// hand-built (not DRF-serializer-backed) nested response/update shape.
export interface SystemSettingsResponse {
  email: {
    host: string;
    port: number;
    use_tls: boolean;
    host_user: string;
    from_email: string;
  };
  telegram: {
    enabled: boolean;
    bot_token: string; // '***' if set, server never returns the real value
    chat_id: string;
  };
  notifications: {
    notify_on_success: boolean;
    notify_on_failure: boolean;
    notify_schedule_summary: boolean;
  };
  ldap: {
    enabled: boolean;
    server_uri: string;
    bind_dn: string;
    user_search_base: string;
    user_search_filter: string;
  };
  backup: {
    retention_days: number;
    parallel_workers: number;
  };
  jwt: {
    access_token_lifetime: number;
    refresh_token_lifetime: number;
  };
  redis: {
    url: string;
  };
}

// Update payload — every field optional (only keys present are applied),
// plus the write-only password fields the GET response never includes.
export interface SystemSettingsUpdatePayload {
  email?: Partial<SystemSettingsResponse['email'] & { host_password: string }>;
  telegram?: Partial<SystemSettingsResponse['telegram']>;
  notifications?: Partial<SystemSettingsResponse['notifications']>;
  ldap?: Partial<SystemSettingsResponse['ldap'] & { bind_password: string }>;
  backup?: Partial<SystemSettingsResponse['backup']>;
  jwt?: Partial<SystemSettingsResponse['jwt']>;
}

// backend/accounts/saml_views.py::SAMLSettingsAPIView
export interface SAMLSettingsResponse {
  enabled: boolean;
  sp_entity_id: string;
  sp_acs_url: string;
  sp_sls_url: string;
  sp_metadata_url: string;
  idp_entity_id: string;
  idp_sso_url: string;
  idp_slo_url: string;
  idp_x509_cert: string;
  attr_username: string;
  attr_email: string;
  attr_first_name: string;
  attr_last_name: string;
  auto_create_users: boolean;
  default_role: UserRole;
  want_assertions_signed: boolean;
  want_messages_signed: boolean;
}

// Update payload — server-computed sp_*_url fields are deliberately not
// accepted here (SAMLSettingsAPIView.post only reads the config fields).
export type SAMLSettingsUpdatePayload = Partial<Omit<
  SAMLSettingsResponse, 'sp_acs_url' | 'sp_sls_url' | 'sp_metadata_url'
>>;

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
  device_filters: DeviceFilters;
  created_at: string;
  updated_at: string;
  created_by_email: string | null;
}

export type NotificationTrigger = 'backup_failed' | 'backup_success' | 'device_offline' | 'config_changed' | 'critical_change';

export type NotificationChannel = 'email' | 'telegram' | 'webhook';

export interface Notification {
  id: number;
  rule: number | null;
  rule_name: string | null;
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

// Compliance Types — matches backend/compliance
export type ComplianceRuleType = 'must_contain' | 'must_not_contain';

export interface ComplianceRule {
  type: ComplianceRuleType;
  pattern: string;
  is_regex?: boolean;
  description?: string;
}

export type ComplianceSeverity = 'low' | 'medium' | 'high' | 'critical';

export interface CompliancePolicy {
  id: number;
  name: string;
  description: string;
  is_active: boolean;
  severity: ComplianceSeverity;
  device_filters: DeviceFilters;
  rules: ComplianceRule[];
  created_at: string;
  updated_at: string;
  created_by_email: string | null;
  open_violation_count: number;
}

export type ComplianceViolationStatus = 'open' | 'resolved';

export interface ComplianceViolation {
  id: number;
  policy: number;
  policy_name: string;
  policy_severity: ComplianceSeverity;
  device: number;
  device_name: string;
  device_ip: string;
  backup: number | null;
  rule_description: string;
  status: ComplianceViolationStatus;
  detected_at: string;
  last_seen_at: string;
  resolved_at: string | null;
}

export interface ComplianceStatistics {
  open_total: number;
  by_severity: Record<ComplianceSeverity, number>;
  affected_devices: number;
}

// Stale-backups dashboard widget — matches
// backend/core/dashboard_views.py::stale_backups
export interface StaleDevice {
  id: number;
  name: string;
  ip_address: string;
  vendor: string | null;
  device_type: string | null;
  tags: string[];
  criticality: string;
  last_backup: string | null;
  days_since_backup: number | null;
}

export interface StaleBackupsResponse {
  threshold_days: number;
  count: number;
  devices: StaleDevice[];
}

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
  total: number;
}

// backend/devices/views.py::DeviceViewSet.statistics
export interface DeviceStatistics {
  total: number;
  by_status: Record<string, number>;
  by_criticality: Record<string, number>;
  by_vendor: { vendor__name: string | null; count: number }[];
  backup_enabled: number;
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
  [key: string]: unknown;
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
  // Admin-only (DeviceCreateSerializer silently drops this for anyone
  // else) — see validate_backup_commands in devices/serializers.py for
  // the expected shape.
  custom_commands?: Record<string, unknown>;
}

// Thrown by AuthContext's login() when the backend's 400 response signals
// a second factor is required — a frontend-normalized (camelCase) version
// of TwoFactorRequiredResponse, not the same shape (see AuthContext.tsx's
// login() catch block, which builds this from the raw response).
export interface LoginTwoFactorRequiredError {
  twoFactorRequired: true;
  message: string;
  totpAvailable: boolean;
  webauthnOptions?: string;
}

// Context Types
export interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  // Rejects with LoginTwoFactorRequiredError specifically when a second
  // factor is required and wasn't supplied — callers narrow on
  // `twoFactorRequired` (see LoginPage.tsx) to tell that apart from a
  // genuine failure, which rejects with the underlying AxiosError instead.
  login: (email: string, password: string, twoFactorToken?: string, webauthnResponse?: object) => Promise<AuthResponse>;
  logout: () => Promise<void>;
  register: (data: RegisterData) => Promise<AuthResponse>;
  updateProfile: (data: Partial<User>) => Promise<User>;
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
