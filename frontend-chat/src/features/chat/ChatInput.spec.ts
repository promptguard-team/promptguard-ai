import { afterEach, describe, expect, it } from 'vitest';
import { nextTick } from 'vue';
import { mount, type VueWrapper } from '@vue/test-utils';
import { appPlugins } from '@/test/plugins';
import ChatInput from './ChatInput.vue';

const mounted: VueWrapper[] = [];

function mountInput(props: { disabled?: boolean } = {}, attach = false) {
  const wrapper = mount(ChatInput, {
    props: { disabled: false, ...props },
    global: { plugins: appPlugins() },
    ...(attach ? { attachTo: document.body } : {}),
  });
  mounted.push(wrapper);
  return wrapper;
}

afterEach(() => {
  while (mounted.length > 0) {
    mounted.pop()?.unmount();
  }
});

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

  it('does not send on Enter while an IME composition is active', async () => {
    const wrapper = mountInput();
    const textarea = wrapper.find('textarea');
    await textarea.setValue('nihon');
    await textarea.trigger('keydown', { key: 'Enter', isComposing: true });
    await textarea.trigger('keydown', { key: 'Enter', keyCode: 229 });
    expect(wrapper.emitted('send')).toBeUndefined();
  });

  it('focuses the textarea on mount', () => {
    const wrapper = mountInput({}, true);
    expect(document.activeElement).toBe(wrapper.find('textarea').element);
  });

  it('keeps focus after sending', async () => {
    const wrapper = mountInput({}, true);
    const textarea = wrapper.find('textarea');
    await textarea.setValue('hello');
    (document.activeElement as HTMLElement).blur();
    await textarea.trigger('keydown', { key: 'Enter' });
    await nextTick();
    expect(document.activeElement).toBe(textarea.element);
  });

  it('regains focus when disabled goes from true to false', async () => {
    const wrapper = mountInput({ disabled: true }, true);
    expect(document.activeElement).not.toBe(wrapper.find('textarea').element);
    await wrapper.setProps({ disabled: false });
    await nextTick();
    expect(document.activeElement).toBe(wrapper.find('textarea').element);
  });

  it('labels the textarea and announces the counter politely', async () => {
    const wrapper = mountInput();
    expect(wrapper.find('textarea').attributes('aria-label')).toBeTruthy();
    await wrapper.find('textarea').setValue('a'.repeat(30001));
    expect(wrapper.find('[data-test="counter"]').attributes('aria-live')).toBe('polite');
  });

  it('derives max-height from the row limit', () => {
    const wrapper = mountInput();
    const style = wrapper.find('textarea').attributes('style') ?? '';
    expect(style).toContain('--chat-input-max-rows: 6');
  });

  it('shows no counter at exactly 30000 characters', async () => {
    const wrapper = mountInput();
    await wrapper.find('textarea').setValue('a'.repeat(30000));
    expect(wrapper.find('[data-test="counter"]').exists()).toBe(false);
  });

  it('still sends at exactly 32000 characters', async () => {
    const wrapper = mountInput();
    const textarea = wrapper.find('textarea');
    await textarea.setValue('a'.repeat(32000));
    await textarea.trigger('keydown', { key: 'Enter' });
    expect(wrapper.emitted('send')).toHaveLength(1);
  });
});
