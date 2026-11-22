import type { Router } from 'vue-router';
import type { SessionEndReason } from '@/api/client';

/** Drops the session and sends the user to /login with the reason for the banner. */
export function endSession(
  auth: { clearSession(): void },
  router: Router,
  reason: SessionEndReason,
): Promise<unknown> {
  auth.clearSession();
  return router.push({ path: '/login', query: { reason } });
}
