import { beforeEach, describe, expect, it, vi } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';
import { createRouter, createMemoryHistory } from 'vue-router';
import { ApiError } from '@/api/client';
import { useAuthStore } from '@/stores/auth';
import { appPlugins } from '@/test/plugins';
import LoginPage from './LoginPage.vue';

vi.mock('@/stores/auth');

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div>home</div>' } },
      { path: '/login', component: LoginPage },
    ],
  });
}

async function mountPage(path = '/login') {
  const router = makeRouter();
  await router.push(path);
  const wrapper = mount(LoginPage, { global: { plugins: [...appPlugins(), router] } });
  return { wrapper, router };
}

describe('LoginPage', () => {
  const login = vi.fn();

  beforeEach(() => {
    login.mockReset();
    vi.mocked(useAuthStore).mockReturnValue({ login } as unknown as ReturnType<
      typeof useAuthStore
    >);
  });

  it('logs in and navigates home', async () => {
    login.mockResolvedValue(undefined);
    const { wrapper, router } = await mountPage();
    await wrapper.find('input[type="email"]').setValue('a@b.pl');
    await wrapper.find('input[type="password"]').setValue('secret');
    await wrapper.find('form').trigger('submit');
    await flushPromises();
    expect(login).toHaveBeenCalledWith('a@b.pl', 'secret');
    expect(router.currentRoute.value.path).toBe('/');
  });

  it('shows the credentials error on 401', async () => {
    login.mockRejectedValue(new ApiError('unauthorized', 401));
    const { wrapper } = await mountPage();
    await wrapper.find('input[type="email"]').setValue('a@b.pl');
    await wrapper.find('input[type="password"]').setValue('bad');
    await wrapper.find('form').trigger('submit');
    await flushPromises();
    expect(wrapper.text()).toContain('Nieprawidłowy e-mail lub hasło.');
  });

  it('shows a generic error on other failures', async () => {
    login.mockRejectedValue(new ApiError('network'));
    const { wrapper } = await mountPage();
    await wrapper.find('input[type="email"]').setValue('a@b.pl');
    await wrapper.find('input[type="password"]').setValue('x');
    await wrapper.find('form').trigger('submit');
    await flushPromises();
    expect(wrapper.text()).toContain('Nie udało się połączyć z serwerem.');
  });

  it('shows the expired-session banner when reason=expired', async () => {
    const { wrapper } = await mountPage('/login?reason=expired');
    expect(wrapper.text()).toContain('Sesja wygasła');
  });
});
