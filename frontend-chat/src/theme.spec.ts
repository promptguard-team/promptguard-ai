import { beforeEach, describe, expect, it } from 'vitest';
import { Dark } from 'quasar';
import { applyStoredTheme, toggleTheme } from '@/theme';

const THEME_KEY = 'promptguard.ui.theme';

describe('theme', () => {
  beforeEach(() => {
    localStorage.clear();
    Dark.set(true);
  });

  it('defaults to dark when nothing is stored', () => {
    Dark.set(false);
    applyStoredTheme();
    expect(Dark.isActive).toBe(true);
  });

  it('is light when light is stored', () => {
    localStorage.setItem(THEME_KEY, 'light');
    applyStoredTheme();
    expect(Dark.isActive).toBe(false);
  });

  it('toggles the mode and persists the choice', () => {
    toggleTheme();
    expect(Dark.isActive).toBe(false);
    expect(localStorage.getItem(THEME_KEY)).toBe('light');
    toggleTheme();
    expect(Dark.isActive).toBe(true);
    expect(localStorage.getItem(THEME_KEY)).toBe('dark');
  });
});
