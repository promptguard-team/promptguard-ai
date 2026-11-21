import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import { login as apiLogin, me, type User } from '@/api/auth';
import { ApiError } from '@/api/client';
import { readString, removeKey, writeString } from '@/storage/local';

export const TOKEN_KEY = 'promptguard.auth.token';

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(readString(TOKEN_KEY));
  const user = ref<User | null>(null);
  const bootstrapped = ref(false);

  const isAuthenticated = computed(() => user.value !== null);

  function clearSession(): void {
    token.value = null;
    user.value = null;
    removeKey(TOKEN_KEY);
  }

  /** Resolves the stored token into a user once per app start. */
  async function bootstrap(): Promise<void> {
    if (bootstrapped.value) {
      return;
    }
    bootstrapped.value = true;
    if (!token.value) {
      return;
    }
    try {
      user.value = await me();
    } catch (error) {
      if (error instanceof ApiError && error.kind === 'unauthorized') {
        clearSession();
        return;
      }
      // Network or server trouble: keep the token, the guard sends the user to /login.
    }
  }

  async function login(email: string, password: string): Promise<void> {
    const result = await apiLogin(email, password);
    token.value = result.access_token;
    writeString(TOKEN_KEY, result.access_token);
    user.value = await me();
  }

  return { token, user, bootstrapped, isAuthenticated, bootstrap, login, clearSession };
});
