import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import { login as apiLogin, me, type User } from '@/api/auth';
import { ApiError } from '@/api/client';
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
  let bootstrapping: Promise<void> | null = null;

  const isAuthenticated = computed(() => user.value !== null);

  function clearSession(): void {
    token.value = null;
    user.value = null;
    removeKey(TOKEN_KEY);
  }

  async function resolveStoredToken(): Promise<void> {
    if (!token.value) {
      return;
    }
    try {
      const current = await me();
      if (current.role === CISO_ROLE) {
        user.value = current;
      } else {
        clearSession();
      }
    } catch (error) {
      if (error instanceof ApiError && error.kind === 'unauthorized') {
        clearSession();
        return;
      }
      // Network or server trouble: keep the token, the guard sends the user to /login.
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
    token.value = result.access_token;
    writeString(TOKEN_KEY, result.access_token);
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
    user.value = current;
  }

  return { token, user, isAuthenticated, bootstrap, login, clearSession };
});
