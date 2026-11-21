import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import { appPlugins } from '@/test/plugins';
import ChatInput from './ChatInput.vue';

function mountInput(props: { disabled?: boolean } = {}) {
  return mount(ChatInput, {
    props: { disabled: false, ...props },
    global: { plugins: appPlugins() },
  });
}

describe('ChatInput', () => {
  it('emits send with the trimmed text on Enter and clears the field', async () => {
    const wrapper = mountInput();
    const textarea = wrapper.find('textarea');
    await textarea.setValue('  hello  ');
    await textarea.trigger('keydown', { key: 'Enter' });
    expect(wrapper.emitted('send')).toEqual([['hello']]);
    expect((textarea.element as HTMLTextAreaElement).value).toBe('');
  });

  it('does not send on Shift+Enter', async () => {
    const wrapper = mountInput();
    const textarea = wrapper.find('textarea');
    await textarea.setValue('line');
    await textarea.trigger('keydown', { key: 'Enter', shiftKey: true });
    expect(wrapper.emitted('send')).toBeUndefined();
  });

  it('ignores empty or whitespace-only input', async () => {
    const wrapper = mountInput();
    const textarea = wrapper.find('textarea');
    await textarea.setValue('   ');
    await textarea.trigger('keydown', { key: 'Enter' });
    expect(wrapper.emitted('send')).toBeUndefined();
  });

  it('does not send while disabled', async () => {
    const wrapper = mountInput({ disabled: true });
    const textarea = wrapper.find('textarea');
    await textarea.setValue('hello');
    await textarea.trigger('keydown', { key: 'Enter' });
    expect(wrapper.emitted('send')).toBeUndefined();
    expect(wrapper.find('button').attributes('disabled')).toBeDefined();
  });

  it('shows the counter above 30000 characters and blocks sending above 32000', async () => {
    const wrapper = mountInput();
    const textarea = wrapper.find('textarea');
    expect(wrapper.find('[data-test="counter"]').exists()).toBe(false);

    await textarea.setValue('a'.repeat(30001));
    expect(wrapper.find('[data-test="counter"]').text()).toContain('30001');

    await textarea.setValue('a'.repeat(32001));
    await textarea.trigger('keydown', { key: 'Enter' });
    expect(wrapper.emitted('send')).toBeUndefined();
    expect(wrapper.find('button').attributes('disabled')).toBeDefined();
  });

  it('sends on the button click', async () => {
    const wrapper = mountInput();
    await wrapper.find('textarea').setValue('click');
    await wrapper.find('button').trigger('click');
    expect(wrapper.emitted('send')).toEqual([['click']]);
  });
});
