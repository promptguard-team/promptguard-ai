<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { useQuasar } from 'quasar';
import { Doughnut } from 'vue-chartjs';
import type { ChartData, ChartOptions } from 'chart.js';
import { AUDIT_ACTIONS, type ActionCounts } from '@/api/audit';
import '@/charts/register';
import { chartTheme } from '@/charts/theme';
import { ACTION_COLORS } from './actionColors';

const props = defineProps<{ counts: ActionCounts }>();
const { t } = useI18n();
const $q = useQuasar();

const total = computed(() => AUDIT_ACTIONS.reduce((sum, action) => sum + props.counts[action], 0));

const data = computed<ChartData<'doughnut', number[], string>>(() => ({
  labels: AUDIT_ACTIONS.map((action) => t(`actions.${action}`)),
  datasets: [
    {
      data: AUDIT_ACTIONS.map((action) => props.counts[action]),
      backgroundColor: AUDIT_ACTIONS.map((action) => ACTION_COLORS[action]),
      borderWidth: 0,
    },
  ],
}));

const options = computed<ChartOptions<'doughnut'>>(() => ({
  responsive: true,
  maintainAspectRatio: false,
  cutout: '65%',
  plugins: {
    legend: { position: 'bottom', labels: { color: chartTheme($q.dark.isActive).text } },
  },
}));
</script>

<template>
  <div v-if="total === 0" class="text-grey-6 text-body2 q-pa-md" data-test="donut-empty">
    {{ t('dashboard.noEvents') }}
  </div>
  <div v-else class="chart-box">
    <Doughnut :data="data" :options="options" />
  </div>
</template>
