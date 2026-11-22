import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { createMemoryHistory, createRouter } from 'vue-router';
import { me, type User } from '@/api/auth';
import { ApiError, configureClient } from '@/api/client';
import { TOKEN_KEY, useAuthStore } from '@/stores/auth';
import { installGuard, routes } from './index';
import { endSession } from './session';

vi.mock('@/api/auth', () => ({ login: vi.fn(), me: vi.fn() }));

const chatter: User = { id: 'u2', email: 'u@example.com', role: 'chat_user', is_active: true };

function setup() {
  setActivePinia(createPinia());
  const router = createRouter({ history: createMemoryHistory(), routes });
  installGuard(router);
  return { router, auth: useAuthStore() };
}

describe('app router with the real guard', () => {
  beforeEach(() => {
    vi.mocked(me).mockReset();
    configureClient({ getToken: () => null, onSessionEnd: () => {} });
  });

  it('sends a guest from /events to /login', async () => {
    const { router } = setup();
    await router.push('/events');
    expect(router.currentRoute.value.path).toBe('/login');
  });

  it('sends a guest from an unknown path to /login', async () => {
    const { router } = setup();
    await router.push('/nope');
    expect(router.currentRoute.value.path).toBe('/login');
  });

  it('shows the forbidden reason when the stored token lost the ciso role', async () => {
    localStorage.setItem(TOKEN_KEY, 'tok');
    vi.mocked(me).mockResolvedValue(chatter);
    const { router } = setup();

    await router.push('/');

    expect(router.currentRoute.value.path).toBe('/login');
    expect(router.currentRoute.value.query).toEqual({ reason: 'forbidden' });
  });

  it('ends on /login with the token cleared when the stored token is rejected', async () => {
    localStorage.setItem(TOKEN_KEY, 'tok');
    // The mocked me() bypasses the client, so no real 401 triggers onSessionEnd here; the
    // store clears the session itself and the guard redirects to a plain /login.
    vi.mocked(me).mockRejectedValue(new ApiError('unauthorized', 401));
    const { router, auth } = setup();
    configureClient({
      getToken: () => auth.token,
      onSessionEnd: (reason) => void endSession(auth, router, reason),
    });

    await router.push('/');

    expect(router.currentRoute.value.path).toBe('/login');
    expect(auth.token).toBeNull();
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
  });
});
