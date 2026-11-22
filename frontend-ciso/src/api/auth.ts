import { request } from './client';

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface User {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
}

export function login(email: string, password: string): Promise<TokenResponse> {
  return request<TokenResponse>('POST', '/auth/login', {
    body: { email, password },
    notifySession: false,
  });
}

export function me(options?: { notifySession?: boolean }): Promise<User> {
  return request<User>('GET', '/auth/me', options);
}
