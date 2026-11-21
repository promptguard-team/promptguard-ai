import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, configureClient, request } from './client';

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('api/client', () => {
  const fetchMock = vi.fn<typeof fetch>();
  const onUnauthorized = vi.fn();

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock);
    fetchMock.mockReset();
    onUnauthorized.mockReset();
    configureClient({ getToken: () => 'tok', onUnauthorized });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('sends JSON with the Bearer header and returns the parsed body', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { ok: true }));
    const result = await request<{ ok: boolean }>('POST', '/chat', { prompt: 'hi' });

    expect(result).toEqual({ ok: true });
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe('/api/chat');
    expect(init?.method).toBe('POST');
    expect(init?.body).toBe(JSON.stringify({ prompt: 'hi' }));
    const headers = init?.headers as Record<string, string>;
    expect(headers.Authorization).toBe('Bearer tok');
    expect(headers['Content-Type']).toBe('application/json');
  });

  it('omits the Authorization header when there is no token', async () => {
    configureClient({ getToken: () => null, onUnauthorized });
    fetchMock.mockResolvedValue(jsonResponse(200, {}));
    await request('GET', '/auth/me');
    const headers = fetchMock.mock.calls[0]![1]?.headers as Record<string, string>;
    expect(headers.Authorization).toBeUndefined();
  });

  it.each([
    [401, 'unauthorized'],
    [403, 'forbidden'],
    [502, 'provider'],
    [500, 'http'],
  ] as const)('maps HTTP %i to ApiError kind "%s" with the detail', async (status, kind) => {
    fetchMock.mockResolvedValue(jsonResponse(status, { detail: 'why' }));
    const error = await request('GET', '/x').catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).kind).toBe(kind);
    expect((error as ApiError).status).toBe(status);
    expect((error as ApiError).detail).toBe('why');
  });

  it('maps a failed fetch to kind "network"', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));
    const error = await request('GET', '/x').catch((e: unknown) => e);
    expect((error as ApiError).kind).toBe('network');
    expect((error as ApiError).status).toBeUndefined();
  });

  it('invokes the unauthorized handler exactly once on 401', async () => {
    fetchMock.mockResolvedValue(jsonResponse(401, { detail: 'expired' }));
    await request('GET', '/x').catch(() => undefined);
    expect(onUnauthorized).toHaveBeenCalledOnce();
  });

  it('does not invoke the unauthorized handler when notifyUnauthorized is false', async () => {
    fetchMock.mockResolvedValue(jsonResponse(401, { detail: 'invalid credentials' }));
    await request('POST', '/auth/login', {}, { notifyUnauthorized: false }).catch(() => undefined);
    expect(onUnauthorized).not.toHaveBeenCalled();
  });

  it('tolerates a non-JSON error body', async () => {
    fetchMock.mockResolvedValue(new Response('Bad Gateway', { status: 502 }));
    const error = await request('GET', '/x').catch((e: unknown) => e);
    expect((error as ApiError).kind).toBe('provider');
    expect((error as ApiError).detail).toBeUndefined();
  });
});
