import { computed, watch, type Ref } from 'vue';
import { listEvents } from '@/api/audit';
import { useRequest } from '@/composables/useRequest';
import { eventListParams, toEventQuery, type EventFilters } from './eventQuery';

/** Event page for the current filters; reloads (aborting the old request) when they change. */
export function useEvents(filters: Ref<EventFilters>) {
  const events = useRequest((signal) => listEvents(eventListParams(filters.value), signal));
  // Watch a normalised key, not the object: equal-but-new filters must not refetch, and the
  // email only labels the user chip, so it does not affect the request.
  const requestKey = computed(() => {
    const query = toEventQuery(filters.value);
    delete query.email;
    return JSON.stringify(query);
  });
  watch(requestKey, () => void events.run(), { immediate: true });
  return events;
}
