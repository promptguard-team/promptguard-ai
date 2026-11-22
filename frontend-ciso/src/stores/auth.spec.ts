import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { ApiError } from '@/api/client';
import { login as apiLogin, me, type User } from '@/api/auth';
import { NotCisoError, TOKEN_KEY, useAuthStore } from './auth';

vi.mock('@/api/auth', () => ({ login: vi.fn(), me: vi.fn() }));

const ciso: User = { id: 'u1', email: 'ciso@example.com', role: 'ciso', is_active: true };
const chatter: User = { ...ciso, id: 'u2', role: 'chat_user' };

describe('auth store', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.mocked(apiLogin).mockReset();
    vi.mocked(me).mockReset();
  });

  it('logs in a CISO and stores the token', async () => {
    vi.mocked(apiLogin).mockResolvedValue({ access_token: 'tok', token_type: 'bearer' });
    vi.mocked(me).mockResolvedValue(ciso);
    const auth = useAuthStore();

    await auth.login('ciso@example.com', 'pw');

    expect(auth.user).toEqual(ciso);
    expect(auth.isAuthenticated).toBe(true);
    expect(localStorage.getItem(TOKEN_KEY)).toBe('tok');
  });

  it('rejects a non-CISO account and keeps no token', async () => {
    vi.mocked(apiLogin).mockResolvedValue({ access_token: 'tok', token_type: 'bearer' });
    vi.mocked(me).mockResolvedValue(chatter);
    const auth = useAuthStore();

    await expect(auth.login('u@example.com', 'pw')).rejects.toBeInstanceOf(NotCisoError);

    expect(auth.token).toBeNull();
    expect(auth.user).toBeNull();
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
  });

  it('drops the token when me() fails after login', async () => {
    vi.mocked(apiLogin).mockResolvedValue({ access_token: 'tok', token_type: 'bearer' });
    vi.mocked(me).mockRejectedValue(new ApiError('network'));
    const auth = useAuthStore();

    await expect(auth.login('ciso@example.com', 'pw')).rejects.toBeInstanceOf(ApiError);
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
  });

  it('restores a stored CISO session once, sharing the promise', async () => {
    localStorage.setItem(TOKEN_KEY, 'tok');
    vi.mocked(me).mockResolvedValue(ciso);
    const auth = useAuthStore();

    await Promise.all([auth.bootstrap(), auth.bootstrap()]);

    expect(me).toHaveBeenCalledOnce();
    expect(auth.user).toEqual(ciso);
  });

  it('clears a stored token that belongs to a non-CISO', async () => {
    localStorage.setItem(TOKEN_KEY, 'tok');
    vi.mocked(me).mockResolvedValue(chatter);
    const auth = useAuthStore();

    await auth.bootstrap();

    expect(auth.user).toBeNull();
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
  });

  it('clears an expired stored token but keeps it on network trouble', async () => {
    localStorage.setItem(TOKEN_KEY, 'tok');
    vi.mocked(me).mockRejectedValue(new ApiError('unauthorized', 401));
    await useAuthStore().bootstrap();
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();

    setActivePinia(createPinia());
    localStorage.setItem(TOKEN_KEY, 'tok');
    vi.mocked(me).mockRejectedValue(new ApiError('network'));
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    await useAuthStore().bootstrap();
    expect(localStorage.getItem(TOKEN_KEY)).toBe('tok');
    warn.mockRestore();
  });

  it('skips the network without a stored token', async () => {
    await useAuthStore().bootstrap();
    expect(me).not.toHaveBeenCalled();
  });
});
