<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { useQuasar } from 'quasar';
import { Bar } from 'vue-chartjs';
import type { ChartOptions } from 'chart.js';
import type { AuditTimeseries } from '@/api/audit';
import '@/charts/register';
import { chartTheme } from '@/charts/theme';
import { buildTrendData } from './trendData';

const props = defineProps<{ series: AuditTimeseries }>();
const { t } = useI18n();
const $q = useQuasar();

const data = computed(() =>
  buildTrendData(props.series.points, props.series.bucket, (action) => t(`actions.${action}`)),
);

const options = computed<ChartOptions<'bar'>>(() => {
  const theme = chartTheme($q.dark.isActive);
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { position: 'bottom', labels: { color: theme.text } } },
    scales: {
      x: { stacked: true, ticks: { color: theme.text }, grid: { display: false } },
      y: {
        stacked: true,
        beginAtZero: true,
        ticks: { color: theme.text, precision: 0 },
        grid: { color: theme.grid },
      },
    },
  };
});
</script>

<template>
  <div class="chart-box">
    <Bar :data="data" :options="options" />
  </div>
</template>
