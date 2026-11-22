import { beforeEach, describe, expect, it, vi } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { h } from 'vue';
import { createMemoryHistory, createRouter, RouterView } from 'vue-router';
import { ApiError } from '@/api/client';
import { NotCisoError, useAuthStore } from '@/stores/auth';
import { appPlugins } from '@/test/plugins';
import LoginPage from './LoginPage.vue';

async function mountAt(path: string) {
  const pinia = createPinia();
  setActivePinia(pinia);
  const auth = useAuthStore();
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', component: LoginPage },
      { path: '/', component: { render: () => h('div', 'home') } },
    ],
  });
  await router.push(path);
  await router.isReady();
  const wrapper = mount(
    { render: () => h(RouterView) },
    {
      global: { plugins: [...appPlugins(pinia), router] },
    },
  );
  return { wrapper, router, auth };
}

async function submit(wrapper: Awaited<ReturnType<typeof mountAt>>['wrapper']) {
  await wrapper.find('input[type="email"]').setValue('ciso@example.com');
  await wrapper.find('input[type="password"]').setValue('secret123');
  await wrapper.find('form').trigger('submit');
  await flushPromises();
}

describe('LoginPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('logs in and opens the dashboard', async () => {
    const { wrapper, router, auth } = await mountAt('/login');
    const login = vi.spyOn(auth, 'login').mockResolvedValue();

    await submit(wrapper);

    expect(login).toHaveBeenCalledWith('ciso@example.com', 'secret123');
    expect(router.currentRoute.value.path).toBe('/');
  });

  it.each([
    [new ApiError('unauthorized', 401), 'Nieprawidłowy e-mail lub hasło.'],
    [new NotCisoError(), 'To konto nie ma uprawnień do panelu CISO.'],
    [new ApiError('network'), 'Nie udało się połączyć z serwerem.'],
  ])('shows an error for %s', async (error, message) => {
    const { wrapper, router, auth } = await mountAt('/login');
    vi.spyOn(auth, 'login').mockRejectedValue(error);

    await submit(wrapper);

    expect(wrapper.get('[role="alert"]').text()).toBe(message);
    expect(router.currentRoute.value.path).toBe('/login');
  });

  it.each([
    ['expired', 'Sesja wygasła. Zaloguj się ponownie.'],
    ['forbidden', 'To konto nie ma uprawnień do panelu CISO.'],
  ])('explains why the session ended (%s)', async (reason, message) => {
    const { wrapper } = await mountAt(`/login?reason=${reason}`);
    expect(wrapper.get('[data-test="reason"]').text()).toBe(message);
  });
});
