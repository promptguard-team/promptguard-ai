import { Dark } from 'quasar';
import { readString, writeString } from '@/storage/local';

const THEME_KEY = 'promptguard.ui.theme';

export function applyStoredTheme(): void {
  Dark.set(readString(THEME_KEY) !== 'light');
}

export function toggleTheme(): void {
  const next = Dark.isActive ? 'light' : 'dark';
  Dark.set(next === 'dark');
  writeString(THEME_KEY, next);
}
