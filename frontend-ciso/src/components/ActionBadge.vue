<script setup lang="ts">
import { useI18n } from 'vue-i18n';
import type { AuditAction } from '@/api/audit';

defineProps<{ action: AuditAction }>();
const { t } = useI18n();

const BADGE_COLORS: Record<AuditAction, string> = {
  allowed: 'positive',
  blocked_prompt: 'negative',
  blocked_response: 'red-9',
  provider_error: 'grey-7',
};
</script>

<template>
  <q-badge :color="BADGE_COLORS[action]" :label="t(`actions.${action}`)" class="q-py-xs q-px-sm" />
</template>
