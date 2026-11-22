import { afterEach, describe, expect, it, vi } from 'vitest';
import { readString, removeKey, writeString } from './local';

describe('storage/local', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it('round-trips a value and removes it', () => {
    writeString('k', 'v');
    expect(readString('k')).toBe('v');

    removeKey('k');
    expect(readString('k')).toBeNull();
  });

  it('swallows storage errors and warns', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const denied = (): never => {
      throw new Error('denied');
    };
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(denied);
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(denied);
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(denied);

    expect(readString('k')).toBeNull();
    expect(() => writeString('k', 'v')).not.toThrow();
    expect(() => removeKey('k')).not.toThrow();
    expect(warn).toHaveBeenCalledTimes(3);
  });
});
