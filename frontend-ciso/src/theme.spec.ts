import { describe, expect, it } from 'vitest';
import { Dark } from 'quasar';
import { applyStoredTheme, THEME_KEY, toggleTheme } from './theme';

describe('theme', () => {
  it('defaults to dark and persists toggles', () => {
    applyStoredTheme();
    expect(Dark.isActive).toBe(true);
    expect(document.documentElement.dataset.theme).toBe('dark');

    toggleTheme();

    expect(Dark.isActive).toBe(false);
    expect(document.documentElement.dataset.theme).toBe('light');
    expect(localStorage.getItem(THEME_KEY)).toBe('light');
  });

  it('applies a stored light theme', () => {
    localStorage.setItem(THEME_KEY, 'light');
    applyStoredTheme();
    expect(Dark.isActive).toBe(false);
  });
});
