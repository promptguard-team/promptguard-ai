// localStorage can throw (private mode, quota, disabled storage). Every call is
// guarded so persistence failures never break the UI.

function warn(action: string, key: string, error: unknown): void {
  console.warn(`localStorage ${action} failed for "${key}"`, error);
}

export function readString(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch (error) {
    warn('read', key, error);
    return null;
  }
}

export function writeString(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch (error) {
    warn('write', key, error);
  }
}

export function removeKey(key: string): void {
  try {
    localStorage.removeItem(key);
  } catch (error) {
    warn('remove', key, error);
  }
}
