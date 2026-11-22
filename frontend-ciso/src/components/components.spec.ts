import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import { QBtnToggle } from 'quasar';
import { appPlugins } from '@/test/plugins';
import ActionBadge from './ActionBadge.vue';
import ErrorBanner from './ErrorBanner.vue';
import RangeSelect from './RangeSelect.vue';

const global = { plugins: appPlugins() };

describe('ErrorBanner', () => {
  it('is an alert that emits retry', async () => {
    const wrapper = mount(ErrorBanner, { global });

    expect(wrapper.get('[role="alert"]').text()).toContain('Nie udało się pobrać danych.');
    await wrapper.get('[data-test="retry"]').trigger('click');

    expect(wrapper.emitted('retry')).toHaveLength(1);
  });
});

describe('RangeSelect', () => {
  it('offers the presets and updates the model', async () => {
    const wrapper = mount(RangeSelect, { props: { modelValue: '7d' }, global });

    expect(wrapper.text()).toContain('24 h');
    expect(wrapper.text()).toContain('30 dni');
    wrapper.findComponent(QBtnToggle).vm.$emit('update:modelValue', '24h');

    expect(wrapper.emitted('update:modelValue')).toEqual([['24h']]);
  });
});

describe('ActionBadge', () => {
  it.each([
    ['allowed', 'Dozwolone', 'bg-positive'],
    ['blocked_prompt', 'Zablokowany prompt', 'bg-negative'],
    ['provider_error', 'Błąd dostawcy', 'bg-grey-7'],
  ] as const)('renders %s', (action, label, colorClass) => {
    const wrapper = mount(ActionBadge, { props: { action }, global });

    expect(wrapper.text()).toBe(label);
    expect(wrapper.classes()).toContain(colorClass);
  });
});
