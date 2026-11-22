<script setup lang="ts">
import { EMPTY_VALUE, formatCount } from '@/format';

defineProps<{
  label: string;
  value: number | null;
  /** Pre-formatted secondary line, e.g. "25% wszystkich". */
  share?: string;
  icon: string;
  color: string;
  loading: boolean;
}>();
</script>

<template>
  <q-card flat bordered>
    <q-card-section class="row items-center no-wrap">
      <div class="col">
        <div class="text-caption text-grey-6">{{ label }}</div>
        <q-skeleton v-if="loading" type="text" width="72px" class="text-h5" />
        <template v-else>
          <div class="text-h5 text-weight-medium" data-test="kpi-value">
            {{ value === null ? EMPTY_VALUE : formatCount(value) }}
          </div>
          <div v-if="share" class="text-caption text-grey-6" data-test="kpi-share">{{ share }}</div>
        </template>
      </div>
      <q-avatar :color="color" text-color="white" :icon="icon" size="44px" rounded />
    </q-card-section>
  </q-card>
</template>
