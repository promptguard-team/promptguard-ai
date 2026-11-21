import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { ApiError } from '@/api/client';
import * as authApi from '@/api/auth';
import { TOKEN_KEY, useAuthStore } from './auth';

vi.mock('@/api/auth');

const user: authApi.User = { id: 'u1', email: 'a@b.pl', role: 'user', is_active: true };

describe('stores/auth', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.mocked(authApi.login).mockReset();
    vi.mocked(authApi.me).mockReset();
  });

  it('starts unauthenticated without a stored token and does not call /auth/me', async () => {
    const store = useAuthStore();
    await store.bootstrap();
    expect(store.isAuthenticated).toBe(false);
    expect(authApi.me).not.toHaveBeenCalled();
  });

  it('restores the session from a stored token', async () => {
    localStorage.setItem(TOKEN_KEY, 'stored');
    vi.mocked(authApi.me).mockResolvedValue(user);
    const store = useAuthStore();
    await store.bootstrap();
    expect(store.token).toBe('stored');
    expect(store.user).toEqual(user);
    expect(store.isAuthenticated).toBe(true);
  });

  it('clears a token the server rejects with 401', async () => {
    localStorage.setItem(TOKEN_KEY, 'stale');
    vi.mocked(authApi.me).mockRejectedValue(new ApiError('unauthorized', 401));
    const store = useAuthStore();
    await store.bootstrap();
    expect(store.isAuthenticated).toBe(false);
    expect(store.token).toBeNull();
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
  });

  it('keeps the token when /auth/me fails for a network reason', async () => {
    localStorage.setItem(TOKEN_KEY, 'kept');
    vi.mocked(authApi.me).mockRejectedValue(new ApiError('network'));
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    const store = useAuthStore();
    await store.bootstrap();
    expect(store.isAuthenticated).toBe(false);
    expect(store.token).toBe('kept');
  });

  it('bootstraps only once', async () => {
    localStorage.setItem(TOKEN_KEY, 'stored');
    vi.mocked(authApi.me).mockResolvedValue(user);
    const store = useAuthStore();
    await store.bootstrap();
    await store.bootstrap();
    expect(authApi.me).toHaveBeenCalledOnce();
  });

  it('login stores the token and loads the user', async () => {
    vi.mocked(authApi.login).mockResolvedValue({ access_token: 'new', token_type: 'bearer' });
    vi.mocked(authApi.me).mockResolvedValue(user);
    const store = useAuthStore();
    await store.login('a@b.pl', 'secret');
    expect(authApi.login).toHaveBeenCalledWith('a@b.pl', 'secret');
    expect(store.token).toBe('new');
    expect(localStorage.getItem(TOKEN_KEY)).toBe('new');
    expect(store.user).toEqual(user);
  });

  it('login propagates the error and stores nothing on bad credentials', async () => {
    vi.mocked(authApi.login).mockRejectedValue(new ApiError('unauthorized', 401));
    const store = useAuthStore();
    await expect(store.login('a@b.pl', 'wrong')).rejects.toBeInstanceOf(ApiError);
    expect(store.token).toBeNull();
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
  });

  it('clearSession removes the token but leaves other storage untouched', async () => {
    localStorage.setItem(TOKEN_KEY, 'stored');
    localStorage.setItem('promptguard.chat.v1.u1', '{"version":1,"conversations":[]}');
    vi.mocked(authApi.me).mockResolvedValue(user);
    const store = useAuthStore();
    await store.bootstrap();
    store.clearSession();
    expect(store.isAuthenticated).toBe(false);
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
    expect(localStorage.getItem('promptguard.chat.v1.u1')).not.toBeNull();
  });

  it('concurrent bootstrap calls share one request and both see the user', async () => {
    localStorage.setItem(TOKEN_KEY, 'stored');
    vi.mocked(authApi.me).mockResolvedValue(user);
    const store = useAuthStore();
    await Promise.all([store.bootstrap(), store.bootstrap()]);
    expect(authApi.me).toHaveBeenCalledOnce();
    expect(store.isAuthenticated).toBe(true);
    expect(store.bootstrapped).toBe(true);
  });

  it('login clears the token when /auth/me fails afterwards', async () => {
    vi.mocked(authApi.login).mockResolvedValue({ access_token: 'new', token_type: 'bearer' });
    vi.mocked(authApi.me).mockRejectedValue(new ApiError('network'));
    const store = useAuthStore();
    await expect(store.login('a@b.pl', 'secret')).rejects.toBeInstanceOf(ApiError);
    expect(store.token).toBeNull();
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
  });
});
