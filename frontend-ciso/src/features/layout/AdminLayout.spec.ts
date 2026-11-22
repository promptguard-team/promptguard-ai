import { describe, expect, it } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { h } from 'vue';
import { createMemoryHistory, createRouter, RouterView } from 'vue-router';
import { TOKEN_KEY, useAuthStore } from '@/stores/auth';
import { appPlugins } from '@/test/plugins';
import AdminLayout from './AdminLayout.vue';

async function mountLayout() {
  const pinia = createPinia();
  setActivePinia(pinia);
  const auth = useAuthStore();
  auth.token = 'tok';
  auth.user = { id: 'u1', email: 'ciso@example.com', role: 'ciso', is_active: true };
  localStorage.setItem(TOKEN_KEY, 'tok');

  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/',
        component: AdminLayout,
        children: [
          {
            path: '',
            component: { render: () => h('div', 'dash') },
            meta: { titleKey: 'nav.dashboard' },
          },
          {
            path: 'events',
            component: { render: () => h('div', 'events') },
            meta: { titleKey: 'nav.events' },
          },
        ],
      },
      { path: '/login', component: { render: () => h('div', 'login') } },
    ],
  });
  await router.push('/events');
  await router.isReady();
  const wrapper = mount(
    { render: () => h(RouterView) },
    {
      global: { plugins: [...appPlugins(pinia), router] },
    },
  );
  return { wrapper, router, auth };
}

describe('AdminLayout', () => {
  it('shows the view title, navigation and the signed-in email', async () => {
    const { wrapper } = await mountLayout();

    expect(wrapper.get('[data-test="title"]').text()).toBe('Zdarzenia');
    expect(wrapper.text()).toContain('Pulpit');
    expect(wrapper.get('[data-test="user-email"]').text()).toBe('ciso@example.com');
  });

  it('logs out to /login', async () => {
    const { wrapper, router, auth } = await mountLayout();

    await wrapper.get('[data-test="logout"]').trigger('click');
    await flushPromises();

    expect(router.currentRoute.value.path).toBe('/login');
    expect(auth.token).toBeNull();
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
  });
});
