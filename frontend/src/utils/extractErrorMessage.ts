/**
 * Pulls a human-readable message out of an Axios error from the backend.
 *
 * The backend has two genuinely different error shapes, both legitimate:
 *  - {"detail": "message"} — from a manually-constructed Response() or a
 *    raised APIException (NotFound, PermissionDenied, ...).
 *  - {"field_name": ["message", ...]} or {"non_field_errors": [...]} — DRF's
 *    standard shape for serializer ValidationError (raise_exception=True).
 *
 * Several call sites were reading a stale `.error` key that no backend
 * response has actually used since the API error envelope was unified —
 * this was silently falling through to a generic fallback message every
 * time, e.g. hiding the real "old password is incorrect" behind a generic
 * "failed to change password". Centralizing the extraction here instead of
 * re-guessing the shape at every call site.
 */
export function extractErrorMessage(error: unknown, fallback: string): string {
  const data = (error as { response?: { data?: Record<string, unknown> } })?.response?.data;
  if (!data || typeof data !== 'object') {
    return fallback;
  }

  if (typeof data.detail === 'string') {
    return data.detail;
  }

  // Field-keyed validation error: grab the first field's first message.
  const firstKey = Object.keys(data)[0];
  if (firstKey) {
    const value = data[firstKey];
    if (Array.isArray(value) && typeof value[0] === 'string') {
      return value[0];
    }
    if (typeof value === 'string') {
      return value;
    }
  }

  return fallback;
}
