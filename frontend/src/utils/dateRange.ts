export type DateFilterType = 'all' | 'today' | 'yesterday' | 'last7days' | 'last30days' | 'custom';

export interface DateRangeResult {
  date_from?: string;
  date_to?: string;
}

/**
 * Computes the {date_from, date_to} query params for a backup-list date
 * filter. Pulled out of BackupsPage.tsx so this logic — including a fixed
 * "yesterday" off-by-one (it used to compute [day-before-yesterday,
 * yesterday) instead of [yesterday, today)) — is unit-testable
 * independent of rendering the page.
 *
 * `now` defaults to the real current time but can be pinned by callers
 * (tests) instead of depending on wall-clock time at call time.
 *
 * date_to is inclusive on the backend (`created_at__lte=date_to`), so
 * every upper bound here is the last millisecond of its day, not the
 * next day's midnight.
 */
export function getDateRange(
  filter: DateFilterType,
  now: Date = new Date(),
  custom: { dateFrom?: string; dateTo?: string } = {}
): DateRangeResult {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());

  switch (filter) {
    case 'today':
      return { date_from: today.toISOString() };
    case 'yesterday': {
      const yesterday = new Date(today);
      yesterday.setDate(yesterday.getDate() - 1);
      return {
        date_from: yesterday.toISOString(),
        date_to: new Date(today.getTime() - 1).toISOString(),
      };
    }
    case 'last7days': {
      const last7 = new Date(today);
      last7.setDate(last7.getDate() - 7);
      return { date_from: last7.toISOString() };
    }
    case 'last30days': {
      const last30 = new Date(today);
      last30.setDate(last30.getDate() - 30);
      return { date_from: last30.toISOString() };
    }
    case 'custom':
      return {
        date_from: custom.dateFrom ? new Date(custom.dateFrom).toISOString() : undefined,
        date_to: custom.dateTo ? new Date(custom.dateTo).toISOString() : undefined,
      };
    default:
      return {};
  }
}
