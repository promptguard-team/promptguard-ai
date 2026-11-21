<script setup lang="ts">
import { useI18n } from 'vue-i18n';

const { t } = useI18n();
</script>

<template>
  <div class="empty-state">
    <h1 class="empty-state__greeting">{{ t('chat.greeting') }}</h1>
    <div class="empty-state__input">
      <slot />
    </div>
  </div>
</template>

<style scoped lang="sass">
.empty-state
  flex: 1
  min-height: 0
  display: flex
  flex-direction: column
  align-items: center
  justify-content: center
  padding: 16px

.empty-state__greeting
  font-size: 28px
  font-weight: 500
  line-height: 1.2
  letter-spacing: normal
  margin: 0 0 24px
  text-align: center

.empty-state__input
  width: 100%
  max-width: 760px
</style>
