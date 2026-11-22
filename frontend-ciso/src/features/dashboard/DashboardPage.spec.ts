import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';
import { h } from 'vue';
import { QLayout, QPageContainer } from 'quasar';
import { createMemoryHistory, createRouter, RouterView } from 'vue-router';
import { getStats, getTimeseries, listEvents, type AuditStats } from '@/api/audit';
import { ApiError } from '@/api/client';
import RangeSelect from '@/components/RangeSelect.vue';
import { appPlugins } from '@/test/plugins';
import DashboardPage from './DashboardPage.vue';

vi.mock('@/api/audit', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/audit')>();
  return { ...actual, getStats: vi.fn(), getTimeseries: vi.fn(), listEvents: vi.fn() };
});

vi.mock('vue-chartjs', async () => {
  const { defineComponent, h } = await import('vue');
  const marker = (name: string) =>
    defineComponent({
      props: ['data', 'options'],
      setup: () => () => h('div', { 'data-test': name }),
    });
  return { Bar: marker('bar-chart'), Doughnut: marker('doughnut-chart') };
});

const stats: AuditStats = {
  total: 8,
  by_action: { allowed: 5, blocked_prompt: 2, blocked_response: 0, provider_error: 1 },
  flagged: 1,
  ml_unavailable: 2,
};

async function mountAt(path: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: DashboardPage },
      { path: '/events', component: { render: () => h('div') } },
    ],
  });
  await router.push(path);
  await router.isReady();
  const wrapper = mount(
    { render: () => h(QLayout, null, () => h(QPageContainer, null, () => h(RouterView))) },
    {
      global: { plugins: [...appPlugins(), router] },
    },
  );
  await flushPromises();
  return { wrapper, router };
}

describe('DashboardPage', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  beforeEach(() => {
    vi.mocked(getStats).mockReset().mockResolvedValue(stats);
    vi.mocked(getTimeseries).mockReset().mockResolvedValue({ bucket: 'hour', points: [] });
    vi.mocked(listEvents)
      .mockReset()
      .mockResolvedValue({ items: [], total: 0, limit: 5, offset: 0 });
  });

  it('reads the range from the URL and shows the KPIs', async () => {
    const { wrapper } = await mountAt('/?range=24h');

    expect(vi.mocked(getTimeseries).mock.lastCall?.[1]).toBe('hour');
    const values = wrapper.findAll('[data-test="kpi-value"]').map((w) => w.text());
    expect(values).toEqual(['8', '2', '1', '2']);
    expect(wrapper.findAll('[data-test="kpi-share"]')[0]!.text()).toMatch(/^25\s?% wszystkich$/);
    expect(wrapper.find('[data-test="bar-chart"]').exists()).toBe(true);
  });

  it('writes a new range to the URL and reloads', async () => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date('2026-11-20T10:00:00Z'));
    const { wrapper, router } = await mountAt('/');

    wrapper.findComponent(RangeSelect).vm.$emit('update:modelValue', '30d');
    await flushPromises();

    expect(router.currentRoute.value.query.range).toBe('30d');
    expect(getStats).toHaveBeenCalledTimes(2);
    expect(getTimeseries).toHaveBeenCalledTimes(2);
    expect(vi.mocked(getStats).mock.lastCall?.[0].from.toISOString()).toBe(
      '2026-10-21T22:00:00.000Z',
    );
  });

  it('shows a retryable error for a failed card only', async () => {
    vi.mocked(getStats).mockRejectedValueOnce(new ApiError('http', 500));
    const { wrapper } = await mountAt('/');

    // The stats banner and the donut card's banner; the trend card is unaffected.
    expect(wrapper.findAll('[role="alert"]')).toHaveLength(2);
    expect(wrapper.find('[data-test="bar-chart"]').exists()).toBe(true);

    await wrapper.get('[data-test="retry"]').trigger('click');
    await flushPromises();

    expect(getStats).toHaveBeenCalledTimes(2);
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
  });

  it('links to the event list filtered to blocks in the same range', async () => {
    const { wrapper } = await mountAt('/?range=24h');

    const href = wrapper.get('[data-test="see-all"]').attributes('href');
    expect(href).toContain('/events?');
    expect(href).toContain('range=24h');
    expect(href).toContain('action=blocked_prompt&action=blocked_response');
  });

  it('refreshes on demand', async () => {
    const { wrapper } = await mountAt('/');

    await wrapper.get('[data-test="refresh"]').trigger('click');
    await flushPromises();

    expect(getStats).toHaveBeenCalledTimes(2);
    expect(getTimeseries).toHaveBeenCalledTimes(2);
    expect(listEvents).toHaveBeenCalledTimes(2);
  });

  it('hides stale numbers and shows a donut error when stats fail', async () => {
    const { wrapper } = await mountAt('/');
    vi.mocked(getStats).mockRejectedValueOnce(new ApiError('http', 500));

    await wrapper.get('[data-test="refresh"]').trigger('click');
    await flushPromises();

    const values = wrapper.findAll('[data-test="kpi-value"]').map((w) => w.text());
    expect(values).toEqual(['—', '—', '—', '—']);
    // One banner above the KPIs and one inside the donut card.
    expect(wrapper.findAll('[role="alert"]')).toHaveLength(2);
    expect(wrapper.find('[data-test="doughnut-chart"]').exists()).toBe(false);
  });

  it('shows an empty share when there were no requests', async () => {
    vi.mocked(getStats).mockResolvedValue({
      total: 0,
      by_action: { allowed: 0, blocked_prompt: 0, blocked_response: 0, provider_error: 0 },
      flagged: 0,
      ml_unavailable: 0,
    });
    const { wrapper } = await mountAt('/');

    const shares = wrapper.findAll('[data-test="kpi-share"]').map((w) => w.text());
    expect(shares).toEqual(['—', '—']);
  });
});
