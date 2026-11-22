import { watch, type Ref } from 'vue';
import { listEvents } from '@/api/audit';
import { useRequest } from '@/composables/useRequest';
import { eventListParams, type EventFilters } from './eventQuery';

/** Event page for the current filters; reloads (aborting the old request) when they change. */
export function useEvents(filters: Ref<EventFilters>) {
  const events = useRequest((signal) => listEvents(eventListParams(filters.value), signal));
  watch(filters, () => void events.run(), { immediate: true });
  return events;
}
