export type ApiErrorKind = 'unauthorized' | 'forbidden' | 'network' | 'http' | 'aborted';

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status?: number;
  readonly detail?: string;

  constructor(kind: ApiErrorKind, status?: number, detail?: string) {
    super(detail ?? kind);
    this.name = 'ApiError';
    this.kind = kind;
    this.status = status;
    this.detail = detail;
  }
}

export const API_BASE = '/api';

/** Why the session ended: the token expired (401) or the ciso role is gone (403). */
export type SessionEndReason = 'expired' | 'forbidden';

interface ClientConfig {
  getToken: () => string | null;
  onSessionEnd: (reason: SessionEndReason) => void;
}

export type QueryValue = string | number | boolean | readonly string[] | undefined;

export interface RequestOptions {
  body?: unknown;
  query?: Record<string, QueryValue>;
  signal?: AbortSignal;
  /** False for the login call, where 401 means bad credentials, not an ended session. */
  notifySession?: boolean;
}

let config: ClientConfig = {
  getToken: () => null,
  onSessionEnd: () => {},
};

export function configureClient(next: ClientConfig): void {
  config = next;
}

export function isAborted(error: unknown): boolean {
  return error instanceof ApiError && error.kind === 'aborted';
}

export function buildUrl(path: string, query: Record<string, QueryValue> = {}): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined) {
      continue;
    }
    if (typeof value === 'object') {
      value.forEach((item) => params.append(key, item));
    } else {
      params.append(key, String(value));
    }
  }
  const search = params.toString();
  return `${API_BASE}${path}${search ? `?${search}` : ''}`;
}

async function readDetail(response: Response): Promise<string | undefined> {
  try {
    const data: unknown = await response.json();
    if (typeof data === 'object' && data !== null && 'detail' in data) {
      const detail = (data as { detail: unknown }).detail;
      return typeof detail === 'string' ? detail : undefined;
    }
  } catch {
    // Non-JSON body: no detail.
  }
  return undefined;
}

export async function request<T>(
  method: 'GET' | 'POST',
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json';
  }
  const token = config.getToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(buildUrl(path, options.query), {
      method,
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: options.signal,
    });
  } catch (error) {
    if (options.signal?.aborted) {
      throw new ApiError('aborted');
    }
    throw new ApiError('network', undefined, error instanceof Error ? error.message : undefined);
  }

  if (response.ok) {
    try {
      return (await response.json()) as T;
    } catch {
      if (options.signal?.aborted) {
        throw new ApiError('aborted');
      }
      throw new ApiError('http', response.status, 'invalid JSON response');
    }
  }

  const detail = await readDetail(response);
  if (options.signal?.aborted && response.status !== 401 && response.status !== 403) {
    throw new ApiError('aborted');
  }
  // A late response for an older token must not end a newer session.
  const notify = options.notifySession !== false && token !== null && config.getToken() === token;
  switch (response.status) {
    case 401:
      if (notify) {
        config.onSessionEnd('expired');
      }
      throw new ApiError('unauthorized', 401, detail);
    case 403:
      // Any 403 ends the session by default: every 403 the gateway returns to this app means
      // the ciso role is gone. Pass notifySession: false where 403 means something else.
      if (notify) {
        config.onSessionEnd('forbidden');
      }
      throw new ApiError('forbidden', 403, detail);
    default:
      throw new ApiError('http', response.status, detail);
  }
}
