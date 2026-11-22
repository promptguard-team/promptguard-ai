<script setup lang="ts">
import { useI18n } from 'vue-i18n';
import type { AuditEventSummary } from '@/api/audit';
import ActionBadge from '@/components/ActionBadge.vue';
import { orEmpty } from '@/format';
import { formatDateTime } from '@/time/ranges';

defineProps<{ items: readonly AuditEventSummary[] }>();
const { t } = useI18n();
</script>

<template>
  <q-list v-if="items.length" separator>
    <q-item v-for="event in items" :key="event.id" data-test="recent-block">
      <q-item-section>
        <q-item-label class="ellipsis">{{ event.user_email }}</q-item-label>
        <q-item-label caption>
          {{ formatDateTime(event.created_at) }} · {{ orEmpty(event.rule) }}
        </q-item-label>
      </q-item-section>
      <q-item-section side>
        <ActionBadge :action="event.action" />
      </q-item-section>
    </q-item>
  </q-list>
  <div v-else class="text-grey-6 text-body2 q-pa-md" data-test="recent-empty">
    {{ t('dashboard.noBlocks') }}
  </div>
</template>
