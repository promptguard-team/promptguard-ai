import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { QBtnToggle, QChip, QInput, QSelect } from 'quasar';
import { appPlugins } from '@/test/plugins';
import { defaultEventFilters, type EventFilters } from './eventQuery';
import EventFiltersBar from './EventFiltersBar.vue';

function mountBar(overrides: Partial<EventFilters> = {}) {
  return mount(EventFiltersBar, {
    props: { filters: { ...defaultEventFilters(), ...overrides } },
    global: { plugins: appPlugins() },
  });
}

describe('EventFiltersBar', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('emits a preset range', () => {
    const wrapper = mountBar();
    wrapper.findComponent(QBtnToggle).vm.$emit('update:modelValue', '24h');
    expect(wrapper.emitted('change')).toEqual([[{ range: '24h', fromDay: null, toDay: null }]]);
  });

  it('starts a custom range at the last seven Warsaw days', () => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date('2026-11-20T10:00:00Z'));
    const wrapper = mountBar();

    wrapper.findComponent(QBtnToggle).vm.$emit('update:modelValue', 'custom');

    expect(wrapper.emitted('change')).toEqual([
      [{ range: 'custom', fromDay: '2026-11-14', toDay: '2026-11-20' }],
    ]);
  });

  it('emits valid custom days and flags invalid ones', async () => {
    const wrapper = mountBar({ range: 'custom', fromDay: '2026-11-14', toDay: '2026-11-20' });
    const [from] = wrapper.findAllComponents(QInput);

    from!.vm.$emit('update:modelValue', '2026-11-01');
    expect(wrapper.emitted('change')).toEqual([
      [{ range: 'custom', fromDay: '2026-11-01', toDay: '2026-11-20' }],
    ]);

    from!.vm.$emit('update:modelValue', '2026-11-25');
    await wrapper.vm.$nextTick();
    expect(wrapper.emitted('change')).toHaveLength(1);
    expect(wrapper.text()).toContain('Nieprawidłowy zakres dat.');
  });

  it('emits action, flagged and ML status filters', () => {
    const wrapper = mountBar();
    const [actions, flagged, ml] = wrapper.findAllComponents(QSelect);

    actions!.vm.$emit('update:modelValue', ['blocked_prompt']);
    actions!.vm.$emit('update:modelValue', null);
    flagged!.vm.$emit('update:modelValue', 'true');
    flagged!.vm.$emit('update:modelValue', 'all');
    ml!.vm.$emit('update:modelValue', 'unavailable');

    expect(wrapper.emitted('change')).toEqual([
      [{ actions: ['blocked_prompt'] }],
      [{ actions: [] }],
      [{ flagged: true }],
      [{ flagged: null }],
      [{ mlStatus: 'unavailable' }],
    ]);
  });

  it('shows the user chip and clears it', () => {
    const wrapper = mountBar({
      userId: '3f2b8c1e-4d5a-4b6c-8d7e-9f0a1b2c3d4e',
      userEmail: 'jan@example.com',
    });

    const chip = wrapper.findComponent(QChip);
    expect(chip.text()).toContain('jan@example.com');
    chip.vm.$emit('remove');

    expect(wrapper.emitted('change')).toEqual([[{ userId: null, userEmail: null }]]);
  });

  it('keeps an invalid draft when an unrelated filter changes', async () => {
    const wrapper = mountBar({ range: 'custom', fromDay: '2026-11-14', toDay: '2026-11-20' });
    const [from] = wrapper.findAllComponents(QInput);
    from!.vm.$emit('update:modelValue', '2026-11-25');
    await wrapper.vm.$nextTick();

    await wrapper.setProps({
      filters: {
        ...defaultEventFilters(),
        range: 'custom',
        fromDay: '2026-11-14',
        toDay: '2026-11-20',
        flagged: true,
      },
    });

    expect(wrapper.text()).toContain('Nieprawidłowy zakres dat.');
    expect(wrapper.findAllComponents(QInput)[0]!.props('modelValue')).toBe('2026-11-25');
  });

  it('shows no range error while a draft is empty', async () => {
    const wrapper = mountBar({ range: 'custom', fromDay: '2026-11-14', toDay: '2026-11-20' });
    const [from] = wrapper.findAllComponents(QInput);

    from!.vm.$emit('update:modelValue', '');
    await wrapper.vm.$nextTick();

    expect(wrapper.text()).not.toContain('Nieprawidłowy zakres dat.');
  });

  it('shows the range error under both date inputs', async () => {
    const wrapper = mountBar({ range: 'custom', fromDay: '2026-11-14', toDay: '2026-11-20' });
    wrapper.findAllComponents(QInput)[0]!.vm.$emit('update:modelValue', '2026-11-25');
    await wrapper.vm.$nextTick();

    expect(wrapper.findAllComponents(QInput)[1]!.props('errorMessage')).toBe(
      'Nieprawidłowy zakres dat.',
    );
  });
});
