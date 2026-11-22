import type { ChartData } from 'chart.js';
import { AUDIT_ACTIONS, type AuditAction, type Bucket, type TimeseriesPoint } from '@/api/audit';
import { formatBucketLabel } from '@/time/ranges';
import { ACTION_COLORS } from './actionColors';

export function buildTrendData(
  points: readonly TimeseriesPoint[],
  bucket: Bucket,
  labelFor: (action: AuditAction) => string,
): ChartData<'bar', number[], string> {
  return {
    labels: points.map((point) => formatBucketLabel(point.start, bucket)),
    datasets: AUDIT_ACTIONS.map((action) => ({
      label: labelFor(action),
      data: points.map((point) => point.by_action[action]),
      backgroundColor: ACTION_COLORS[action],
      stack: 'actions',
    })),
  };
}
