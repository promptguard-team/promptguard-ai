export type ApiErrorKind = 'unauthorized' | 'forbidden' | 'provider' | 'network' | 'http';

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

type HttpMethod = 'GET' | 'POST';

interface ClientConfig {
  getToken: () => string | null;
  onUnauthorized: () => void;
}

interface RequestOptions {
  /** Set to false for the login call, where 401 means bad credentials, not an expired session. */
  notifyUnauthorized?: boolean;
}

let config: ClientConfig = {
  getToken: () => null,
  onUnauthorized: () => {},
};

export function configureClient(next: ClientConfig): void {
  config = next;
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
  method: HttpMethod,
  path: string,
  body?: unknown,
  options: RequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
  }
  const token = config.getToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (error) {
    throw new ApiError('network', undefined, error instanceof Error ? error.message : undefined);
  }

  if (response.ok) {
    return (await response.json()) as T;
  }

  const detail = await readDetail(response);
  switch (response.status) {
    case 401:
      if (options.notifyUnauthorized !== false) {
        config.onUnauthorized();
      }
      throw new ApiError('unauthorized', 401, detail);
    case 403:
      throw new ApiError('forbidden', 403, detail);
    case 502:
      throw new ApiError('provider', 502, detail);
    default:
      throw new ApiError('http', response.status, detail);
  }
}
