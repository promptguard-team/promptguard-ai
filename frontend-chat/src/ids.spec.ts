import { afterEach, describe, expect, it, vi } from 'vitest';
import { newId } from './ids';

const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

describe('newId', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('returns a v4 UUID', () => {
    expect(newId()).toMatch(UUID_V4);
  });

  it('falls back to getRandomValues outside a secure context', () => {
    const real = globalThis.crypto;
    vi.stubGlobal('crypto', {
      getRandomValues: (array: Uint8Array) => real.getRandomValues(array),
    });
    const ids = new Set([newId(), newId(), newId()]);
    expect(ids.size).toBe(3);
    for (const id of ids) {
      expect(id).toMatch(UUID_V4);
    }
  });
});
