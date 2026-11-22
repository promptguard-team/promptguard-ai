import { describe, expect, it } from 'vitest';
import { effectScope } from 'vue';
import { ApiError } from '@/api/client';
import { useRequest } from './useRequest';

interface Pending<T> {
  signal: AbortSignal;
  resolve: (value: T) => void;
  reject: (error: unknown) => void;
}

function controllable<T>() {
  const calls: Pending<T>[] = [];
  const load = (signal: AbortSignal) =>
    new Promise<T>((resolve, reject) => calls.push({ signal, resolve, reject }));
  return { calls, load };
}

function inScope<T>(fn: () => T): T {
  return effectScope().run(fn)!;
}

describe('useRequest', () => {
  it('tracks loading and stores data', async () => {
    const { calls, load } = controllable<number>();
    const state = inScope(() => useRequest(load));

    const done = state.run();
    expect(state.loading).toBe(true);
    calls[0]!.resolve(42);
    await done;

    expect(state.data).toBe(42);
    expect(state.loading).toBe(false);
    expect(state.error).toBeNull();
  });

  it('aborts the previous run and ignores its late result', async () => {
    const { calls, load } = controllable<string>();
    const state = inScope(() => useRequest(load));

    const first = state.run();
    const second = state.run();
    expect(calls[0]!.signal.aborted).toBe(true);

    calls[1]!.resolve('new');
    await second;
    calls[0]!.resolve('old');
    await first;

    expect(state.data).toBe('new');
    expect(state.loading).toBe(false);
  });

  it('stores errors but ignores aborts', async () => {
    const { calls, load } = controllable<string>();
    const state = inScope(() => useRequest(load));

    const failing = state.run();
    calls[0]!.reject(new ApiError('http', 500));
    await failing;
    expect(state.error?.kind).toBe('http');

    const aborted = state.run();
    expect(state.error).toBeNull();
    calls[1]!.reject(new ApiError('aborted'));
    state.cancel();
    await aborted;
    expect(state.error).toBeNull();
    expect(state.loading).toBe(false);
  });

  it('aborts when its scope is disposed', () => {
    const { calls, load } = controllable<string>();
    const scope = effectScope();
    const state = scope.run(() => useRequest(load))!;

    void state.run();
    scope.stop();

    expect(calls[0]!.signal.aborted).toBe(true);
  });
});
