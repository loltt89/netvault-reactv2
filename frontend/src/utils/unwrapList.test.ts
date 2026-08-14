import { describe, it, expect } from 'vitest';
import { unwrapList } from './unwrapList';

describe('unwrapList', () => {
  it('returns a plain array unchanged', () => {
    expect(unwrapList([1, 2, 3])).toEqual([1, 2, 3]);
  });

  it('returns an empty array unchanged', () => {
    expect(unwrapList([])).toEqual([]);
  });

  it('unwraps a DRF-style paginated response', () => {
    const response = { count: 2, next: null, previous: null, results: ['a', 'b'] };
    expect(unwrapList(response)).toEqual(['a', 'b']);
  });

  it('returns an empty array when results is missing', () => {
    // @ts-expect-error — deliberately malformed to exercise the fallback
    expect(unwrapList({ count: 0 })).toEqual([]);
  });

  it('returns an empty array for null/undefined', () => {
    expect(unwrapList(null)).toEqual([]);
    expect(unwrapList(undefined)).toEqual([]);
  });
});
