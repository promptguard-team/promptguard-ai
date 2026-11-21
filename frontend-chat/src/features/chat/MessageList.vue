<script setup lang="ts">
import { nextTick, ref, watch } from 'vue';
import type { Message } from '@/stores/types';
import MessageBubble from './MessageBubble.vue';

const props = defineProps<{ messages: Message[] }>();
const emit = defineEmits<{ retry: [messageId: string] }>();

const scroller = ref<HTMLElement | null>(null);

// Follow new messages, status changes of the last one, and switches between conversations.
watch(
  () => [props.messages, props.messages.length, props.messages.at(-1)?.status],
  async () => {
    await nextTick();
    const el = scroller.value;
    if (el !== null) {
      el.scrollTop = el.scrollHeight;
    }
  },
  { immediate: true },
);
</script>

<template>
  <div ref="scroller" class="message-list">
    <div class="message-list__column">
      <!-- The store only retries the last message, so only that one offers the button. -->
      <MessageBubble
        v-for="(message, index) in messages"
        :key="message.id"
        :message="message"
        :can-retry="index === messages.length - 1"
        @retry="emit('retry', message.id)"
      />
    </div>
  </div>
</template>

<style scoped lang="sass">
.message-list
  flex: 1
  min-height: 0
  overflow-y: auto
  padding: 16px

.message-list__column
  max-width: 760px
  margin: 0 auto
</style>
