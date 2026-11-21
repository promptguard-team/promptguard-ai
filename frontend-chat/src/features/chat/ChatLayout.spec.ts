import { beforeEach, describe, expect, it, vi } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { Quasar } from 'quasar';
import { createMemoryHistory, createRouter } from 'vue-router';
import * as chatApi from '@/api/chat';
import { i18n } from '@/i18n';
import { CONVERSATION_ROUTE } from '@/router/guard';
import { TOKEN_KEY, useAuthStore } from '@/stores/auth';
import { useConversationsStore } from '@/stores/conversations';
import ChatLayout from './ChatLayout.vue';

vi.mock('@/api/chat');

const sendPrompt = vi.mocked(chatApi.sendPrompt);

async function mountLayout() {
  const pinia = createPinia();
  setActivePinia(pinia);
  const conversations = useConversationsStore();
  conversations.load('u1');
  const stub = { template: '<div />' };
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: stub },
      { path: '/c/:id', name: CONVERSATION_ROUTE, component: stub },
      { path: '/login', component: stub },
    ],
  });
  await router.push('/');
  const wrapper = mount(ChatLayout, {
    global: { plugins: [[Quasar, {}], pinia, i18n, router] },
  });
  return { wrapper, router, conversations };
}

describe('ChatLayout', () => {
  beforeEach(() => {
    sendPrompt.mockReset();
  });

  it('routes to the new conversation on the first send while the reply is pending', async () => {
    let resolve!: (value: chatApi.ChatResponse) => void;
    sendPrompt.mockReturnValue(new Promise((res) => (resolve = res)));
    const { wrapper, router, conversations } = await mountLayout();
    expect(wrapper.text()).toContain('W czym mogę pomóc?');

    await wrapper.find('textarea').setValue('hello');
    await wrapper.find('textarea').trigger('keydown', { key: 'Enter' });
    await flushPromises();

    const id = conversations.sorted[0]!.id;
    expect(router.currentRoute.value.fullPath).toBe(`/c/${id}`);
    expect(conversations.sending).toBe(true);
    expect(wrapper.text()).not.toContain('W czym mogę pomóc?');
    expect(wrapper.find('[data-test="typing"]').exists()).toBe(true);

    resolve({ response: 'Hi there', blocked: false });
    await flushPromises();
    expect(wrapper.text()).toContain('Hi there');
    expect(router.currentRoute.value.fullPath).toBe(`/c/${id}`);
    expect(conversations.sorted).toHaveLength(1);
  });

  it('returns home when the active conversation is deleted', async () => {
    sendPrompt.mockResolvedValue({ response: 'r', blocked: false });
    const { wrapper, router, conversations } = await mountLayout();
    const id = conversations.create('hello');
    await router.push(`/c/${id}`);

    wrapper.findComponent({ name: 'ConversationDrawer' }).vm.$emit('remove', id);
    await flushPromises();

    expect(conversations.get(id)).toBeUndefined();
    expect(router.currentRoute.value.fullPath).toBe('/');
  });

  it('logs out from the drawer: clears the session and goes to /login', async () => {
    const { wrapper, router, conversations } = await mountLayout();
    const auth = useAuthStore();
    auth.token = 'tok';
    localStorage.setItem(TOKEN_KEY, 'tok');

    wrapper.findComponent({ name: 'ConversationDrawer' }).vm.$emit('logout');
    await flushPromises();

    expect(router.currentRoute.value.fullPath).toBe('/login');
    expect(conversations.userId).toBeNull();
    expect(auth.token).toBeNull();
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
  });
});
