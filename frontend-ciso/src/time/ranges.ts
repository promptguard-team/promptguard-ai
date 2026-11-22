import { EMPTY_VALUE } from '@/format';
import type { Bucket, TimeRange } from '@/api/audit';

/** The gateway buckets days in this zone; the UI formats every timestamp in it too. */
export const DASHBOARD_TIME_ZONE = 'Europe/Warsaw';

export const RANGE_PRESETS = ['24h', '7d', '30d'] as const;
export type RangePreset = (typeof RANGE_PRESETS)[number];
export const DEFAULT_PRESET: RangePreset = '7d';

export interface PresetRange extends TimeRange {
  bucket: Bucket;
}

export function isRangePreset(value: unknown): value is RangePreset {
  return typeof value === 'string' && (RANGE_PRESETS as readonly string[]).includes(value);
}

interface WallClock {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
  second: number;
}

const partsFormatter = new Intl.DateTimeFormat('en-US', {
  timeZone: DASHBOARD_TIME_ZONE,
  year: 'numeric',
  month: 'numeric',
  day: 'numeric',
  hour: 'numeric',
  minute: 'numeric',
  second: 'numeric',
  hourCycle: 'h23',
});

function wallClock(date: Date): WallClock {
  const parts: Record<string, number> = {};
  for (const part of partsFormatter.formatToParts(date)) {
    if (part.type !== 'literal') {
      parts[part.type] = Number(part.value);
    }
  }
  return {
    year: parts.year ?? 0,
    month: parts.month ?? 1,
    day: parts.day ?? 1,
    hour: parts.hour ?? 0,
    minute: parts.minute ?? 0,
    second: parts.second ?? 0,
  };
}

/** Warsaw's UTC offset at `date`, in milliseconds. */
function offsetMs(date: Date): number {
  const w = wallClock(date);
  const asUtc = Date.UTC(w.year, w.month - 1, w.day, w.hour, w.minute, w.second);
  return asUtc - Math.floor(date.getTime() / 1000) * 1000;
}

/** The instant Warsaw's calendar day starts. `month` is 1-based; `day` may overflow. */
export function warsawMidnight(year: number, month: number, day: number): Date {
  const guess = Date.UTC(year, month - 1, day);
  const first = guess - offsetMs(new Date(guess));
  // The offset at the guess can differ from the offset at the result near a DST change.
  return new Date(guess - offsetMs(new Date(first)));
}

/** Start of the Warsaw day containing `date`, moved `daysBack` days earlier. */
export function startOfWarsawDay(date: Date, daysBack = 0): Date {
  const w = wallClock(date);
  return warsawMidnight(w.year, w.month, w.day - daysBack);
}

const pad = (n: number): string => String(n).padStart(2, '0');

/** The Warsaw calendar date of `date` as YYYY-MM-DD (the format of `<input type="date">`). */
export function warsawDay(date: Date): string {
  const w = wallClock(date);
  return `${w.year}-${pad(w.month)}-${pad(w.day)}`;
}

const HOUR_MS = 60 * 60 * 1000;

function floorToHour(date: Date): number {
  return Math.floor(date.getTime() / HOUR_MS) * HOUR_MS;
}

export function presetRange(preset: RangePreset, now: Date = new Date()): PresetRange {
  switch (preset) {
    case '24h':
      // Start of the current hour minus 23h: 23 full buckets plus the current partial one,
      // never a partial first bucket (UTC and Warsaw hours coincide).
      return { from: new Date(floorToHour(now) - 23 * HOUR_MS), to: now, bucket: 'hour' };
    case '7d':
      return { from: startOfWarsawDay(now, 6), to: now, bucket: 'day' };
    case '30d':
      return { from: startOfWarsawDay(now, 29), to: now, bucket: 'day' };
  }
}

const DAY_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;

function parseDay(value: string): [number, number, number] | null {
  const match = DAY_PATTERN.exec(value);
  if (!match) {
    return null;
  }
  const [year, month, day] = [Number(match[1]), Number(match[2]), Number(match[3])];
  const check = new Date(Date.UTC(year, month - 1, day));
  const valid =
    check.getUTCFullYear() === year &&
    check.getUTCMonth() === month - 1 &&
    check.getUTCDate() === day;
  return valid ? [year, month, day] : null;
}

/** Inclusive Warsaw days (YYYY-MM-DD) to a half-open window; null when invalid or reversed. */
export function dayRange(fromDay: string, toDay: string): TimeRange | null {
  const start = parseDay(fromDay);
  const end = parseDay(toDay);
  if (!start || !end) {
    return null;
  }
  const from = warsawMidnight(...start);
  const to = warsawMidnight(end[0], end[1], end[2] + 1);
  return from < to ? { from, to } : null;
}

const dateTimeFormatter = new Intl.DateTimeFormat('pl-PL', {
  timeZone: DASHBOARD_TIME_ZONE,
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hourCycle: 'h23',
});

export function formatDateTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? EMPTY_VALUE : dateTimeFormatter.format(date);
}

export function formatBucketLabel(value: string, bucket: Bucket): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return EMPTY_VALUE;
  }
  const w = wallClock(date);
  return bucket === 'hour' ? `${pad(w.hour)}:00` : `${pad(w.day)}.${pad(w.month)}`;
}
