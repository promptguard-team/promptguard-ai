import { describe, expect, it } from 'vitest';
import type { TimeseriesPoint } from '@/api/audit';
import { ACTION_COLORS } from './actionColors';
import { buildTrendData } from './trendData';

const points: TimeseriesPoint[] = [
  {
    start: '2026-11-19T00:00:00+01:00',
    by_action: { allowed: 5, blocked_prompt: 2, blocked_response: 0, provider_error: 1 },
  },
  {
    start: '2026-11-20T00:00:00+01:00',
    by_action: { allowed: 3, blocked_prompt: 0, blocked_response: 1, provider_error: 0 },
  },
];

describe('buildTrendData', () => {
  it('builds one stacked dataset per action with Warsaw labels', () => {
    const data = buildTrendData(points, 'day', (action) => `L:${action}`);

    expect(data.labels).toEqual(['19.11', '20.11']);
    expect(data.datasets.map((d) => d.label)).toEqual([
      'L:allowed',
      'L:blocked_prompt',
      'L:blocked_response',
      'L:provider_error',
    ]);
    expect(data.datasets[1]).toMatchObject({
      data: [2, 0],
      backgroundColor: ACTION_COLORS.blocked_prompt,
      stack: 'actions',
    });
  });
});
