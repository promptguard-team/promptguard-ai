import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { effectScope, nextTick, ref, type EffectScope } from 'vue';
import { flushPromises } from '@vue/test-utils';
import { getStats, getTimeseries, listEvents, type AuditStats } from '@/api/audit';
import { ApiError } from '@/api/client';
import type { RangePreset } from '@/time/ranges';
import { RECENT_LIMIT, useDashboard } from './useDashboard';

vi.mock('@/api/audit', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/audit')>();
  return { ...actual, getStats: vi.fn(), getTimeseries: vi.fn(), listEvents: vi.fn() };
});

const stats: AuditStats = {
  total: 8,
  by_action: { allowed: 5, blocked_prompt: 2, blocked_response: 0, provider_error: 1 },
  flagged: 1,
  ml_unavailable: 2,
};

describe('useDashboard', () => {
  let scope: EffectScope;

  beforeEach(() => {
    scope = effectScope();
    vi.mocked(getStats).mockReset().mockResolvedValue(stats);
    vi.mocked(getTimeseries).mockReset().mockResolvedValue({ bucket: 'day', points: [] });
    vi.mocked(listEvents)
      .mockReset()
      .mockResolvedValue({ items: [], total: 0, limit: RECENT_LIMIT, offset: 0 });
  });

  afterEach(() => {
    scope.stop();
    vi.useRealTimers();
  });

  it('loads stats, the trend and recent blocks for the preset', async () => {
    const preset = ref<RangePreset>('7d');
    const dashboard = scope.run(() => useDashboard(preset))!;
    await flushPromises();

    expect(dashboard.stats.data).toEqual(stats);
    expect(getTimeseries).toHaveBeenCalledWith(
      expect.objectContaining({ bucket: 'day' }),
      'day',
      expect.any(AbortSignal),
    );
    expect(listEvents).toHaveBeenCalledWith(
      expect.objectContaining({
        actions: ['blocked_prompt', 'blocked_response'],
        limit: RECENT_LIMIT,
        offset: 0,
      }),
      expect.any(AbortSignal),
    );
  });

  it('reloads with hourly buckets when the preset changes', async () => {
    const preset = ref<RangePreset>('7d');
    scope.run(() => useDashboard(preset));
    await flushPromises();

    preset.value = '24h';
    await nextTick();
    await flushPromises();

    expect(vi.mocked(getTimeseries).mock.lastCall?.[1]).toBe('hour');
  });

  it('keeps one card working when another fails', async () => {
    vi.mocked(getStats).mockRejectedValue(new ApiError('http', 500));
    const dashboard = scope.run(() => useDashboard(ref<RangePreset>('7d')))!;
    await flushPromises();

    expect(dashboard.stats.error?.kind).toBe('http');
    expect(dashboard.trend.data).toEqual({ bucket: 'day', points: [] });
  });

  it('recomputes now on refresh and reloads all three cards', async () => {
    vi.useFakeTimers({ toFake: ['Date'] });
    const t1 = new Date('2026-11-20T10:00:00Z');
    const t2 = new Date('2026-11-20T10:05:00Z');
    vi.setSystemTime(t1);
    const dashboard = scope.run(() => useDashboard(ref<RangePreset>('7d')))!;
    await flushPromises();

    vi.setSystemTime(t2);
    dashboard.refresh();
    await flushPromises();

    expect(getStats).toHaveBeenCalledTimes(2);
    expect(getTimeseries).toHaveBeenCalledTimes(2);
    expect(listEvents).toHaveBeenCalledTimes(2);
    expect(vi.mocked(getStats).mock.lastCall?.[0].to).toEqual(t2);
  });
});
