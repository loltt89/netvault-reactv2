import { PaginatedResponse } from '../types';

/**
 * Every list endpoint in this app can come back either as a plain array or
 * as a DRF-style PaginatedResponse, and callers need to unwrap either shape
 * before rendering. This exact `Array.isArray(x) ? x : x.results || []`
 * check was copy-pasted independently into ~12 call sites (AuditLogsPage,
 * UsersPage, DevicesListPage x2, DeviceDetailPage x2, BackupSchedules,
 * BackupRetentionPolicies x2, SystemSettings x2, TasksTable) — pulled out
 * once here instead.
 */
export function unwrapList<T>(response: T[] | PaginatedResponse<T> | null | undefined): T[] {
  if (Array.isArray(response)) {
    return response;
  }
  return response?.results ?? [];
}
