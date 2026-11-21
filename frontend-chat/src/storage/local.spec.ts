import { afterEach, describe, expect, it, vi } from 'vitest';
import { readJson, readString, removeKey, writeJson, writeString } from './local';

describe('storage/local', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('round-trips JSON values', () => {
    writeJson('k', { a: 1, b: ['x'] });
    expect(readJson<{ a: number; b: string[] }>('k')).toEqual({ a: 1, b: ['x'] });
  });

  it('returns null for a missing key', () => {
    expect(readJson('missing')).toBeNull();
    expect(readString('missing')).toBeNull();
  });

  it('returns null and warns on corrupt JSON', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    localStorage.setItem('k', '{not json');
    expect(readJson('k')).toBeNull();
    expect(warn).toHaveBeenCalledOnce();
  });

  it('swallows storage errors on write', () => {
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('quota');
    });
    expect(() => writeJson('k', 1)).not.toThrow();
    expect(() => writeString('k', 'v')).not.toThrow();
  });

  it('writes, reads and removes strings', () => {
    writeString('s', 'value');
    expect(readString('s')).toBe('value');
    removeKey('s');
    expect(readString('s')).toBeNull();
  });
});
