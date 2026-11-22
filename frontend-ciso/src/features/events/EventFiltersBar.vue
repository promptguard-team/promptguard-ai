<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { AUDIT_ACTIONS, ML_STATUSES, type AuditAction, type MlStatus } from '@/api/audit';
import { dayRange, RANGE_PRESETS, startOfWarsawDay, warsawDay } from '@/time/ranges';
import type { EventFilters, EventRange } from './eventQuery';

const props = defineProps<{ filters: EventFilters }>();
const emit = defineEmits<{ change: [patch: Partial<EventFilters>] }>();
const { t } = useI18n();

type FlaggedChoice = 'all' | 'true' | 'false';
type MlChoice = MlStatus | 'all';

const rangeOptions = computed(() => [
  ...RANGE_PRESETS.map((preset) => ({ label: t(`ranges.${preset}`), value: preset })),
  { label: t('ranges.custom'), value: 'custom' },
]);
const actionOptions = computed(() =>
  AUDIT_ACTIONS.map((action) => ({ label: t(`actions.${action}`), value: action })),
);
const flaggedOptions = computed(() => [
  { label: t('events.filters.all'), value: 'all' },
  { label: t('events.filters.yes'), value: 'true' },
  { label: t('events.filters.no'), value: 'false' },
]);
const mlOptions = computed(() => [
  { label: t('events.filters.all'), value: 'all' },
  ...ML_STATUSES.map((status) => ({ label: t(`mlStatus.${status}`), value: status })),
]);

const flaggedChoice = computed<FlaggedChoice>(() =>
  props.filters.flagged === null ? 'all' : props.filters.flagged ? 'true' : 'false',
);

// Date inputs edit drafts; only a valid range reaches the URL.
const fromDraft = ref(props.filters.fromDay ?? '');
const toDraft = ref(props.filters.toDay ?? '');
watch(
  () => [props.filters.fromDay, props.filters.toDay] as const,
  ([fromDay, toDay]) => {
    fromDraft.value = fromDay ?? '';
    toDraft.value = toDay ?? '';
  },
);
const draftInvalid = computed(() => dayRange(fromDraft.value, toDraft.value) === null);

function setRange(value: EventRange): void {
  if (value === 'custom') {
    const now = new Date();
    emit('change', {
      range: 'custom',
      fromDay: warsawDay(startOfWarsawDay(now, 6)),
      toDay: warsawDay(now),
    });
  } else {
    emit('change', { range: value, fromDay: null, toDay: null });
  }
}

function setDraft(which: 'from' | 'to', value: string | number | null): void {
  const text = value === null ? '' : String(value);
  if (which === 'from') {
    fromDraft.value = text;
  } else {
    toDraft.value = text;
  }
  if (!draftInvalid.value) {
    emit('change', { range: 'custom', fromDay: fromDraft.value, toDay: toDraft.value });
  }
}

function setActions(value: AuditAction[] | null): void {
  emit('change', { actions: value ?? [] });
}

function setFlagged(value: FlaggedChoice): void {
  emit('change', { flagged: value === 'all' ? null : value === 'true' });
}

function setMlStatus(value: MlChoice): void {
  emit('change', { mlStatus: value === 'all' ? null : value });
}
</script>

<template>
  <div class="row q-col-gutter-md items-start">
    <div class="col-12">
      <q-btn-toggle
        :model-value="filters.range"
        :options="rangeOptions"
        no-caps
        unelevated
        dense
        toggle-color="primary"
        @update:model-value="setRange"
      />
    </div>
    <template v-if="filters.range === 'custom'">
      <div class="col-6 col-md-3">
        <q-input
          type="date"
          dense
          outlined
          :label="t('events.filters.from')"
          :model-value="fromDraft"
          :error="draftInvalid"
          :error-message="t('events.filters.invalidRange')"
          @update:model-value="(v) => setDraft('from', v)"
        />
      </div>
      <div class="col-6 col-md-3">
        <q-input
          type="date"
          dense
          outlined
          :label="t('events.filters.to')"
          :model-value="toDraft"
          :error="draftInvalid"
          @update:model-value="(v) => setDraft('to', v)"
        />
      </div>
    </template>
    <div class="col-12 col-md-4">
      <q-select
        multiple
        clearable
        use-chips
        emit-value
        map-options
        dense
        outlined
        :label="t('events.filters.action')"
        :options="actionOptions"
        :model-value="filters.actions"
        @update:model-value="setActions"
      />
    </div>
    <div class="col-6 col-md-2">
      <q-select
        emit-value
        map-options
        dense
        outlined
        :label="t('events.filters.flagged')"
        :options="flaggedOptions"
        :model-value="flaggedChoice"
        @update:model-value="setFlagged"
      />
    </div>
    <div class="col-6 col-md-2">
      <q-select
        emit-value
        map-options
        dense
        outlined
        :label="t('events.filters.mlStatus')"
        :options="mlOptions"
        :model-value="filters.mlStatus ?? 'all'"
        @update:model-value="setMlStatus"
      />
    </div>
    <div v-if="filters.userId" class="col-12">
      <q-chip
        removable
        icon="person"
        :remove-aria-label="t('events.filters.clearUser')"
        @remove="emit('change', { userId: null, userEmail: null })"
        >{{ filters.userEmail ?? filters.userId }}</q-chip
      >
    </div>
  </div>
</template>
