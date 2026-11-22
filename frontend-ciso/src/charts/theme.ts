export interface ChartTheme {
  text: string;
  grid: string;
}

/** Axis and legend colours that stay legible on either page background. */
export function chartTheme(dark: boolean): ChartTheme {
  return dark
    ? { text: '#cbd5e1', grid: 'rgba(148, 163, 184, 0.2)' }
    : { text: '#475569', grid: 'rgba(100, 116, 139, 0.2)' };
}
