import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { effectScope, nextTick, ref, type EffectScope } from 'vue';
import { flushPromises } from '@vue/test-utils';
import { listEvents } from '@/api/audit';
import { defaultEventFilters, type EventFilters } from './eventQuery';
import { useEvents } from './useEvents';

vi.mock('@/api/audit', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/audit')>();
  return { ...actual, listEvents: vi.fn() };
});

const UUID = '3f2b8c1e-4d5a-4b6c-8d7e-9f0a1b2c3d4e';

describe('useEvents', () => {
  let scope: EffectScope;

  beforeEach(() => {
    scope = effectScope();
    vi.mocked(listEvents)
      .mockReset()
      .mockResolvedValue({ items: [], total: 0, limit: 25, offset: 0 });
  });

  afterEach(() => scope.stop());

  it('loads immediately and again whenever the filters change', async () => {
    const filters = ref<EventFilters>(defaultEventFilters());
    const events = scope.run(() => useEvents(filters))!;
    await flushPromises();
    expect(events.data).toEqual({ items: [], total: 0, limit: 25, offset: 0 });

    filters.value = { ...filters.value, page: 2 };
    await nextTick();
    await flushPromises();

    expect(listEvents).toHaveBeenCalledTimes(2);
    expect(vi.mocked(listEvents).mock.lastCall?.[0]).toMatchObject({ offset: 25 });
  });

  it('does not reload for equal filters or an email-only change', async () => {
    const filters = ref<EventFilters>({
      ...defaultEventFilters(),
      userId: UUID,
      userEmail: 'a@x.pl',
    });
    scope.run(() => useEvents(filters));
    await flushPromises();

    filters.value = { ...filters.value };
    await nextTick();
    filters.value = { ...filters.value, userEmail: 'b@x.pl' };
    await nextTick();
    await flushPromises();

    expect(listEvents).toHaveBeenCalledTimes(1);
  });
});
