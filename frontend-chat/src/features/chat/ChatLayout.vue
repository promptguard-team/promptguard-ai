<script setup lang="ts">
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';
import { useQuasar } from 'quasar';
import { CONVERSATION_ROUTE } from '@/router/guard';
import { useAuthStore } from '@/stores/auth';
import { useConversationsStore } from '@/stores/conversations';
import { toggleTheme } from '@/theme';
import ChatInput from './ChatInput.vue';
import ConversationDrawer from './ConversationDrawer.vue';
import EmptyState from './EmptyState.vue';
import MessageList from './MessageList.vue';

const { t } = useI18n();
const $q = useQuasar();
const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const conversations = useConversationsStore();

// With show-if-above the drawer opens itself on wide screens and starts closed on narrow ones.
const drawerOpen = ref(false);

const activeId = computed(() => (typeof route.params.id === 'string' ? route.params.id : null));
const active = computed(() =>
  activeId.value === null ? undefined : conversations.get(activeId.value),
);
const messages = computed(() => active.value?.messages ?? []);

/** Fills the q-page with a fixed-height flex column so only the message list scrolls. */
function pageStyle(offset: number, height: number): Record<string, string> {
  return { height: `${height - offset}px` };
}

function openConversation(id: string): Promise<unknown> {
  return router.push({ name: CONVERSATION_ROUTE, params: { id } });
}

/** On narrow screens the drawer overlays the chat, so it gets out of the way after a choice. */
function closeOverlayDrawer(): void {
  if ($q.screen.lt.md) {
    drawerOpen.value = false;
  }
}

async function onSend(text: string): Promise<void> {
  if (conversations.sending) {
    return;
  }
  // Create the conversation up front so the route changes before the reply arrives.
  const id = activeId.value ?? conversations.create(text);
  if (id !== activeId.value) {
    await openConversation(id);
  }
  await conversations.send(id, text);
}

function onRetry(messageId: string): void {
  if (activeId.value !== null) {
    void conversations.retry(activeId.value, messageId);
  }
}

async function onCreate(): Promise<void> {
  closeOverlayDrawer();
  await router.push('/');
}

async function onSelect(id: string): Promise<void> {
  closeOverlayDrawer();
  await openConversation(id);
}

async function onRemove(id: string): Promise<void> {
  conversations.remove(id);
  if (id === activeId.value) {
    await router.push('/');
  }
}

async function onLogout(): Promise<void> {
  auth.clearSession();
  conversations.unload();
  await router.push('/login');
}
</script>

<template>
  <q-layout view="lHh Lpr lFf">
    <q-header class="chat-header">
      <q-toolbar>
        <q-btn
          flat
          dense
          round
          icon="menu"
          :aria-label="t('drawer.toggleDrawer')"
          @click="drawerOpen = !drawerOpen"
        />
        <q-toolbar-title class="text-subtitle1">{{ t('app.name') }}</q-toolbar-title>
      </q-toolbar>
    </q-header>

    <q-drawer v-model="drawerOpen" show-if-above bordered :width="260" :breakpoint="1023">
      <ConversationDrawer
        :conversations="conversations.sorted"
        :active-id="activeId"
        :user-email="auth.user?.email ?? ''"
        :dark="$q.dark.isActive"
        @create="onCreate"
        @select="onSelect"
        @remove="onRemove"
        @toggle-theme="toggleTheme"
        @logout="onLogout"
      />
    </q-drawer>

    <q-page-container>
      <q-page class="chat-page" :style-fn="pageStyle">
        <EmptyState v-if="messages.length === 0">
          <ChatInput :key="activeId ?? 'new'" :disabled="conversations.sending" @send="onSend" />
        </EmptyState>
        <template v-else>
          <MessageList :messages="messages" @retry="onRetry" />
          <div class="chat-page__input">
            <ChatInput :key="activeId ?? 'new'" :disabled="conversations.sending" @send="onSend" />
          </div>
        </template>
      </q-page>
    </q-page-container>
  </q-layout>
</template>

<style scoped lang="sass">
.chat-header
  background: transparent
  color: inherit
  box-shadow: none

.chat-page
  display: flex
  flex-direction: column
  overflow: hidden

.chat-page__input
  max-width: 760px
  width: 100%
  margin: 0 auto
  padding: 0 16px 16px
</style>
