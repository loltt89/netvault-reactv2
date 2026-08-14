import { describe, it, expect } from 'vitest';
import { getDateRange } from './dateRange';

// Pinned reference "now": Wednesday, 2026-08-19 15:30:00 local time.
const NOW = new Date(2026, 7, 19, 15, 30, 0);

function localMidnight(year: number, month: number, day: number): string {
  return new Date(year, month, day).toISOString();
}

describe('getDateRange', () => {
  it('all: returns no bounds', () => {
    expect(getDateRange('all', NOW)).toEqual({});
  });

  it('today: date_from is today at local midnight, no date_to', () => {
    const result = getDateRange('today', NOW);
    expect(result.date_from).toBe(localMidnight(2026, 7, 19));
    expect(result.date_to).toBeUndefined();
  });

  it('yesterday: covers [yesterday 00:00, today 00:00) — not the day before', () => {
    // Regression test for the fix: this used to compute
    // [day-before-yesterday, yesterday) instead.
    const result = getDateRange('yesterday', NOW);
    expect(result.date_from).toBe(localMidnight(2026, 7, 18));
    // date_to is inclusive on the backend (created_at__lte), so the upper
    // bound is one millisecond before today's midnight, not today's
    // midnight itself and not the day-before-yesterday.
    expect(result.date_to).toBe(new Date(new Date(2026, 7, 19).getTime() - 1).toISOString());
    expect(result.date_to).not.toBe(localMidnight(2026, 7, 18));
  });

  it('last7days: date_from is 7 days before today', () => {
    const result = getDateRange('last7days', NOW);
    expect(result.date_from).toBe(localMidnight(2026, 7, 12));
    expect(result.date_to).toBeUndefined();
  });

  it('last30days: date_from is 30 days before today', () => {
    const result = getDateRange('last30days', NOW);
    expect(result.date_from).toBe(localMidnight(2026, 6, 20));
    expect(result.date_to).toBeUndefined();
  });

  it('custom: uses the provided dateFrom/dateTo', () => {
    const result = getDateRange('custom', NOW, { dateFrom: '2026-08-01', dateTo: '2026-08-10' });
    expect(result.date_from).toBe(new Date('2026-08-01').toISOString());
    expect(result.date_to).toBe(new Date('2026-08-10').toISOString());
  });

  it('custom: omits bounds that were not provided', () => {
    expect(getDateRange('custom', NOW, {})).toEqual({ date_from: undefined, date_to: undefined });
  });

  it('yesterday range crosses a month boundary correctly', () => {
    const firstOfMonth = new Date(2026, 8, 1, 9, 0, 0); // 2026-09-01
    const result = getDateRange('yesterday', firstOfMonth);
    expect(result.date_from).toBe(localMidnight(2026, 7, 31));
  });
});
