import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import { defineComponent, h } from 'vue';
import { appPlugins } from '@/test/plugins';

describe('test harness', () => {
  it('mounts a component with Quasar, Pinia and i18n installed', () => {
    const Probe = defineComponent({ render: () => h('div', 'ok') });
    const wrapper = mount(Probe, { global: { plugins: appPlugins() } });
    expect(wrapper.text()).toBe('ok');
  });
});
