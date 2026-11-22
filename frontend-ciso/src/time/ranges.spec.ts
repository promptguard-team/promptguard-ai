import { describe, expect, it } from 'vitest';
import {
  dayRange,
  formatBucketLabel,
  formatDateTime,
  isRangePreset,
  presetRange,
  startOfWarsawDay,
  warsawDay,
  warsawMidnight,
} from './ranges';

const iso = (d: Date): string => d.toISOString();

describe('time/ranges', () => {
  it.each([
    [2026, 10, 25, '2026-10-24T22:00:00.000Z'], // DST end day starts in summer time
    [2026, 10, 26, '2026-10-25T23:00:00.000Z'],
    [2026, 3, 29, '2026-03-28T23:00:00.000Z'], // DST start day starts in winter time
    [2026, 3, 30, '2026-03-29T22:00:00.000Z'],
  ])('warsawMidnight(%i-%i-%i) is %s', (y, m, d, expected) => {
    expect(iso(warsawMidnight(y, m, d))).toBe(expected);
  });

  it('finds the Warsaw day containing an instant', () => {
    // 23:30 UTC on Nov 20 is 00:30 on Nov 21 in Warsaw.
    const late = new Date('2026-11-20T23:30:00Z');
    expect(iso(startOfWarsawDay(late))).toBe('2026-11-20T23:00:00.000Z');
    expect(iso(startOfWarsawDay(late, 1))).toBe('2026-11-19T23:00:00.000Z');
    expect(warsawDay(late)).toBe('2026-11-21');
  });

  it('builds presets ending now', () => {
    const now = new Date('2026-11-20T10:00:00Z');

    expect(presetRange('24h', now)).toEqual({
      from: new Date('2026-11-19T10:00:00Z'),
      to: now,
      bucket: 'hour',
    });
    // Seven Warsaw days: Nov 14 00:00 local through now.
    expect(presetRange('7d', now)).toEqual({
      from: new Date('2026-11-13T23:00:00Z'),
      to: now,
      bucket: 'day',
    });
    expect(iso(presetRange('30d', now).from)).toBe('2026-10-21T22:00:00.000Z');
  });

  it('recognises presets', () => {
    expect(isRangePreset('7d')).toBe(true);
    expect(isRangePreset('1y')).toBe(false);
    expect(isRangePreset(undefined)).toBe(false);
  });

  it('turns inclusive local days into a half-open window', () => {
    expect(dayRange('2026-11-01', '2026-11-03')).toEqual({
      from: new Date('2026-10-31T23:00:00Z'),
      to: new Date('2026-11-03T23:00:00Z'),
    });
    expect(dayRange('2026-11-03', '2026-11-03')).not.toBeNull();
  });

  it.each([
    ['2026-11-04', '2026-11-03'],
    ['2026-02-30', '2026-03-01'],
    ['20261101', '2026-11-03'],
    ['', ''],
  ])('rejects the day range %s..%s', (from, to) => {
    expect(dayRange(from, to)).toBeNull();
  });

  it('formats in Warsaw time', () => {
    expect(formatDateTime('2026-11-20T10:00:00Z')).toMatch(/^20\.11\.2026,? 11:00:00$/);
    expect(formatBucketLabel('2026-11-20T10:00:00Z', 'hour')).toBe('11:00');
    expect(formatBucketLabel('2026-11-20T00:00:00+01:00', 'day')).toBe('20.11');
  });
});
