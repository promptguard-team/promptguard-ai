import { shallowRef, watch, type Ref } from 'vue';
import { BLOCKED_ACTIONS, getStats, getTimeseries, listEvents } from '@/api/audit';
import { useRequest } from '@/composables/useRequest';
import { presetRange, type RangePreset } from '@/time/ranges';

export const RECENT_LIMIT = 5;

/** Loads the three dashboard cards independently, so one failure never blanks the page. */
export function useDashboard(preset: Ref<RangePreset>) {
  const range = shallowRef(presetRange(preset.value));

  const stats = useRequest((signal) => getStats(range.value, signal));
  const trend = useRequest((signal) => getTimeseries(range.value, range.value.bucket, signal));
  const recent = useRequest((signal) =>
    listEvents(
      { range: range.value, actions: BLOCKED_ACTIONS, limit: RECENT_LIMIT, offset: 0 },
      signal,
    ),
  );

  /** Recomputes "now" and reloads every card. */
  function refresh(): void {
    range.value = presetRange(preset.value);
    void stats.run();
    void trend.run();
    void recent.run();
  }

  watch(preset, refresh, { immediate: true });

  return { range, stats, trend, recent, refresh };
}
