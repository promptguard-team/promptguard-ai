import type { SessionEndReason } from '@/api/client';
import type { RouteLocationNormalized, RouteLocationRaw } from 'vue-router';

/** What the guard needs from the auth store, as functions so it is trivially testable. */
export interface GuardDeps {
  bootstrap: () => Promise<void>;
  isAuthenticated: () => boolean;
  /** Returns and clears why a stored session was dropped at startup, if it was. */
  takeEndReason: () => SessionEndReason | null;
}

export async function authGuard(
  to: RouteLocationNormalized,
  deps: GuardDeps,
): Promise<true | RouteLocationRaw> {
  await deps.bootstrap();
  const authenticated = deps.isAuthenticated();
  if (to.meta.requiresAuth && !authenticated) {
    const reason = deps.takeEndReason();
    return reason ? { path: '/login', query: { reason } } : { path: '/login' };
  }
  if (to.path === '/login' && authenticated) {
    return { path: '/' };
  }
  return true;
}
