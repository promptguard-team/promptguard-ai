import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import { login as apiLogin, me, type User } from '@/api/auth';
import { ApiError, type SessionEndReason } from '@/api/client';
import { readString, removeKey, writeString } from '@/storage/local';

// The chat app shares this origin, so the panel keeps its own key.
export const TOKEN_KEY = 'promptguard.ciso.token';
export const CISO_ROLE = 'ciso';

/** The credentials were valid but the account may not use the panel. */
export class NotCisoError extends Error {
  constructor() {
    super('account lacks the ciso role');
    this.name = 'NotCisoError';
  }
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(readString(TOKEN_KEY));
  const user = ref<User | null>(null);
  // Set when a stored session turns out unusable at startup; the guard shows it on /login.
  const endReason = ref<SessionEndReason | null>(null);
  let bootstrapping: Promise<void> | null = null;

  const isAuthenticated = computed(() => user.value !== null);

  function clearSession(): void {
    token.value = null;
    user.value = null;
    removeKey(TOKEN_KEY);
  }

  async function resolveStoredToken(): Promise<void> {
    const stored = token.value;
    if (!stored) {
      return;
    }
    try {
      const current = await me();
      if (token.value !== stored) {
        // The session changed (logout or a new login) while me() was in flight.
        return;
      }
      if (current.role === CISO_ROLE) {
        user.value = current;
      } else {
        clearSession();
        endReason.value = 'forbidden';
      }
    } catch (error) {
      if (error instanceof ApiError && error.kind === 'unauthorized') {
        clearSession();
        return;
      }
      // Network or server trouble: keep the token, the guard sends the user to /login,
      // and the next navigation retries instead of reusing this failed attempt.
      bootstrapping = null;
      console.warn('could not restore the session', error);
    }
  }

  /** Resolves the stored token once per app start; concurrent callers share the result. */
  function bootstrap(): Promise<void> {
    bootstrapping ??= resolveStoredToken();
    return bootstrapping;
  }

  async function login(email: string, password: string): Promise<void> {
    const result = await apiLogin(email, password);
    // The client reads token.value for me(); persist only once the role check passes.
    token.value = result.access_token;
    let current: User;
    try {
      current = await me();
    } catch (error) {
      // Never keep a token we could not resolve into a user.
      clearSession();
      throw error;
    }
    if (current.role !== CISO_ROLE) {
      clearSession();
      throw new NotCisoError();
    }
    writeString(TOKEN_KEY, result.access_token);
    user.value = current;
    endReason.value = null;
    // The session is already resolved; a later bootstrap() must not call me() again.
    bootstrapping = Promise.resolve();
  }

  return { token, user, endReason, isAuthenticated, bootstrap, login, clearSession };
});
