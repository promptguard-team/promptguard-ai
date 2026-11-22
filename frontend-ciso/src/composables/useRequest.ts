import { getCurrentScope, onScopeDispose, reactive, ref, shallowRef } from 'vue';
import { ApiError, isAborted } from '@/api/client';

export interface RequestState<T> {
  readonly data: T | null;
  readonly loading: boolean;
  readonly error: ApiError | null;
  run: () => Promise<void>;
  cancel: () => void;
}

/**
 * Runs `load` on demand. A new run aborts the previous one, so a stale response
 * can never overwrite a newer one. Aborts are not errors.
 */
export function useRequest<T>(load: (signal: AbortSignal) => Promise<T>): RequestState<T> {
  const data = shallowRef<T | null>(null);
  const loading = ref(false);
  const error = shallowRef<ApiError | null>(null);
  let controller: AbortController | null = null;

  async function run(): Promise<void> {
    controller?.abort();
    const current = new AbortController();
    controller = current;
    loading.value = true;
    error.value = null;
    try {
      const result = await load(current.signal);
      if (controller === current) {
        data.value = result;
      }
    } catch (e) {
      if (controller !== current || isAborted(e)) {
        return;
      }
      if (!(e instanceof ApiError)) {
        // Surface programming errors; the UI only shows the wrapped message.
        console.error('request failed', e);
      }
      error.value = e instanceof ApiError ? e : new ApiError('http', undefined, String(e));
    } finally {
      if (controller === current) {
        controller = null;
        loading.value = false;
      }
    }
  }

  function cancel(): void {
    controller?.abort();
    controller = null;
    loading.value = false;
  }

  if (getCurrentScope()) {
    onScopeDispose(cancel);
  }

  // reactive() unwraps the refs; TypeScript cannot follow that through the generic.
  return reactive({ data, loading, error, run, cancel }) as unknown as RequestState<T>;
}
