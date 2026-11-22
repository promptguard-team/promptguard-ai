import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, buildUrl, configureClient, isAborted, request } from './client';

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('api/client', () => {
  const fetchMock = vi.fn<typeof fetch>();
  const onSessionEnd = vi.fn();

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock);
    fetchMock.mockReset();
    onSessionEnd.mockReset();
    configureClient({ getToken: () => 'tok', onSessionEnd });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('builds query strings, repeating arrays and skipping undefined', () => {
    expect(
      buildUrl('/audit/events', {
        action: ['blocked_prompt', 'blocked_response'],
        flagged: false,
        limit: 25,
        user_id: undefined,
      }),
    ).toBe(
      '/api/audit/events?action=blocked_prompt&action=blocked_response&flagged=false&limit=25',
    );
    expect(buildUrl('/auth/me')).toBe('/api/auth/me');
  });

  it('sends the Bearer header and a JSON body', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { ok: true }));

    const result = await request<{ ok: boolean }>('POST', '/auth/login', { body: { a: 1 } });

    expect(result).toEqual({ ok: true });
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe('/api/auth/login');
    expect(init?.body).toBe(JSON.stringify({ a: 1 }));
    const headers = init?.headers as Record<string, string>;
    expect(headers.Authorization).toBe('Bearer tok');
    expect(headers['Content-Type']).toBe('application/json');
  });

  it.each([
    [401, 'unauthorized', 'expired'],
    [403, 'forbidden', 'forbidden'],
  ] as const)('maps %i to "%s" and ends the session as "%s"', async (status, kind, reason) => {
    fetchMock.mockResolvedValue(jsonResponse(status, { detail: 'why' }));

    const error = await request('GET', '/audit/stats').catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).kind).toBe(kind);
    expect((error as ApiError).detail).toBe('why');
    expect(onSessionEnd).toHaveBeenCalledWith(reason);
  });

  it('does not end the session when notifySession is false', async () => {
    fetchMock.mockResolvedValue(jsonResponse(401, { detail: 'bad credentials' }));

    await request('POST', '/auth/login', { notifySession: false }).catch(() => undefined);

    expect(onSessionEnd).not.toHaveBeenCalled();
  });

  it('maps other statuses to "http"', async () => {
    fetchMock.mockResolvedValue(jsonResponse(500, {}));

    const error = await request('GET', '/x').catch((e: unknown) => e);

    expect((error as ApiError).kind).toBe('http');
    expect((error as ApiError).status).toBe(500);
  });

  it('maps a fetch failure to "network"', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));

    const error = await request('GET', '/x').catch((e: unknown) => e);

    expect((error as ApiError).kind).toBe('network');
  });

  it('maps an aborted request to "aborted"', async () => {
    const controller = new AbortController();
    fetchMock.mockImplementation(() => {
      controller.abort();
      return Promise.reject(new DOMException('aborted', 'AbortError'));
    });

    const error = await request('GET', '/x', { signal: controller.signal }).catch(
      (e: unknown) => e,
    );

    expect(isAborted(error)).toBe(true);
    expect(fetchMock.mock.calls[0]![1]?.signal).toBe(controller.signal);
  });

  it('does not end a newer session on a late 401 for an older token', async () => {
    let token = 'A';
    configureClient({ getToken: () => token, onSessionEnd });
    fetchMock.mockImplementation(() => {
      token = 'B';
      return Promise.resolve(jsonResponse(401, { detail: 'expired' }));
    });

    const error = await request('GET', '/audit/stats').catch((e: unknown) => e);

    expect((error as ApiError).kind).toBe('unauthorized');
    expect(onSessionEnd).not.toHaveBeenCalled();
  });

  it('maps an abort while reading a non-OK body to "aborted"', async () => {
    const controller = new AbortController();
    const response = jsonResponse(500, {});
    vi.spyOn(response, 'json').mockImplementation(() => {
      controller.abort();
      return Promise.reject(new DOMException('aborted', 'AbortError'));
    });
    fetchMock.mockResolvedValue(response);

    const error = await request('GET', '/x', { signal: controller.signal }).catch(
      (e: unknown) => e,
    );

    expect(isAborted(error)).toBe(true);
  });

  it('maps an abort while reading an OK body to "aborted"', async () => {
    const controller = new AbortController();
    const response = jsonResponse(200, {});
    vi.spyOn(response, 'json').mockImplementation(() => {
      controller.abort();
      return Promise.reject(new DOMException('aborted', 'AbortError'));
    });
    fetchMock.mockResolvedValue(response);

    const error = await request('GET', '/x', { signal: controller.signal }).catch(
      (e: unknown) => e,
    );

    expect(isAborted(error)).toBe(true);
  });

  it('sends no Content-Type without a body and no Authorization without a token', async () => {
    configureClient({ getToken: () => null, onSessionEnd });
    fetchMock.mockResolvedValue(jsonResponse(200, {}));

    await request('GET', '/x');

    const headers = fetchMock.mock.calls[0]![1]?.headers as Record<string, string>;
    expect(headers['Content-Type']).toBeUndefined();
    expect(headers.Authorization).toBeUndefined();
  });

  it('does not end the session on a 403 when notifySession is false', async () => {
    fetchMock.mockResolvedValue(jsonResponse(403, { detail: 'nope' }));

    await request('GET', '/x', { notifySession: false }).catch(() => undefined);

    expect(onSessionEnd).not.toHaveBeenCalled();
  });
});
