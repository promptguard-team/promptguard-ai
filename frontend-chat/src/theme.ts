import { Dark } from 'quasar';
import { readString, writeString } from '@/storage/local';

const THEME_KEY = 'promptguard.ui.theme';

type Theme = 'dark' | 'light';

// index.html sets the same attribute before the bundle loads, so the page
// background never flashes the wrong colour.
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
