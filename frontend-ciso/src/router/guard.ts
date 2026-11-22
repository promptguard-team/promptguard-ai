import type { RouteLocationNormalized, RouteLocationRaw } from 'vue-router';

/** What the guard needs from the auth store, as functions so it is trivially testable. */
export interface GuardDeps {
  bootstrap: () => Promise<void>;
  isAuthenticated: () => boolean;
}

export async function authGuard(
  to: RouteLocationNormalized,
  deps: GuardDeps,
): Promise<true | RouteLocationRaw> {
  await deps.bootstrap();
  const authenticated = deps.isAuthenticated();
  if (to.meta.requiresAuth && !authenticated) {
    return { path: '/login' };
  }
  if (to.path === '/login' && authenticated) {
    return { path: '/' };
  }
  return true;
}
