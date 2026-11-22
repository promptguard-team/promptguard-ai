import { afterEach, describe, expect, it, vi } from 'vitest';
import { Dark } from 'quasar';
import { Bar } from 'vue-chartjs';
import { mount } from '@vue/test-utils';
import type { AuditEventSummary } from '@/api/audit';
import { appPlugins } from '@/test/plugins';
import ActionDonut from './ActionDonut.vue';
import KpiTile from './KpiTile.vue';
import RecentBlocks from './RecentBlocks.vue';
import TrendChart from './TrendChart.vue';

// jsdom has no canvas: replace the chart components with markers.
vi.mock('vue-chartjs', async () => {
  const { defineComponent, h } = await import('vue');
  const marker = (name: string) =>
    defineComponent({
      props: ['data', 'options'],
      setup: () => () => h('div', { 'data-test': name }),
    });
  return { Bar: marker('bar-chart'), Doughnut: marker('doughnut-chart') };
});

const global = { plugins: appPlugins() };

const event: AuditEventSummary = {
  id: 'e1',
  created_at: '2026-11-20T10:00:00Z',
  user_id: 'u1',
  user_email: 'jan@example.com',
  action: 'blocked_prompt',
  rule: null,
  ml_status: 'ok',
  ml_score: 0.97,
  ml_label: 'injection',
  ml_model_version: 'v1',
  flagged: true,
};

describe('KpiTile', () => {
  it('shows the value and share', () => {
    const wrapper = mount(KpiTile, {
      props: {
        label: 'Zablokowane',
        value: 12345,
        share: '25% wszystkich',
        icon: 'block',
        color: 'negative',
        loading: false,
      },
      global,
    });

    expect(wrapper.get('[data-test="kpi-value"]').text()).toMatch(/^12\s345$/);
    expect(wrapper.get('[data-test="kpi-share"]').text()).toBe('25% wszystkich');
  });

  it('shows a dash without a value and a skeleton while loading', () => {
    expect(
      mount(KpiTile, {
        props: { label: 'X', value: null, icon: 'a', color: 'primary', loading: false },
        global,
      })
        .get('[data-test="kpi-value"]')
        .text(),
    ).toBe('—');
    const loading = mount(KpiTile, {
      props: { label: 'X', value: 1, icon: 'a', color: 'primary', loading: true },
      global,
    });
    expect(loading.find('[data-test="kpi-value"]').exists()).toBe(false);
  });
});

describe('ActionDonut', () => {
  it('shows an empty state when there are no events', () => {
    const wrapper = mount(ActionDonut, {
      props: { counts: { allowed: 0, blocked_prompt: 0, blocked_response: 0, provider_error: 0 } },
      global,
    });

    expect(wrapper.find('[data-test="donut-empty"]').exists()).toBe(true);
    expect(wrapper.find('[data-test="doughnut-chart"]').exists()).toBe(false);
  });

  it('draws the chart when there are events', () => {
    const wrapper = mount(ActionDonut, {
      props: { counts: { allowed: 3, blocked_prompt: 1, blocked_response: 0, provider_error: 0 } },
      global,
    });

    expect(wrapper.find('[data-test="doughnut-chart"]').exists()).toBe(true);
  });
});

describe('TrendChart', () => {
  afterEach(() => Dark.set(false));

  it.each([
    [true, '#cbd5e1'],
    [false, '#475569'],
  ])('uses theme-aware tick colors (dark=%s)', (dark, color) => {
    Dark.set(dark);
    const wrapper = mount(TrendChart, {
      props: { series: { bucket: 'hour', points: [] } },
      global,
    });
    const options = wrapper.findComponent(Bar).props('options') as {
      scales: { y: { ticks: { color: string } } };
    };
    expect(options.scales.y.ticks.color).toBe(color);
  });

  it('renders the bar chart', () => {
    const wrapper = mount(TrendChart, {
      props: { series: { bucket: 'hour', points: [] } },
      global,
    });
    expect(wrapper.find('[data-test="bar-chart"]').exists()).toBe(true);
  });
});

describe('RecentBlocks', () => {
  it('lists blocked events', () => {
    const wrapper = mount(RecentBlocks, { props: { items: [event] }, global });

    const row = wrapper.get('[data-test="recent-block"]');
    expect(row.text()).toContain('jan@example.com');
    expect(row.text()).toContain('Zablokowany prompt');
    expect(row.text()).toContain('—');
  });

  it('shows an empty state', () => {
    const wrapper = mount(RecentBlocks, { props: { items: [] }, global });
    expect(wrapper.get('[data-test="recent-empty"]').text()).toBe(
      'Brak blokad w wybranym okresie.',
    );
  });
});
