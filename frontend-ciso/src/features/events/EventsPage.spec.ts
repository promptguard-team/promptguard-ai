import { beforeEach, describe, expect, it, vi } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';
import { h } from 'vue';
import { QLayout, QPageContainer } from 'quasar';
import { createMemoryHistory, createRouter, RouterView } from 'vue-router';
import { listEvents } from '@/api/audit';
import { ApiError } from '@/api/client';
import { appPlugins } from '@/test/plugins';
import EventFiltersBar from './EventFiltersBar.vue';
import EventsPage from './EventsPage.vue';
import EventsTable from './EventsTable.vue';

vi.mock('@/api/audit', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/audit')>();
  return { ...actual, listEvents: vi.fn() };
});

const UUID = '3f2b8c1e-4d5a-4b6c-8d7e-9f0a1b2c3d4e';

async function mountAt(path: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/events', component: EventsPage }],
  });
  await router.push(path);
  await router.isReady();
  const wrapper = mount(
    { render: () => h(QLayout, null, () => h(QPageContainer, null, () => h(RouterView))) },
    { global: { plugins: [...appPlugins(), router] } },
  );
  await flushPromises();
  return { wrapper, router };
}

describe('EventsPage', () => {
  beforeEach(() => {
    vi.mocked(listEvents)
      .mockReset()
      .mockResolvedValue({ items: [], total: 120, limit: 25, offset: 25 });
  });

  it('loads the page and filters named in the URL', async () => {
    await mountAt('/events?action=blocked_prompt&page=2');

    expect(vi.mocked(listEvents).mock.lastCall?.[0]).toMatchObject({
      actions: ['blocked_prompt'],
      limit: 25,
      offset: 25,
    });
  });

  it('writes filter changes to the URL and returns to page 1', async () => {
    const { wrapper, router } = await mountAt('/events?action=blocked_prompt&page=2');

    wrapper.findComponent(EventFiltersBar).vm.$emit('change', { flagged: true });
    await flushPromises();

    // toEventQuery writes actions as an array; vue-router keeps it as one.
    expect(router.currentRoute.value.query).toEqual({
      action: ['blocked_prompt'],
      flagged: 'true',
    });
    expect(vi.mocked(listEvents).mock.lastCall?.[0]).toMatchObject({ flagged: true, offset: 0 });
  });

  it('paginates through the URL', async () => {
    const { wrapper, router } = await mountAt('/events');

    wrapper.findComponent(EventsTable).vm.$emit('paginate', 3, 25);
    await flushPromises();
    expect(router.currentRoute.value.query.page).toBe('3');

    wrapper.findComponent(EventsTable).vm.$emit('paginate', 3, 50);
    await flushPromises();
    expect(router.currentRoute.value.query).toEqual({ size: '50' });
  });

  it('filters by a clicked user', async () => {
    const { wrapper, router } = await mountAt('/events');

    wrapper.findComponent(EventsTable).vm.$emit('filterUser', UUID, 'jan@example.com');
    await flushPromises();

    expect(router.currentRoute.value.query).toEqual({ user: UUID, email: 'jan@example.com' });
    expect(vi.mocked(listEvents).mock.lastCall?.[0]).toMatchObject({ userId: UUID });
  });

  it('shows a retryable error', async () => {
    vi.mocked(listEvents).mockRejectedValueOnce(new ApiError('network'));
    const { wrapper } = await mountAt('/events');

    await wrapper.get('[data-test="retry"]').trigger('click');
    await flushPromises();

    expect(listEvents).toHaveBeenCalledTimes(2);
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
  });
});
