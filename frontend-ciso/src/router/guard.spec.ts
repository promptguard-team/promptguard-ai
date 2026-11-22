import { describe, expect, it, vi } from 'vitest';
import type { RouteLocationNormalized } from 'vue-router';
import { authGuard, type GuardDeps } from './guard';

function route(path: string, requiresAuth = false): RouteLocationNormalized {
  return {
    path,
    name: undefined,
    params: {},
    query: {},
    hash: '',
    fullPath: path,
    matched: [],
    meta: { requiresAuth },
    redirectedFrom: undefined,
  } as RouteLocationNormalized;
}

function deps(authenticated: boolean): GuardDeps {
  return {
    bootstrap: vi.fn().mockResolvedValue(undefined),
    isAuthenticated: () => authenticated,
  };
}

describe('authGuard', () => {
  it('waits for bootstrap', async () => {
    const d = deps(false);
    await authGuard(route('/login'), d);
    expect(d.bootstrap).toHaveBeenCalledOnce();
  });

  it('sends guests from protected routes to /login', async () => {
    expect(await authGuard(route('/', true), deps(false))).toEqual({ path: '/login' });
  });

  it('lets guests open /login', async () => {
    expect(await authGuard(route('/login'), deps(false))).toBe(true);
  });

  it('sends signed-in users away from /login', async () => {
    expect(await authGuard(route('/login'), deps(true))).toEqual({ path: '/' });
  });

  it('lets signed-in users open protected routes', async () => {
    expect(await authGuard(route('/events', true), deps(true))).toBe(true);
  });
});
