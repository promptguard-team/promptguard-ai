import { beforeEach, describe, expect, it, vi } from 'vitest';
import { effectScope, nextTick, ref } from 'vue';
import { flushPromises } from '@vue/test-utils';
import { listEvents } from '@/api/audit';
import { defaultEventFilters, type EventFilters } from './eventQuery';
import { useEvents } from './useEvents';

vi.mock('@/api/audit', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/audit')>();
  return { ...actual, listEvents: vi.fn() };
});

describe('useEvents', () => {
  beforeEach(() => {
    vi.mocked(listEvents)
      .mockReset()
      .mockResolvedValue({ items: [], total: 0, limit: 25, offset: 0 });
  });

  it('loads immediately and again whenever the filters change', async () => {
    const filters = ref<EventFilters>(defaultEventFilters());
    const events = effectScope().run(() => useEvents(filters))!;
    await flushPromises();
    expect(events.data).toEqual({ items: [], total: 0, limit: 25, offset: 0 });

    filters.value = { ...filters.value, page: 2 };
    await nextTick();
    await flushPromises();

    expect(listEvents).toHaveBeenCalledTimes(2);
    expect(vi.mocked(listEvents).mock.lastCall?.[0]).toMatchObject({ offset: 25 });
  });
});
