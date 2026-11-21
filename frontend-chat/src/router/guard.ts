import type { RouteLocationNormalized, RouteLocationRaw } from 'vue-router';

/** What the guard needs from the stores, expressed as functions so it is trivially testable. */
export interface GuardDeps {
  bootstrap: () => Promise<void>;
  isAuthenticated: () => boolean;
  userId: () => string | null;
  /** The user whose conversations are currently loaded, or null after unload. */
  loadedUserId: () => string | null;
  loadConversations: (userId: string) => void;
  hasConversation: (id: string) => boolean;
}

export const CONVERSATION_ROUTE = 'conversation';

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

  if (authenticated) {
    const userId = deps.userId();
    if (userId !== null && userId !== deps.loadedUserId()) {
      deps.loadConversations(userId);
    }
    if (to.name === CONVERSATION_ROUTE) {
      const id = String(to.params.id ?? '');
      if (!deps.hasConversation(id)) {
        return { path: '/' };
      }
    }
  }
  return true;
}
