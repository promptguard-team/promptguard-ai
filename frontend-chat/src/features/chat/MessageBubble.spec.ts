import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import { appPlugins } from '@/test/plugins';
import type { Message } from '@/stores/types';
import MessageBubble from './MessageBubble.vue';

function msg(overrides: Partial<Message>): Message {
  return { id: 'm', role: 'assistant', text: '', status: 'ok', createdAt: 0, ...overrides };
}

function mountBubble(message: Message, extraProps: { canRetry?: boolean } = {}) {
  return mount(MessageBubble, {
    props: { message, ...extraProps },
    global: { plugins: appPlugins() },
  });
}

describe('MessageBubble', () => {
  it('renders a user message as plain text in a bubble', () => {
    const wrapper = mountBubble(msg({ role: 'user', text: '<b>hi</b>\nthere' }));
    expect(wrapper.classes()).toContain('message--user');
    expect(wrapper.find('.message__text').text()).toContain('<b>hi</b>');
    expect(wrapper.find('b').exists()).toBe(false);
  });

  it('adds the policy note to a blocked user message', () => {
    const wrapper = mountBubble(msg({ role: 'user', text: 'x', status: 'blocked' }));
    expect(wrapper.text()).toContain('Wiadomość zablokowana przez politykę bezpieczeństwa.');
  });

  it('renders assistant markdown', () => {
    const wrapper = mountBubble(msg({ text: '**bold**' }));
    expect(wrapper.classes()).toContain('message--assistant');
    expect(wrapper.find('.markdown strong').text()).toBe('bold');
  });

  it('shows a typing indicator while sending', () => {
    const wrapper = mountBubble(msg({ status: 'sending' }));
    expect(wrapper.find('[data-test="typing"]').exists()).toBe(true);
  });

  it('shows the blocked-response note', () => {
    const wrapper = mountBubble(msg({ status: 'blocked' }));
    expect(wrapper.text()).toContain('Odpowiedź modelu została zablokowana przez PromptGuard.');
  });

  it.each([
    ['provider', 'Dostawca LLM jest niedostępny.'],
    ['network', 'Nie udało się połączyć z serwerem.'],
    ['http', 'Nie udało się połączyć z serwerem.'],
  ] as const)('shows the %s error with a retry button', async (errorKind, copy) => {
    const wrapper = mountBubble(msg({ status: 'error', errorKind }));
    expect(wrapper.text()).toContain(copy);
    await wrapper.find('[data-test="retry"]').trigger('click');
    expect(wrapper.emitted('retry')).toHaveLength(1);
  });

  it('hides the retry button when canRetry is false', () => {
    const wrapper = mountBubble(msg({ status: 'error', errorKind: 'network' }), {
      canRetry: false,
    });
    expect(wrapper.text()).toContain('Nie udało się połączyć z serwerem.');
    expect(wrapper.find('[data-test="retry"]').exists()).toBe(false);
  });
});
