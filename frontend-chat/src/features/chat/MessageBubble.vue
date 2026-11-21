<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { renderMarkdown } from '@/markdown';
import type { Message } from '@/stores/types';

const props = withDefaults(defineProps<{ message: Message; canRetry?: boolean }>(), {
  canRetry: true,
});
const emit = defineEmits<{ retry: [] }>();

const { t } = useI18n();

const html = computed(() =>
  props.message.role === 'assistant' && props.message.status === 'ok'
    ? renderMarkdown(props.message.text)
    : '',
);

const errorCopy = computed(() =>
  props.message.errorKind === 'provider' ? t('chat.providerUnavailable') : t('chat.networkError'),
);
</script>

<template>
  <div class="message" :class="`message--${message.role}`">
    <template v-if="message.role === 'user'">
      <div class="message__bubble">
        <div class="message__text">{{ message.text }}</div>
      </div>
      <div v-if="message.status === 'blocked'" class="message__note message__note--warning">
        <q-icon name="shield" size="16px" />
        <span>{{ t('chat.promptBlocked') }}</span>
      </div>
    </template>

    <template v-else>
      <div
        v-if="message.status === 'sending'"
        data-test="typing"
        class="message__typing"
        role="status"
        :aria-label="t('chat.thinking')"
      >
        <span aria-hidden="true" /><span aria-hidden="true" /><span aria-hidden="true" />
      </div>
      <!-- Sanitised by renderMarkdown (src/markdown.ts); v-html is safe here. -->
      <div v-else-if="message.status === 'ok'" class="markdown" v-html="html" />
      <div v-else-if="message.status === 'blocked'" class="message__note message__note--warning">
        <q-icon name="shield" size="16px" />
        <span>{{ t('chat.responseBlocked') }}</span>
      </div>
      <div v-else class="message__note message__note--negative">
        <q-icon name="error_outline" size="16px" />
        <span>{{ errorCopy }}</span>
        <q-btn
          v-if="canRetry"
          data-test="retry"
          flat
          dense
          no-caps
          size="sm"
          :label="t('chat.retry')"
          @click="emit('retry')"
        />
      </div>
    </template>
  </div>
</template>

<style scoped lang="sass">
.message
  display: flex
  flex-direction: column
  gap: 6px
  margin: 12px 0
  max-width: 100%

.message--user
  align-items: flex-end

.message__bubble
  max-width: 80%
  padding: 10px 14px
  border-radius: 16px
  background: rgba(127, 127, 127, 0.18)

.message__text
  white-space: pre-wrap
  overflow-wrap: anywhere

.message__note
  display: inline-flex
  align-items: center
  gap: 6px
  font-size: 13px

// Dark-theme colours (default); light overrides live in styles/app.sass because
// scoped :global() drops the descendant selector. Both reach WCAG AA (>= 4.5:1).
.message__note--warning
  color: #fbbf24

.message__note--negative
  color: #f87171

.message__typing
  display: inline-flex
  gap: 4px
  padding: 8px 0
  span
    width: 6px
    height: 6px
    border-radius: 50%
    background: currentColor
    opacity: 0.4
    animation: pulse 1.2s infinite ease-in-out
    &:nth-child(2)
      animation-delay: 0.2s
    &:nth-child(3)
      animation-delay: 0.4s

@media (prefers-reduced-motion: reduce)
  .message__typing span
    animation: none

@keyframes pulse
  0%, 80%, 100%
    opacity: 0.4
  40%
    opacity: 1
</style>
