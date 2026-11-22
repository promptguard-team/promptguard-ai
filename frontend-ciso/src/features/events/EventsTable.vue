<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import type { QTableColumn } from 'quasar';
import type { AuditEventPage, AuditEventSummary, MlStatus } from '@/api/audit';
import ActionBadge from '@/components/ActionBadge.vue';
import { EMPTY_VALUE, formatScore, orEmpty } from '@/format';
import { formatDateTime } from '@/time/ranges';
import { PAGE_SIZES, type EventFilters, type PageSize } from './eventQuery';

const props = defineProps<{
  page: AuditEventPage | null;
  loading: boolean;
  filters: EventFilters;
}>();
const emit = defineEmits<{
  paginate: [page: number, pageSize: PageSize];
  filterUser: [userId: string, email: string];
}>();
const { t } = useI18n();

const columns = computed<QTableColumn<AuditEventSummary>[]>(() => [
  {
    name: 'created_at',
    label: t('events.columns.time'),
    field: 'created_at',
    align: 'left',
    format: (value: string) => formatDateTime(value),
  },
  { name: 'user_email', label: t('events.columns.user'), field: 'user_email', align: 'left' },
  { name: 'action', label: t('events.columns.action'), field: 'action', align: 'left' },
  { name: 'rule', label: t('events.columns.rule'), field: 'rule', align: 'left', format: orEmpty },
  {
    name: 'ml_status',
    label: t('events.columns.mlStatus'),
    field: 'ml_status',
    align: 'left',
    format: (value: MlStatus) => t(`mlStatus.${value}`),
  },
  {
    name: 'ml_score',
    label: t('events.columns.mlScore'),
    field: 'ml_score',
    align: 'right',
    format: formatScore,
  },
  {
    name: 'ml_label',
    label: t('events.columns.mlLabel'),
    field: 'ml_label',
    align: 'left',
    format: orEmpty,
  },
  {
    name: 'ml_model_version',
    label: t('events.columns.modelVersion'),
    field: 'ml_model_version',
    align: 'left',
    format: orEmpty,
  },
  { name: 'flagged', label: t('events.columns.flagged'), field: 'flagged', align: 'center' },
]);

// Server-side pagination: QTable only reports the requested page; the URL holds the state.
const pagination = computed(() => ({
  page: props.filters.page,
  rowsPerPage: props.filters.pageSize,
  rowsNumber: props.page?.total ?? 0,
}));

function onRequest(request: { pagination: { page: number; rowsPerPage: number } }): void {
  const size: PageSize = request.pagination.rowsPerPage === 50 ? 50 : 25;
  emit('paginate', request.pagination.page, size);
}

function paginationLabel(first: number, last: number, total: number): string {
  return t('events.pagination', { first, last, total });
}
</script>

<template>
  <q-table
    flat
    bordered
    row-key="id"
    :rows="page?.items ?? []"
    :columns="columns"
    :loading="loading"
    :pagination="pagination"
    :rows-per-page-options="[...PAGE_SIZES]"
    :rows-per-page-label="t('events.rowsPerPage')"
    :pagination-label="paginationLabel"
    :no-data-label="t('events.empty')"
    @request="onRequest"
  >
    <template #body-cell-user_email="cell">
      <q-td :props="cell">
        <q-btn
          flat
          dense
          no-caps
          class="q-px-xs"
          data-test="user-link"
          :label="cell.value"
          :aria-label="t('events.filterByUser', { email: cell.value })"
          @click="emit('filterUser', cell.row.user_id, cell.row.user_email)"
        />
      </q-td>
    </template>
    <template #body-cell-action="cell">
      <q-td :props="cell">
        <ActionBadge :action="cell.row.action" />
      </q-td>
    </template>
    <template #body-cell-flagged="cell">
      <q-td :props="cell">
        <q-icon
          v-if="cell.row.flagged"
          name="flag"
          color="warning"
          size="sm"
          data-test="flagged-icon"
          :aria-label="t('events.flagged')"
        />
        <span v-else>{{ EMPTY_VALUE }}</span>
      </q-td>
    </template>
  </q-table>
</template>
