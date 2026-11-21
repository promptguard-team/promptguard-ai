import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import type { Message } from '@/stores/types';
import { appPlugins } from '@/test/plugins';
import MessageList from './MessageList.vue';

function failed(id: string): Message {
  return { id, role: 'assistant', text: '', status: 'error', errorKind: 'network', createdAt: 1 };
}

describe('MessageList', () => {
  it('offers retry only on the last message and reports its id', async () => {
    const messages: Message[] = [
      { id: 'u1', role: 'user', text: 'one', status: 'ok', createdAt: 1 },
      failed('a1'),
      { id: 'u2', role: 'user', text: 'two', status: 'ok', createdAt: 1 },
      failed('a2'),
    ];
    const wrapper = mount(MessageList, {
      props: { messages },
      global: { plugins: appPlugins() },
    });

    const buttons = wrapper.findAll('[data-test="retry"]');
    expect(buttons).toHaveLength(1);
    await buttons[0]!.trigger('click');
    expect(wrapper.emitted('retry')).toEqual([['a2']]);
  });
});
