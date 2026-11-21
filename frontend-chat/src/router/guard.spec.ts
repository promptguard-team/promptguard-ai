import { describe, expect, it, vi } from 'vitest';
import type { RouteLocationNormalized } from 'vue-router';
import { authGuard, type GuardDeps } from './guard';

function route(
  path: string,
  extra: Partial<RouteLocationNormalized> = {},
): RouteLocationNormalized {
  return {
    path,
    name: undefined,
    params: {},
    query: {},
    hash: '',
    fullPath: path,
    matched: [],
    meta: {},
    redirectedFrom: undefined,
    ...extra,
  } as RouteLocationNormalized;
}

function deps(overrides: Partial<GuardDeps> = {}): GuardDeps {
  return {
    bootstrap: vi.fn().mockResolvedValue(undefined),
    isAuthenticated: () => false,
    userId: () => null,
    loadedUserId: () => null,
    loadConversations: vi.fn(),
    hasConversation: () => true,
    ...overrides,
  };
}

describe('authGuard', () => {
  it('awaits bootstrap before deciding', async () => {
    const d = deps();
    await authGuard(route('/login'), d);
    expect(d.bootstrap).toHaveBeenCalledOnce();
  });

  it('redirects an unauthenticated user from a protected route to /login', async () => {
    const result = await authGuard(route('/', { meta: { requiresAuth: true } }), deps());
    expect(result).toEqual({ path: '/login' });
  });

  it('lets an unauthenticated user open /login', async () => {
    expect(await authGuard(route('/login'), deps())).toBe(true);
  });

  it('sends an authenticated user away from /login', async () => {
    const d = deps({ isAuthenticated: () => true, userId: () => 'u1' });
    expect(await authGuard(route('/login'), d)).toEqual({ path: '/' });
  });

  /** Simulates the conversations store: load() records the user, unload() clears it. */
  function authedAs(user: { id: string | null }): { d: GuardDeps; unload: () => void } {
    let loaded: string | null = null;
    const d = deps({
      isAuthenticated: () => user.id !== null,
      userId: () => user.id,
      loadedUserId: () => loaded,
      loadConversations: vi.fn((id: string) => {
        loaded = id;
      }),
    });
    return {
      d,
      unload: () => {
        loaded = null;
      },
    };
  }

  const home = (): RouteLocationNormalized => route('/', { meta: { requiresAuth: true } });

  it('loads the conversations for the authenticated user once', async () => {
    const { d } = authedAs({ id: 'u1' });
    await authGuard(home(), d);
    await authGuard(home(), d);
    expect(d.loadConversations).toHaveBeenCalledOnce();
    expect(d.loadConversations).toHaveBeenCalledWith('u1');
  });

  it('reloads the conversations after the store was unloaded', async () => {
    const { d, unload } = authedAs({ id: 'u1' });
    await authGuard(home(), d);
    unload();
    await authGuard(home(), d);
    expect(d.loadConversations).toHaveBeenCalledTimes(2);
  });

  it('reloads the conversations when the user changes', async () => {
    const user = { id: 'u1' as string | null };
    const { d } = authedAs(user);
    await authGuard(home(), d);
    user.id = 'u2';
    await authGuard(home(), d);
    expect(d.loadConversations).toHaveBeenCalledTimes(2);
    expect(d.loadConversations).toHaveBeenLastCalledWith('u2');
  });

  it('does not load conversations when unauthenticated', async () => {
    const { d } = authedAs({ id: null });
    await authGuard(route('/login'), d);
    await authGuard(home(), d);
    expect(d.loadConversations).not.toHaveBeenCalled();
  });

  it('redirects an unknown conversation id to /', async () => {
    const d = deps({
      isAuthenticated: () => true,
      userId: () => 'u1',
      hasConversation: () => false,
    });
    const result = await authGuard(
      route('/c/nope', {
        name: 'conversation',
        params: { id: 'nope' },
        meta: { requiresAuth: true },
      }),
      d,
    );
    expect(result).toEqual({ path: '/' });
  });

  it('allows a known conversation id', async () => {
    const d = deps({ isAuthenticated: () => true, userId: () => 'u1' });
    const result = await authGuard(
      route('/c/ok', { name: 'conversation', params: { id: 'ok' }, meta: { requiresAuth: true } }),
      d,
    );
    expect(result).toBe(true);
  });
});
