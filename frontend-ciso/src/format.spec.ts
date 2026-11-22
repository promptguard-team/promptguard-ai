import { describe, expect, it } from 'vitest';
import { EMPTY_VALUE, formatCount, formatScore, formatShare, orEmpty } from './format';

describe('format', () => {
  it('formats counts with Polish grouping', () => {
    expect(formatCount(5)).toBe('5');
    expect(formatCount(12345)).toMatch(/^12\s345$/);
  });

  it('formats a share of the total, or null without a total', () => {
    expect(formatShare(1, 8)).toMatch(/^12,5\s?%$/);
    expect(formatShare(2, 8)).toMatch(/^25\s?%$/);
    expect(formatShare(0, 0)).toBeNull();
  });

  it('formats ML scores to two decimals', () => {
    expect(formatScore(0.9731)).toBe('0.97');
    expect(formatScore(null)).toBe(EMPTY_VALUE);
  });

  it('replaces missing text with a dash', () => {
    expect(orEmpty(null)).toBe('—');
    expect(orEmpty('rule-1')).toBe('rule-1');
  });
});
