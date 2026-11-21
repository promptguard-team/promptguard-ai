<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { PROMPT_MAX } from '@/stores/conversations';

const COUNTER_FROM = 30000;
const MAX_ROWS = 6;
const LINE_HEIGHT_PX = 24;

const props = defineProps<{ disabled: boolean }>();
const emit = defineEmits<{ send: [text: string] }>();

const { t } = useI18n();
const text = ref('');
const textarea = ref<HTMLTextAreaElement | null>(null);

const length = computed(() => text.value.length);
const tooLong = computed(() => length.value > PROMPT_MAX);
const showCounter = computed(() => length.value > COUNTER_FROM);
const fieldStyle = {
  '--chat-input-max-rows': MAX_ROWS,
  '--chat-input-line-height': `${LINE_HEIGHT_PX}px`,
};
const canSend = computed(() => !props.disabled && !tooLong.value && text.value.trim().length > 0);

function resize(): void {
  const el = textarea.value;
  if (el === null) {
    return;
  }
  el.style.height = 'auto';
  const lineHeight = parseFloat(getComputedStyle(el).lineHeight) || LINE_HEIGHT_PX;
  el.style.height = `${Math.min(el.scrollHeight, lineHeight * MAX_ROWS)}px`;
}

function submit(): void {
  if (!canSend.value) {
    return;
  }
  emit('send', text.value.trim());
  text.value = '';
  void nextTick(resize);
  focusField();
}

function focusField(): void {
  textarea.value?.focus();
}

onMounted(focusField);

watch(
  () => props.disabled,
  (now, before) => {
    if (before && !now) {
      void nextTick(focusField);
    }
  },
);

function onKeydown(event: KeyboardEvent): void {
  if (event.isComposing || event.keyCode === 229) {
    return;
  }
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    submit();
  }
}
</script>

<template>
  <div class="chat-input" :class="{ 'chat-input--disabled': disabled }">
    <textarea
      ref="textarea"
      v-model="text"
      class="chat-input__field"
      rows="1"
      :style="fieldStyle"
      :placeholder="t('chat.placeholder')"
      :aria-label="t('chat.placeholder')"
      :disabled="disabled"
      @input="resize"
      @keydown="onKeydown"
    />
    <div class="chat-input__footer">
      <span
        v-if="showCounter"
        data-test="counter"
        class="chat-input__counter"
        aria-live="polite"
        :class="{ 'text-negative': tooLong }"
      >
        {{ t('chat.charCount', { count: length, max: PROMPT_MAX }) }}
      </span>
      <q-btn
        round
        unelevated
        color="primary"
        icon="arrow_upward"
        size="sm"
        :disable="!canSend"
        :aria-label="t('chat.send')"
        @click="submit"
      />
    </div>
  </div>
</template>

<style scoped lang="sass">
.chat-input
  display: flex
  flex-direction: column
  gap: 4px
  padding: 10px 12px
  border-radius: 16px
  border: 1px solid rgba(127, 127, 127, 0.35)
  background: var(--q-dark)
  body.body--light &
    background: #fff

.chat-input__field
  width: 100%
  resize: none
  border: none
  outline: none
  background: transparent
  color: inherit
  font: inherit
  line-height: var(--chat-input-line-height)
  max-height: calc(var(--chat-input-max-rows) * var(--chat-input-line-height))

.chat-input__footer
  display: flex
  justify-content: flex-end
  align-items: center
  gap: 8px

.chat-input__counter
  font-size: 12px
  opacity: 0.7
</style>
