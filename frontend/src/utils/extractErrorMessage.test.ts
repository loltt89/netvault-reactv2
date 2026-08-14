import { describe, it, expect } from 'vitest';
import { extractErrorMessage } from './extractErrorMessage';

function axiosError(data: unknown) {
  return { response: { data } };
}

describe('extractErrorMessage', () => {
  it('returns the fallback when error has no response data', () => {
    expect(extractErrorMessage(new Error('network fail'), 'fallback')).toBe('fallback');
    expect(extractErrorMessage(undefined, 'fallback')).toBe('fallback');
    expect(extractErrorMessage(axiosError(undefined), 'fallback')).toBe('fallback');
  });

  it('prefers the {detail} shape', () => {
    const err = axiosError({ detail: 'old password is incorrect' });
    expect(extractErrorMessage(err, 'fallback')).toBe('old password is incorrect');
  });

  it('falls back to the first field-keyed validation error (array form)', () => {
    const err = axiosError({ email: ['This field is required.'] });
    expect(extractErrorMessage(err, 'fallback')).toBe('This field is required.');
  });

  it('falls back to the first field-keyed validation error (string form)', () => {
    const err = axiosError({ non_field_errors: 'Passwords do not match' });
    expect(extractErrorMessage(err, 'fallback')).toBe('Passwords do not match');
  });

  it('returns the fallback when data is an object with no usable shape', () => {
    const err = axiosError({ some_field: 42 });
    expect(extractErrorMessage(err, 'fallback')).toBe('fallback');
  });

  it('returns the fallback when data is an empty object', () => {
    expect(extractErrorMessage(axiosError({}), 'fallback')).toBe('fallback');
  });
});
