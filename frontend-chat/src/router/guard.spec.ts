import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { RouteLocationNormalized } from 'vue-router';
import { authGuard, resetGuardState, type GuardDeps } from './guard';

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
    loadConversations: vi.fn(),
    hasConversation: () => true,
    ...overrides,
  };
}

describe('authGuard', () => {
  beforeEach(() => {
    resetGuardState();
  });

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

  it('loads the conversations for the authenticated user once', async () => {
    const d = deps({ isAuthenticated: () => true, userId: () => 'u1' });
    await authGuard(route('/', { meta: { requiresAuth: true } }), d);
    await authGuard(route('/', { meta: { requiresAuth: true } }), d);
    expect(d.loadConversations).toHaveBeenCalledOnce();
    expect(d.loadConversations).toHaveBeenCalledWith('u1');
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
