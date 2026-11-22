import type { LocationQuery, LocationQueryRaw, LocationQueryValue } from 'vue-router';
import {
  isAuditAction,
  isMlStatus,
  type AuditAction,
  type EventListParams,
  type MlStatus,
} from '@/api/audit';
import {
  dayRange,
  DEFAULT_PRESET,
  isRangePreset,
  presetRange,
  type RangePreset,
} from '@/time/ranges';

export const PAGE_SIZES = [25, 50] as const;
export type PageSize = (typeof PAGE_SIZES)[number];
export const DEFAULT_PAGE_SIZE: PageSize = 25;

export type EventRange = RangePreset | 'custom';

/** Event-list state. The URL query is its source of truth (see parse/toEventQuery). */
export interface EventFilters {
  range: EventRange;
  /** Inclusive Warsaw days (YYYY-MM-DD); set only when range is 'custom'. */
  fromDay: string | null;
  toDay: string | null;
  actions: AuditAction[];
  flagged: boolean | null;
  mlStatus: MlStatus | null;
  userId: string | null;
  /** Shown on the user chip; there is no endpoint to look it up from userId. */
  userEmail: string | null;
  page: number;
  pageSize: PageSize;
}

export function defaultEventFilters(): EventFilters {
  return {
    range: DEFAULT_PRESET,
    fromDay: null,
    toDay: null,
    actions: [],
    flagged: null,
    mlStatus: null,
    userId: null,
    userEmail: null,
    page: 1,
    pageSize: DEFAULT_PAGE_SIZE,
  };
}

type RawValue = LocationQueryValue | LocationQueryValue[] | undefined;

function single(value: RawValue): string | null {
  const first = Array.isArray(value) ? value[0] : value;
  return typeof first === 'string' ? first : null;
}

function many(value: RawValue): string[] {
  const values = Array.isArray(value) ? value : [value];
  return values.filter((item): item is string => typeof item === 'string');
}

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Reads filters from the URL; anything invalid falls back to its default. */
export function parseEventQuery(query: LocationQuery): EventFilters {
  const filters = defaultEventFilters();

  const range = single(query.range);
  if (range === 'custom') {
    const fromDay = single(query.from);
    const toDay = single(query.to);
    if (fromDay && toDay && dayRange(fromDay, toDay)) {
      Object.assign(filters, { range: 'custom', fromDay, toDay });
    }
  } else if (isRangePreset(range)) {
    filters.range = range;
  }

  filters.actions = [...new Set(many(query.action).filter(isAuditAction))];

  const flagged = single(query.flagged);
  filters.flagged = flagged === 'true' ? true : flagged === 'false' ? false : null;

  const mlStatus = single(query.ml);
  filters.mlStatus = isMlStatus(mlStatus) ? mlStatus : null;

  const userId = single(query.user);
  if (userId && UUID_PATTERN.test(userId)) {
    filters.userId = userId;
    filters.userEmail = single(query.email);
  }

  const page = Number(single(query.page));
  if (Number.isInteger(page) && page >= 1) {
    filters.page = page;
  }
  if (single(query.size) === '50') {
    filters.pageSize = 50;
  }
  return filters;
}

/** Writes filters to a URL query, leaving defaults out so links stay short. */
export function toEventQuery(filters: EventFilters): LocationQueryRaw {
  const query: LocationQueryRaw = {};
  if (filters.range === 'custom') {
    if (filters.fromDay && filters.toDay) {
      Object.assign(query, { range: 'custom', from: filters.fromDay, to: filters.toDay });
    }
  } else if (filters.range !== DEFAULT_PRESET) {
    query.range = filters.range;
  }
  if (filters.actions.length) {
    query.action = [...filters.actions];
  }
  if (filters.flagged !== null) {
    query.flagged = String(filters.flagged);
  }
  if (filters.mlStatus) {
    query.ml = filters.mlStatus;
  }
  if (filters.userId) {
    query.user = filters.userId;
    if (filters.userEmail) {
      query.email = filters.userEmail;
    }
  }
  if (filters.page > 1) {
    query.page = String(filters.page);
  }
  if (filters.pageSize !== DEFAULT_PAGE_SIZE) {
    query.size = String(filters.pageSize);
  }
  return query;
}

export function eventListParams(filters: EventFilters, now: Date = new Date()): EventListParams {
  const custom =
    filters.range === 'custom' && filters.fromDay && filters.toDay
      ? dayRange(filters.fromDay, filters.toDay)
      : null;
  const preset = filters.range === 'custom' ? DEFAULT_PRESET : filters.range;
  const { from, to } = custom ?? presetRange(preset, now);
  return {
    range: { from, to },
    actions: filters.actions,
    flagged: filters.flagged,
    mlStatus: filters.mlStatus,
    userId: filters.userId,
    limit: filters.pageSize,
    offset: (filters.page - 1) * filters.pageSize,
  };
}
