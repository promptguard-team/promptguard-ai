<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { RANGE_PRESETS, type RangePreset } from '@/time/ranges';

const model = defineModel<RangePreset>({ required: true });
const { t } = useI18n();
const options = computed(() =>
  RANGE_PRESETS.map((preset) => ({ label: t(`ranges.${preset}`), value: preset })),
);
</script>

<template>
  <q-btn-toggle
    v-model="model"
    :aria-label="t('common.range')"
    :options="options"
    no-caps
    unelevated
    dense
    toggle-color="primary"
  />
</template>
