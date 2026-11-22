import { describe, expect, it, vi } from 'vitest';
import { createMemoryHistory, createRouter } from 'vue-router';
import { endSession } from './session';

describe('endSession', () => {
  it('clears the session and opens /login with the reason', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/login', component: { render: () => null } },
        { path: '/', component: { render: () => null } },
      ],
    });
    await router.push('/');
    const auth = { clearSession: vi.fn() };

    await endSession(auth, router, 'expired');

    expect(auth.clearSession).toHaveBeenCalledOnce();
    expect(router.currentRoute.value.path).toBe('/login');
    expect(router.currentRoute.value.query).toEqual({ reason: 'expired' });
  });
});
