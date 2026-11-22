import { describe, expect, it, vi } from 'vitest';
import type { RouteLocationNormalized } from 'vue-router';
import type { SessionEndReason } from '@/api/client';
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

function deps(authenticated: boolean, reason: SessionEndReason | null = null): GuardDeps {
  return {
    bootstrap: vi.fn().mockResolvedValue(undefined),
    isAuthenticated: () => authenticated,
    takeEndReason: vi.fn().mockReturnValue(reason),
  };
}

describe('authGuard', () => {
  it('waits for bootstrap before deciding', async () => {
    let authenticated = false;
    let finish: () => void = () => {};
    const d: GuardDeps = {
      bootstrap: () =>
        new Promise<void>((resolve) => {
          finish = () => {
            authenticated = true;
            resolve();
          };
        }),
      isAuthenticated: () => authenticated,
      takeEndReason: () => null,
    };

    const result = authGuard(route('/login'), d);
    finish();

    expect(await result).toEqual({ path: '/' });
  });

  it('passes the end reason to /login', async () => {
    expect(await authGuard(route('/', true), deps(false, 'forbidden'))).toEqual({
      path: '/login',
      query: { reason: 'forbidden' },
    });
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
