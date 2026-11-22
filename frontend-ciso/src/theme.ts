import { Dark } from 'quasar';
import { readString, writeString } from '@/storage/local';

// index.html reads the same key before the bundle loads, to avoid a background flash.
export const THEME_KEY = 'promptguard.ciso.theme';

type Theme = 'dark' | 'light';

function setTheme(theme: Theme): void {
  Dark.set(theme === 'dark');
  document.documentElement.dataset.theme = theme;
}

export function applyStoredTheme(): void {
  setTheme(readString(THEME_KEY) === 'light' ? 'light' : 'dark');
}

export function toggleTheme(): void {
  const next: Theme = Dark.isActive ? 'light' : 'dark';
  setTheme(next);
  writeString(THEME_KEY, next);
}
