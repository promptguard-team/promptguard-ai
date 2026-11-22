<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';
import { BLOCKED_ACTIONS } from '@/api/audit';
import ErrorBanner from '@/components/ErrorBanner.vue';
import RangeSelect from '@/components/RangeSelect.vue';
import { EMPTY_VALUE, formatShare } from '@/format';
import { DEFAULT_PRESET, isRangePreset, type RangePreset } from '@/time/ranges';
import { defaultEventFilters, toEventQuery } from '@/features/events/eventQuery';
import ActionDonut from './ActionDonut.vue';
import KpiTile from './KpiTile.vue';
import RecentBlocks from './RecentBlocks.vue';
import TrendChart from './TrendChart.vue';
import { useDashboard } from './useDashboard';

const { t } = useI18n();
const route = useRoute();
const router = useRouter();

// The range lives in the URL so the view survives reloads and can be shared.
const preset = computed<RangePreset>({
  get: () => {
    const raw = route.query.range;
    return isRangePreset(raw) ? raw : DEFAULT_PRESET;
  },
  set: (value) => {
    // Range changes replace the history entry (Back skips them), unlike event filters.
    void router.replace({ query: { ...route.query, range: value } });
  },
});

const { stats, trend, recent, refresh } = useDashboard(preset);

// A failed refresh keeps the previous data; hide it so stale numbers are not shown as current.
const statsData = computed(() => (stats.error ? null : stats.data));
const total = computed(() => statsData.value?.total ?? null);
const blocked = computed(() =>
  statsData.value
    ? statsData.value.by_action.blocked_prompt + statsData.value.by_action.blocked_response
    : null,
);

function shareText(part: number | null): string | undefined {
  if (part === null || total.value === null) {
    return undefined;
  }
  const share = formatShare(part, total.value);
  // Spec: the share reads "—" when there were no requests at all.
  return share === null ? EMPTY_VALUE : t('dashboard.shareOfTotal', { share });
}

const seeAllLink = computed(() => ({
  path: '/events',
  query: toEventQuery({
    ...defaultEventFilters(),
    range: preset.value,
    actions: [...BLOCKED_ACTIONS],
  }),
}));
</script>

<template>
  <q-page padding>
    <div class="row items-center q-mb-md q-gutter-sm">
      <RangeSelect v-model="preset" />
      <q-space />
      <q-btn
        flat
        no-caps
        icon="refresh"
        data-test="refresh"
        :label="t('dashboard.refresh')"
        @click="refresh"
      />
    </div>

    <ErrorBanner v-if="stats.error" class="q-mb-md" @retry="stats.run" />
    <div class="row q-col-gutter-md q-mb-md">
      <div class="col-12 col-sm-6 col-lg-3">
        <KpiTile
          :label="t('dashboard.kpi.total')"
          :value="total"
          icon="swap_vert"
          color="primary"
          :loading="stats.loading"
        />
      </div>
      <div class="col-12 col-sm-6 col-lg-3">
        <KpiTile
          :label="t('dashboard.kpi.blocked')"
          :value="blocked"
          :share="shareText(blocked)"
          icon="block"
          color="negative"
          :loading="stats.loading"
        />
      </div>
      <div class="col-12 col-sm-6 col-lg-3">
        <KpiTile
          :label="t('dashboard.kpi.flagged')"
          :value="statsData?.flagged ?? null"
          icon="flag"
          color="warning"
          :loading="stats.loading"
        />
      </div>
      <div class="col-12 col-sm-6 col-lg-3">
        <KpiTile
          :label="t('dashboard.kpi.mlUnavailable')"
          :value="statsData?.ml_unavailable ?? null"
          :share="shareText(statsData?.ml_unavailable ?? null)"
          icon="cloud_off"
          color="grey-7"
          :loading="stats.loading"
        />
      </div>
    </div>

    <div class="row q-col-gutter-md q-mb-md">
      <div class="col-12 col-lg-8">
        <q-card flat bordered>
          <q-card-section class="text-subtitle1">{{ t('dashboard.trend') }}</q-card-section>
          <q-card-section>
            <ErrorBanner v-if="trend.error" @retry="trend.run" />
            <TrendChart v-else-if="trend.data" :series="trend.data" />
            <q-skeleton v-else height="280px" />
          </q-card-section>
        </q-card>
      </div>
      <div class="col-12 col-lg-4">
        <q-card flat bordered>
          <q-card-section class="text-subtitle1">{{ t('dashboard.distribution') }}</q-card-section>
          <q-card-section>
            <ErrorBanner v-if="stats.error" @retry="stats.run" />
            <ActionDonut v-else-if="stats.data" :counts="stats.data.by_action" />
            <q-skeleton v-else height="280px" />
          </q-card-section>
        </q-card>
      </div>
    </div>

    <q-card flat bordered>
      <q-card-section class="row items-center">
        <div class="text-subtitle1">{{ t('dashboard.recentBlocks') }}</div>
        <q-space />
        <q-btn
          flat
          dense
          no-caps
          color="primary"
          data-test="see-all"
          :to="seeAllLink"
          :label="t('dashboard.seeAll')"
        />
      </q-card-section>
      <q-card-section class="q-pt-none">
        <ErrorBanner v-if="recent.error" @retry="recent.run" />
        <RecentBlocks v-else-if="recent.data" :items="recent.data.items" />
        <q-skeleton v-else height="120px" />
      </q-card-section>
    </q-card>
  </q-page>
</template>
