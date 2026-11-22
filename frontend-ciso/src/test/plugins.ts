import { createPinia, type Pinia } from 'pinia';
import { Quasar } from 'quasar';
import type { Plugin } from 'vue';
import { i18n } from '@/i18n';

/** Plugins every component test mounts with. Pass a pinia to pre-seed stores. */
export function appPlugins(pinia: Pinia = createPinia()): Array<Plugin | [Plugin, unknown]> {
  return [[Quasar, {}], pinia, i18n];
}
