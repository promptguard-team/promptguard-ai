<script setup lang="ts">
import { useI18n } from 'vue-i18n';

const emit = defineEmits<{ retry: [] }>();
const { t } = useI18n();
</script>

<template>
  <q-banner rounded dense role="alert" class="error-banner text-negative">
    <template #avatar>
      <q-icon name="error_outline" color="negative" />
    </template>
    {{ t('common.loadError') }}
    <template #action>
      <q-btn
        flat
        dense
        no-caps
        color="negative"
        data-test="retry"
        :label="t('common.retry')"
        @click="emit('retry')"
      />
    </template>
  </q-banner>
</template>
