import { request } from './client';

export const AUDIT_ACTIONS = [
  'allowed',
  'blocked_prompt',
  'blocked_response',
  'provider_error',
] as const;
export type AuditAction = (typeof AUDIT_ACTIONS)[number];
export const BLOCKED_ACTIONS: readonly AuditAction[] = ['blocked_prompt', 'blocked_response'];

export const ML_STATUSES = ['skipped', 'ok', 'unavailable'] as const;
export type MlStatus = (typeof ML_STATUSES)[number];

export type Bucket = 'hour' | 'day';
export type ActionCounts = Record<AuditAction, number>;

export function isAuditAction(value: unknown): value is AuditAction {
  return typeof value === 'string' && (AUDIT_ACTIONS as readonly string[]).includes(value);
}

export function isMlStatus(value: unknown): value is MlStatus {
  return typeof value === 'string' && (ML_STATUSES as readonly string[]).includes(value);
}

/** Event metadata; the list endpoint never returns prompt or response text. */
export interface AuditEventSummary {
  id: string;
  created_at: string;
  user_id: string;
  user_email: string;
  action: AuditAction;
  rule: string | null;
  ml_status: MlStatus;
  ml_score: number | null;
  ml_label: string | null;
  ml_model_version: string | null;
  flagged: boolean;
}

export interface AuditEventPage {
  items: AuditEventSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface AuditStats {
  total: number;
  by_action: ActionCounts;
  flagged: number;
  ml_unavailable: number;
}

export interface TimeseriesPoint {
  start: string;
  by_action: ActionCounts;
}

export interface AuditTimeseries {
  bucket: Bucket;
  points: TimeseriesPoint[];
}

/** A half-open [from, to) window. */
export interface TimeRange {
  from: Date;
  to: Date;
}

export interface EventListParams {
  range: TimeRange;
  actions?: readonly AuditAction[];
  flagged?: boolean | null;
  mlStatus?: MlStatus | null;
  userId?: string | null;
  limit: number;
  offset: number;
}

function rangeQuery(range: TimeRange): { from: string; to: string } {
  return { from: range.from.toISOString(), to: range.to.toISOString() };
}

export function listEvents(params: EventListParams, signal?: AbortSignal): Promise<AuditEventPage> {
  return request<AuditEventPage>('GET', '/audit/events', {
    signal,
    query: {
      ...rangeQuery(params.range),
      action: params.actions?.length ? params.actions : undefined,
      flagged: params.flagged ?? undefined,
      ml_status: params.mlStatus ?? undefined,
      user_id: params.userId ?? undefined,
      limit: params.limit,
      offset: params.offset,
    },
  });
}

export function getStats(range: TimeRange, signal?: AbortSignal): Promise<AuditStats> {
  return request<AuditStats>('GET', '/audit/stats', { signal, query: rangeQuery(range) });
}

export function getTimeseries(
  range: TimeRange,
  bucket: Bucket,
  signal?: AbortSignal,
): Promise<AuditTimeseries> {
  return request<AuditTimeseries>('GET', '/audit/timeseries', {
    signal,
    query: { ...rangeQuery(range), bucket },
  });
}
