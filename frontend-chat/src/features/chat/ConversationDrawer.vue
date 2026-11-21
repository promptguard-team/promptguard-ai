<script setup lang="ts">
import { useI18n } from 'vue-i18n';
import type { Conversation } from '@/stores/types';

defineProps<{
  conversations: Conversation[];
  activeId: string | null;
  userEmail: string;
  dark: boolean;
}>();

const emit = defineEmits<{
  create: [];
  select: [id: string];
  remove: [id: string];
  toggleTheme: [];
  logout: [];
}>();

const { t } = useI18n();
</script>

<template>
  <div class="drawer column no-wrap full-height">
    <div class="q-pa-sm">
      <q-btn
        flat
        no-caps
        align="left"
        class="full-width"
        icon="add"
        :label="t('drawer.newChat')"
        @click="emit('create')"
      />
    </div>

    <q-scroll-area class="col">
      <q-list dense padding>
        <q-item-label header class="text-grey-6">{{ t('drawer.conversations') }}</q-item-label>
        <q-item v-if="conversations.length === 0" class="text-grey-6">
          <q-item-section>{{ t('drawer.empty') }}</q-item-section>
        </q-item>
        <q-item
          v-for="conversation in conversations"
          :key="conversation.id"
          clickable
          :active="conversation.id === activeId"
          active-class="drawer__item--active"
          class="drawer__item"
          @click="emit('select', conversation.id)"
        >
          <q-item-section>
            <q-item-label lines="1">{{ conversation.title || t('drawer.untitled') }}</q-item-label>
          </q-item-section>
          <q-item-section side>
            <q-btn
              flat
              dense
              round
              size="sm"
              icon="more_horiz"
              :aria-label="t('drawer.more')"
              @click.stop
            >
              <q-menu auto-close>
                <q-list dense>
                  <q-item clickable @click="emit('remove', conversation.id)">
                    <q-item-section avatar>
                      <q-icon name="delete_outline" size="18px" />
                    </q-item-section>
                    <q-item-section>{{ t('drawer.delete') }}</q-item-section>
                  </q-item>
                </q-list>
              </q-menu>
            </q-btn>
          </q-item-section>
        </q-item>
      </q-list>
    </q-scroll-area>

    <q-separator />
    <div class="row no-wrap items-center q-pa-sm q-gutter-xs">
      <q-icon name="account_circle" size="22px" class="text-grey-6" />
      <div class="col ellipsis text-caption" :title="userEmail">{{ userEmail }}</div>
      <q-btn
        flat
        dense
        round
        size="sm"
        :icon="dark ? 'light_mode' : 'dark_mode'"
        :aria-label="t('drawer.toggleTheme')"
        @click="emit('toggleTheme')"
      />
      <q-btn
        flat
        dense
        round
        size="sm"
        icon="logout"
        :aria-label="t('drawer.logout')"
        @click="emit('logout')"
      />
    </div>
  </div>
</template>

<style scoped lang="sass">
.drawer__item
  border-radius: 8px
  margin: 0 8px

.drawer__item--active
  background: rgba(59, 130, 246, 0.18)
  color: inherit
</style>
