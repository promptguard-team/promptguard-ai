<script setup lang="ts">
import { computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import ErrorBanner from '@/components/ErrorBanner.vue';
import { parseEventQuery, toEventQuery, type EventFilters, type PageSize } from './eventQuery';
import EventFiltersBar from './EventFiltersBar.vue';
import EventsTable from './EventsTable.vue';
import { useEvents } from './useEvents';

const route = useRoute();
const router = useRouter();

// The URL is the single source of truth: links are shareable and Back undoes a filter.
const filters = computed(() => parseEventQuery(route.query));
const events = useEvents(filters);

function navigate(next: EventFilters): void {
  void router.push({ query: toEventQuery(next) });
}

function onFilterChange(patch: Partial<EventFilters>): void {
  navigate({ ...filters.value, ...patch, page: 1 });
}

function onPaginate(page: number, pageSize: PageSize): void {
  const sizeChanged = pageSize !== filters.value.pageSize;
  navigate({ ...filters.value, page: sizeChanged ? 1 : page, pageSize });
}

function onFilterUser(userId: string, userEmail: string): void {
  onFilterChange({ userId, userEmail });
}
</script>

<template>
  <q-page padding>
    <q-card flat bordered class="q-mb-md">
      <q-card-section>
        <EventFiltersBar :filters="filters" @change="onFilterChange" />
      </q-card-section>
    </q-card>
    <ErrorBanner v-if="events.error" class="q-mb-md" @retry="events.run" />
    <EventsTable
      :page="events.data"
      :loading="events.loading"
      :filters="filters"
      @paginate="onPaginate"
      @filter-user="onFilterUser"
    />
  </q-page>
</template>
