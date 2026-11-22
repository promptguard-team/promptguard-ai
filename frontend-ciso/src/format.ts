export const EMPTY_VALUE = '—';

const countFormatter = new Intl.NumberFormat('pl-PL');
const shareFormatter = new Intl.NumberFormat('pl-PL', {
  style: 'percent',
  maximumFractionDigits: 1,
});

export function formatCount(value: number): string {
  return countFormatter.format(value);
}

/** `part` as a percentage of `total`; null when there is nothing to divide by. */
export function formatShare(part: number, total: number): string | null {
  return total > 0 ? shareFormatter.format(part / total) : null;
}

export function formatScore(value: number | null): string {
  return value === null ? EMPTY_VALUE : value.toFixed(2);
}

export function orEmpty(value: string | null): string {
  return value ?? EMPTY_VALUE;
}
